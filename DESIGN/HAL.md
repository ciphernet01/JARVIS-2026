# Hardware Abstraction Layer (HAL) — Spec

This document defines the minimal HAL contract for A.S.T.R.A so service layers
and the ReAct agent can interact with hardware in a safe, testable way.

Goals:
- Provide a stable, minimal API for device enumeration and control.
- Allow swapping real hardware implementations with simulated ones for CI.
- Enforce capability checks and a policy boundary before privileged actions.

Core interface (Python sketch):

Methods:
- `list_devices() -> List[Dict[str, Any]]`
  - Return list of known devices with `id`, `type`, `status`, `properties`.
- `get_device(device_id: str) -> Optional[Dict[str, Any]]`
- `add_device(device_id: str, device_type: str, properties: Dict) -> Dict`
- `remove_device(device_id: str) -> Dict`
- `set_device_property(device_id: str, key: str, value: Any) -> Dict`
- `get_device_status(device_id: str) -> Dict`
- `power_cycle_device(device_id: str, offline_seconds: float = 0.05) -> Dict`

Policy & Safety:
- All implementations must call into a `PolicyExecutor` before performing
  actions that change device state.
- `PolicyExecutor` verifies caller identity, permission, and logs the decision.

Simulation:
- Implementations must be swappable via a factory method `get_device_manager(simulated: bool)`
  and by environment variable `JARVIS_SIMULATE_DEVICES=1` for CI.

Auditing:
- Tool calls from the ReAct agent must be logged to `agent_audit.log`.
