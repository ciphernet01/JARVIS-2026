"""Root-side A.S.T.R.A control broker with Unix peer authentication."""

from __future__ import annotations

import argparse
import grp
import json
import os
import pwd
import socket
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional, Tuple

from .policy import BrokerPolicy


DEFAULT_SOCKET_PATH = "/run/astra-control/control.sock"
DEFAULT_AUDIT_PATH = "/var/log/astra-control/audit.jsonl"
MAX_REQUEST_BYTES = 64 * 1024


class BrokerDispatcher:
    def __init__(self, runner: Callable[..., subprocess.CompletedProcess] = subprocess.run):
        self.runner = runner

    def execute(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        if action == "broker.health":
            return {"status": "ok", "service": "astra-control-broker"}
        if action == "service.status":
            return self._systemctl("status", params["name"])
        if action == "service.restart":
            return self._systemctl("restart", params["name"])
        raise ValueError("Action has no dispatcher")

    def _systemctl(self, operation: str, name: str) -> Dict[str, Any]:
        command = ["/usr/bin/systemctl", operation, "--", name]
        completed = self.runner(
            command,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        return {
            "command": command,
            "returncode": completed.returncode,
            "stdout": completed.stdout[-8000:],
            "stderr": completed.stderr[-4000:],
        }


class ControlBroker:
    def __init__(
        self,
        socket_path: str = DEFAULT_SOCKET_PATH,
        audit_path: str = DEFAULT_AUDIT_PATH,
        allowed_group: str = "astra",
        policy: Optional[BrokerPolicy] = None,
        dispatcher: Optional[BrokerDispatcher] = None,
    ):
        self.socket_path = Path(socket_path)
        self.audit_path = Path(audit_path)
        self.allowed_group = allowed_group
        self.policy = policy or BrokerPolicy()
        self.dispatcher = dispatcher or BrokerDispatcher()

    def serve_forever(self) -> None:
        self.socket_path.parent.mkdir(parents=True, exist_ok=True)
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)
        if self.socket_path.exists():
            self.socket_path.unlink()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(str(self.socket_path))
            self._secure_socket()
            server.listen(16)
            while True:
                connection, _ = server.accept()
                with connection:
                    self._handle_connection(connection)

    def _secure_socket(self) -> None:
        group = grp.getgrnam(self.allowed_group)
        os.chown(self.socket_path, 0, group.gr_gid)
        os.chmod(self.socket_path, 0o660)

    def _peer_identity(self, connection: socket.socket) -> Tuple[int, int, int]:
        raw = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        return struct.unpack("3i", raw)

    def _peer_allowed(self, uid: int, gid: int) -> bool:
        if uid == 0:
            return True
        try:
            account = pwd.getpwuid(uid)
            allowed_gid = grp.getgrnam(self.allowed_group).gr_gid
            return allowed_gid in os.getgrouplist(account.pw_name, account.pw_gid) or gid == allowed_gid
        except KeyError:
            return False

    def _read_request(self, connection: socket.socket) -> Dict[str, Any]:
        data = bytearray()
        while not data.endswith(b"\n"):
            chunk = connection.recv(4096)
            if not chunk:
                break
            data.extend(chunk)
            if len(data) > MAX_REQUEST_BYTES:
                raise ValueError("Request is too large")
        request = json.loads(data.decode("utf-8"))
        if not isinstance(request, dict):
            raise ValueError("Request must be an object")
        if request.get("version") != 1:
            raise ValueError("Unsupported protocol version")
        return request

    def _handle_connection(self, connection: socket.socket) -> None:
        pid, uid, gid = self._peer_identity(connection)
        request: Dict[str, Any] = {}
        response: Dict[str, Any]
        try:
            if not self._peer_allowed(uid, gid):
                raise PermissionError("Peer is not authorized for the control socket")
            request = self._read_request(connection)
            decision = self.policy.evaluate(request)
            if not decision.allowed:
                response = {"ok": False, "error": decision.reason, "action": decision.action}
            else:
                result = self.dispatcher.execute(decision.action, request.get("params", {}))
                ok = result.get("returncode", 0) == 0
                response = {"ok": ok, "action": decision.action, "result": result}
        except Exception as exc:
            response = {"ok": False, "error": str(exc), "action": request.get("action", "")}
        self._audit(pid, uid, gid, request, response)
        connection.sendall(json.dumps(response, separators=(",", ":")).encode("utf-8") + b"\n")

    def _audit(
        self,
        pid: int,
        uid: int,
        gid: int,
        request: Dict[str, Any],
        response: Dict[str, Any],
    ) -> None:
        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "peer": {"pid": pid, "uid": uid, "gid": gid},
            "request_id": request.get("request_id"),
            "action": request.get("action"),
            "params": request.get("params", {}),
            "confirmed": request.get("confirmed") is True,
            "reason": request.get("reason", ""),
            "ok": response.get("ok") is True,
            "error": response.get("error"),
        }
        with self.audit_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", default=os.getenv("ASTRA_CONTROL_SOCKET", DEFAULT_SOCKET_PATH))
    parser.add_argument("--audit", default=os.getenv("ASTRA_CONTROL_AUDIT", DEFAULT_AUDIT_PATH))
    parser.add_argument("--group", default=os.getenv("ASTRA_CONTROL_GROUP", "astra"))
    args = parser.parse_args()
    ControlBroker(args.socket, args.audit, args.group).serve_forever()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
