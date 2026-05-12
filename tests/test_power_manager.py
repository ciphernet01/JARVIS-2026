"""Test PowerManager functionality."""
import pytest
from modules.services.power_manager import PowerManager, PowerState, PowerActionResult, PowerAction


def test_power_manager_singleton():
    """Test that PowerManager is a proper singleton."""
    mgr1 = PowerManager()
    mgr2 = PowerManager()
    assert mgr1 is mgr2


def test_power_state_structure():
    """Test that power state has correct structure."""
    mgr = PowerManager()
    state = mgr.state()
    
    assert isinstance(state, PowerState)
    assert isinstance(state.ac_powered, bool)
    assert isinstance(state.charging, bool)
    assert isinstance(state.on_battery, bool)
    assert isinstance(state.low_battery, bool)
    assert isinstance(state.critical_battery, bool)
    
    # battery_percent can be float, int or None
    assert state.battery_percent is None or isinstance(state.battery_percent, (float, int))
    # estimated_runtime can be float or None
    assert state.estimated_runtime_minutes is None or isinstance(state.estimated_runtime_minutes, float)


def test_power_state_immutability():
    """Test that PowerState is immutable."""
    state = PowerState(
        ac_powered=True,
        battery_percent=100.0,
        charging=False,
        on_battery=False,
        low_battery=False,
        critical_battery=False,
        estimated_runtime_minutes=None
    )
    
    with pytest.raises(AttributeError):
        state.ac_powered = False


def test_power_action_result_immutability():
    """Test that PowerActionResult is immutable."""
    result = PowerActionResult(
        success=True,
        action=PowerAction.SLEEP,
        message="Test"
    )
    
    with pytest.raises(AttributeError):
        result.success = False


def test_power_action_enum():
    """Test PowerAction enum values."""
    assert PowerAction.SLEEP.value == "sleep"
    assert PowerAction.RESTART.value == "restart"
    assert PowerAction.SHUTDOWN.value == "shutdown"
    assert PowerAction.HIBERNATE.value == "hibernate"


def test_sleep_without_confirmation():
    """Test that sleep requires confirmation."""
    mgr = PowerManager()
    result = mgr.sleep(confirmed=False)
    
    assert not result.success
    assert result.action == PowerAction.SLEEP
    assert "confirmation" in result.message.lower()


def test_restart_without_confirmation():
    """Test that restart requires confirmation."""
    mgr = PowerManager()
    result = mgr.restart(confirmed=False)
    
    assert not result.success
    assert result.action == PowerAction.RESTART
    assert "confirmation" in result.message.lower()


def test_shutdown_without_confirmation():
    """Test that shutdown requires confirmation."""
    mgr = PowerManager()
    result = mgr.shutdown(confirmed=False)
    
    assert not result.success
    assert result.action == PowerAction.SHUTDOWN
    assert "confirmation" in result.message.lower()


def test_hibernate_without_confirmation():
    """Test that hibernate requires confirmation."""
    mgr = PowerManager()
    result = mgr.hibernate(confirmed=False)
    
    assert not result.success
    assert result.action == PowerAction.HIBERNATE
    assert "confirmation" in result.message.lower()


def test_capability_matrix():
    """Test power management capability matrix generation."""
    mgr = PowerManager()
    capabilities = mgr.capability_matrix()
    
    assert isinstance(capabilities, dict)
    assert "ac_powered" in capabilities
    assert "on_battery" in capabilities
    assert "can_sleep" in capabilities
    assert "can_restart" in capabilities
    assert "can_shutdown" in capabilities
    assert "can_hibernate" in capabilities
    assert "battery_available" in capabilities
    
    # Basic boolean checks
    assert isinstance(capabilities["can_sleep"], bool)
    assert isinstance(capabilities["can_restart"], bool)
    assert isinstance(capabilities["can_shutdown"], bool)


def test_cancel_pending_action():
    """Test cancel pending action."""
    mgr = PowerManager()
    result = mgr.cancel_pending_action()
    
    # Should return a PowerActionResult
    assert isinstance(result, PowerActionResult)
    assert isinstance(result.success, bool)
    assert result.action == PowerAction.SHUTDOWN
    assert isinstance(result.message, str)


def test_power_state_consistency():
    """Test that consecutive power state calls are consistent."""
    mgr = PowerManager()
    state1 = mgr.state()
    state2 = mgr.state()
    
    # Both should have same power source status
    assert state1.ac_powered == state2.ac_powered
    assert state1.on_battery == state2.on_battery
    
    # Battery status should be consistent
    assert state1.battery_percent == state2.battery_percent or (state1.battery_percent is None and state2.battery_percent is None)


def test_battery_thresholds():
    """Test battery low/critical thresholds."""
    # Battery at 15% should be low but not critical
    state = PowerState(
        ac_powered=False,
        battery_percent=15.0,
        charging=False,
        on_battery=True,
        low_battery=True,
        critical_battery=False,
        estimated_runtime_minutes=60.0
    )
    
    assert state.low_battery
    assert not state.critical_battery
    
    # Battery at 5% should be critical
    state = PowerState(
        ac_powered=False,
        battery_percent=5.0,
        charging=False,
        on_battery=True,
        low_battery=True,
        critical_battery=True,
        estimated_runtime_minutes=15.0
    )
    
    assert state.low_battery
    assert state.critical_battery
