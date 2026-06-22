from scripts.check_boot_ready_log import DEFAULT_MARKER, log_contains_marker


def test_boot_ready_log_accepts_exact_marker():
    assert log_contains_marker(DEFAULT_MARKER) is True


def test_boot_ready_log_accepts_equivalent_state_marker():
    log_text = "systemd: starting\nASTRA_BOOT_READY something broker=active backend=active\n"
    assert log_contains_marker(log_text) is True


def test_boot_ready_log_rejects_missing_state():
    assert log_contains_marker("boot complete\n") is False
