import subprocess

from modules.control.broker import BrokerDispatcher
from modules.control.policy import BrokerPolicy


def request(action, params=None, **overrides):
    payload = {
        "version": 1,
        "request_id": "test-request-1",
        "action": action,
        "params": params or {},
        "confirmed": False,
        "reason": "",
    }
    payload.update(overrides)
    return payload


def test_policy_denies_unknown_actions():
    decision = BrokerPolicy().evaluate(request("shell.execute", {"command": "id"}))
    assert decision.allowed is False
    assert decision.reason == "Action is not allowlisted"


def test_policy_allows_read_only_status_for_allowlisted_service():
    decision = BrokerPolicy().evaluate(request("service.status", {"name": "jarvis.service"}))
    assert decision.allowed is True
    assert decision.mutating is False


def test_policy_denies_unlisted_service_and_extra_parameters():
    policy = BrokerPolicy()
    assert policy.evaluate(request("service.status", {"name": "ssh.service"})).allowed is False
    assert policy.evaluate(
        request("service.status", {"name": "jarvis.service", "command": "whoami"})
    ).allowed is False


def test_mutation_requires_confirmation_reason_and_request_id():
    policy = BrokerPolicy()
    base = request("service.restart", {"name": "astra-shell.service"})
    assert policy.evaluate(base).allowed is False
    assert policy.evaluate({**base, "confirmed": True}).allowed is False
    assert policy.evaluate({**base, "confirmed": True, "reason": "operator requested"}).allowed is True


def test_dispatcher_uses_argument_vector_without_shell():
    calls = []

    def runner(command, **kwargs):
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(command, 0, stdout="active\n", stderr="")

    result = BrokerDispatcher(runner=runner).execute(
        "service.status", {"name": "jarvis.service"}
    )

    assert result["returncode"] == 0
    assert calls[0][0] == ["/usr/bin/systemctl", "status", "--", "jarvis.service"]
    assert "shell" not in calls[0][1]
