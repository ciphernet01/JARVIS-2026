"""Tests for Phase 6 release evidence bundles."""

from modules.services.release_evidence_manager import ReleaseEvidenceManager


class ReportStub:
    def __init__(self, reports):
        self.reports = reports

    def list_reports(self, limit=10):
        return self.reports[:limit]


class BundleStub:
    def __init__(self, bundles):
        self.bundles = bundles

    def list_bundles(self, limit=10):
        return self.bundles[:limit]


def report(id_, status="pass", score=1.0):
    return {
        "id": id_,
        "overall_status": status,
        "score": score,
        "path": f"test_reports/{id_}.json",
    }


def make_manager(tmp_path, security=None, performance=None, failover=None, hardware=None, stress=None):
    return ReleaseEvidenceManager(
        workspace_root=str(tmp_path),
        security_manager=ReportStub(security or []),
        performance_manager=ReportStub(performance or []),
        failover_manager=ReportStub(failover or []),
        hardware_validation_manager=ReportStub(hardware or []),
        hardware_stress_manager=ReportStub(stress or []),
    )


def test_release_evidence_blocks_when_required_reports_missing(tmp_path):
    manager = make_manager(tmp_path)

    bundle = manager.create_bundle(save=False)

    assert bundle["release_status"] == "blocked"
    assert bundle["summary"]["required_missing"] == 3
    assert bundle["score"] == 0


def test_release_evidence_ready_with_recommended_evidence_missing(tmp_path):
    manager = make_manager(
        tmp_path,
        security=[report("security")],
        performance=[report("performance")],
        failover=[report("failover")],
    )

    bundle = manager.create_bundle(save=False)

    assert bundle["release_status"] == "ready_with_warnings"
    assert bundle["summary"]["required_missing"] == 0
    assert bundle["summary"]["missing"] == 2


def test_release_evidence_ready_when_all_reports_pass(tmp_path):
    manager = make_manager(
        tmp_path,
        security=[report("security")],
        performance=[report("performance")],
        failover=[report("failover")],
        hardware=[report("hardware", score=92)],
        stress=[report("stress")],
    )

    bundle = manager.create_bundle(label="rc1", save=False)

    assert bundle["label"] == "rc1"
    assert bundle["release_status"] == "ready"
    assert bundle["score"] == 1.0


def test_release_evidence_blocks_when_required_report_fails(tmp_path):
    manager = make_manager(
        tmp_path,
        security=[report("security", status="fail", score=0.25)],
        performance=[report("performance")],
        failover=[report("failover")],
    )

    bundle = manager.create_bundle(save=False)
    security = next(item for item in bundle["items"] if item["key"] == "security_audit")

    assert bundle["release_status"] == "blocked"
    assert bundle["summary"]["required_failed"] == 1
    assert security["status"] == "fail"


def test_release_evidence_saves_and_lists_bundles(tmp_path):
    manager = make_manager(
        tmp_path,
        security=[report("security")],
        performance=[report("performance")],
        failover=[report("failover")],
        hardware=[report("hardware")],
        stress=[report("stress")],
    )

    bundle = manager.create_bundle(label="saved-evidence", save=True)
    bundles = manager.list_bundles()

    assert (tmp_path / "test_reports" / "release_evidence" / f"{bundle['id']}.json").exists()
    assert bundles[0]["id"] == bundle["id"]
    assert bundles[0]["release_status"] == "ready"
