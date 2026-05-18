from modules.services.security_audit_manager import SecurityAuditManager


class SafetyStateStub:
    safety_gates = [
        "confirm_power_actions",
        "confirm_package_changes",
        "confirm_service_lifecycle",
        "workspace_path_boundary",
        "audit_sensitive_actions",
    ]


def test_security_audit_report_structure(tmp_path):
    manager = SecurityAuditManager(workspace_root=str(tmp_path))

    report = manager.run_audit(
        cors_origins=["http://localhost:3000"],
        session_tokens={"a" * 32: {"user_id": "test"}},
        safety_state=SafetyStateStub(),
        save=True,
    )

    assert report["id"].startswith("security-audit-")
    assert report["overall_status"] in {"pass", "warn", "fail"}
    assert 0 <= report["score"] <= 1
    assert len(report["checks"]) >= 6
    assert (tmp_path / "test_reports" / "security_audit" / f"{report['id']}.json").exists()


def test_security_audit_flags_wildcard_cors(tmp_path):
    manager = SecurityAuditManager(workspace_root=str(tmp_path))

    report = manager.run_audit(cors_origins=["*"], session_tokens={}, safety_state=SafetyStateStub(), save=False)
    cors = next(check for check in report["checks"] if check["key"] == "cors_policy")

    assert cors["status"] == "warn"
    assert "wildcard" in cors["detail"].lower()


def test_security_audit_flags_short_tokens(tmp_path):
    manager = SecurityAuditManager(workspace_root=str(tmp_path))

    report = manager.run_audit(cors_origins=[], session_tokens={"short": {}}, safety_state=SafetyStateStub(), save=False)
    token_check = next(check for check in report["checks"] if check["key"] == "session_tokens")

    assert token_check["status"] == "fail"


def test_security_audit_warns_on_empty_optional_provider_keys(tmp_path):
    (tmp_path / ".env").write_text("GEMINI_API_KEY=\nXAI_API_KEY=\n", encoding="utf-8")
    manager = SecurityAuditManager(workspace_root=str(tmp_path))

    report = manager.run_audit(cors_origins=[], session_tokens={}, safety_state=SafetyStateStub(), save=False)
    env_check = next(check for check in report["checks"] if check["key"] == "env_file")

    assert env_check["status"] == "warn"


def test_security_audit_fails_on_weak_non_empty_secret(tmp_path):
    (tmp_path / ".env").write_text("GEMINI_API_KEY=changeme\n", encoding="utf-8")
    manager = SecurityAuditManager(workspace_root=str(tmp_path))

    report = manager.run_audit(cors_origins=[], session_tokens={}, safety_state=SafetyStateStub(), save=False)
    env_check = next(check for check in report["checks"] if check["key"] == "env_file")

    assert env_check["status"] == "fail"


def test_security_audit_flags_missing_safety_gates(tmp_path):
    class UnsafeState:
        safety_gates = ["workspace_path_boundary"]

    manager = SecurityAuditManager(workspace_root=str(tmp_path))

    report = manager.run_audit(cors_origins=[], session_tokens={}, safety_state=UnsafeState(), save=False)
    safety = next(check for check in report["checks"] if check["key"] == "safety_gates")

    assert safety["status"] == "fail"
    assert report["overall_status"] == "fail"


def test_security_audit_lists_saved_reports(tmp_path):
    manager = SecurityAuditManager(workspace_root=str(tmp_path))
    report = manager.run_audit(cors_origins=[], session_tokens={}, safety_state=SafetyStateStub(), save=True)

    reports = manager.list_reports()

    assert reports[0]["id"] == report["id"]
