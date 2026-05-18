"""Test PackageManager package lifecycle planning."""
from modules.services.package_manager import PackageManager, PackageProvider, PackagePlan
from modules.services.safety_manager import SafetyManager


def test_package_provider_state_with_injected_provider():
    provider = PackageProvider("winget", "winget", "Windows", requires_admin=False)
    manager = PackageManager(provider=provider)
    state = manager.provider_state()

    assert state["available"] is True
    assert state["provider"]["name"] == "winget"


def test_winget_install_plan_requires_confirmation():
    provider = PackageProvider("winget", "winget", "Windows", requires_admin=False)
    manager = PackageManager(provider=provider)
    plan = manager.plan("install", "Microsoft.VisualStudioCode")

    assert isinstance(plan, PackagePlan)
    assert plan.requires_confirmation is True
    assert plan.command[:3] == ["winget", "install", "--id"]
    assert "Microsoft.VisualStudioCode" in plan.command


def test_package_execute_dry_run_does_not_run():
    provider = PackageProvider("brew", "brew", "Darwin", requires_admin=False)
    manager = PackageManager(provider=provider)
    result = manager.execute("install", "wget", dry_run=True, confirmed=False)

    assert result.success is False
    assert "Confirmation required" in result.message

    result = manager.execute("install", "wget", dry_run=True, confirmed=True)
    assert result.success is True
    assert result.dry_run is True
    assert result.plan.command == ["brew", "install", "wget"]


def test_safe_mode_blocks_package_changes(tmp_path):
    SafetyManager._instance = None
    SafetyManager._initialized = False
    safety = SafetyManager(workspace_root=str(tmp_path))
    safety.set_safe_mode(True, "unit test")

    provider = PackageProvider("winget", "winget", "Windows", requires_admin=False)
    manager = PackageManager(provider=provider)
    result = manager.execute(
        "uninstall",
        "Example.Package",
        dry_run=False,
        confirmed=True,
        safety_state=safety.state(),
    )

    assert result.success is False
    assert result.plan.blocked is True
    assert "Safe mode" in result.message


def test_search_plan_for_apt_uses_apt_cache():
    provider = PackageProvider("apt-get", "apt-get", "Linux", requires_admin=True)
    manager = PackageManager(provider=provider)
    plan = manager.plan("search", "python3")

    assert plan.command[1:] == ["search", "python3"]
