"""Unprivileged client for the local A.S.T.R.A control broker."""

from __future__ import annotations

import json
import os
import socket
import uuid
from typing import Any, Dict, Optional


DEFAULT_SOCKET_PATH = "/run/astra-control/control.sock"
MAX_RESPONSE_BYTES = 64 * 1024


class ControlBrokerError(RuntimeError):
    pass


class ControlBrokerClient:
    def __init__(self, socket_path: Optional[str] = None, timeout_seconds: float = 10.0):
        self.socket_path = socket_path or os.getenv("ASTRA_CONTROL_SOCKET", DEFAULT_SOCKET_PATH)
        self.timeout_seconds = timeout_seconds

    def request(
        self,
        action: str,
        params: Optional[Dict[str, Any]] = None,
        *,
        confirmed: bool = False,
        reason: str = "",
        request_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "version": 1,
            "request_id": request_id or str(uuid.uuid4()),
            "action": action,
            "params": params or {},
            "confirmed": confirmed,
            "reason": reason,
        }
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8") + b"\n"
        if len(encoded) > MAX_RESPONSE_BYTES:
            raise ControlBrokerError("Broker request is too large")

        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.settimeout(self.timeout_seconds)
                client.connect(self.socket_path)
                client.sendall(encoded)
                chunks = bytearray()
                while not chunks.endswith(b"\n"):
                    chunk = client.recv(4096)
                    if not chunk:
                        break
                    chunks.extend(chunk)
                    if len(chunks) > MAX_RESPONSE_BYTES:
                        raise ControlBrokerError("Broker response is too large")
        except (OSError, TimeoutError) as exc:
            raise ControlBrokerError(f"Control broker unavailable: {exc}") from exc

        try:
            response = json.loads(chunks.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ControlBrokerError("Control broker returned an invalid response") from exc
        if not isinstance(response, dict):
            raise ControlBrokerError("Control broker returned an invalid response object")
        return response
