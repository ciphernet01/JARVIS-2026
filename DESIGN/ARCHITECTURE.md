# A.S.T.R.A — Architecture Overview

This document is a concise architecture and gap analysis for A.S.T.R.A (Agentic Spatial Task Reasoning Architecture), the Debian-based operating environment evolving from the JARVIS codebase.

## Goals
- Provide a secure, auditable agentic OS that can orchestrate software, services, and hardware on infrastructure running Debian.
- Expose a modular HAL (hardware abstraction layer) for safe control of devices and low-level system functions.
- Use a ReAct agent brain (LLMRouter + ReActAgent) for planning and execution while enforcing policy and safety.
- Ship as a reproducible, auditable Debian-based distribution with CI, packaging, and signed releases.

## High-level Components
- Agent Brain
  - `core/llm_router.py`, `core/agent.py` (ReActAgent): LLM orchestration, tool function schemas, audit logging
- Orchestrator / Runtime
  - `core/assistant.py`: main orchestrator, tool registration, conversation & session management
  - `backend/server.py`: FastAPI A.S.T.R.A runtime, orchestration queue, health & metrics
- Services & Managers
  - `modules/services/*`: DeviceManager, SystemManager, PowerManager, NetworkManager, PackageManager, etc.
- Skills & Integrations
  - `modules/skills`, `modules/integration/*`: higher-level capability plugins registered as tools
- I/O & Perception
  - `modules/voice`, `modules/vision`, `desktop-overlay` and `frontend` (React UI)
- Persistence & Memory
  - `modules/persistence`, `modules/intelligence/memory_engine` — short-term & episodic memory
- Security
  - `modules/security`, `core/config.py` — vaults, encryption, audit logs, config management
- Packaging & Distribution
  - `os-distribution/`, installer configs, Debian packaging and Calamares modules

## Operating Model & Safety
- Agent acts through explicit tool calls; every tool is audited to `agent_audit.log`.
- HAL and managers must implement capability checks and authorization before performing privileged operations.
- Services should be run under least privilege (system services, polkit, or dedicated users/containers).

## Gaps & Risks (short list)
1. Low-level hardware drivers and safe HAL: missing standard contract and driver adapters for Debian.
2. Privilege/isolation model: unclear enforcement between agent tools and OS privileged actions.
3. Packaging & installer pipeline: Debian packaging, signed repos, and installer integration need work.
4. LLM infra resilience: offline/fallback model and rate-limited provider handling not hardened.
5. Security hardening: key management, secure defaults, and CI secrets handling need audit.
6. Testing: hardware-in-the-loop tests and reproducible integration tests are sparse.
7. Operational telemetry & policy: RBAC, audit retention, and long-term storage policies.

## Recommended Immediate Actions (MVP → 3 months)
1. Define HAL contract (API surface): DeviceManager interface, simulation adapter, and unit tests.
2. Implement a safe simulated `DeviceManager` to enable CI tests without hardware.
3. Add privilege boundary: enforce actions via a PolicyExecutor that validates requests before execution.
4. Create `DESIGN/ARCHITECTURE.md` (this draft) and a short `ROADMAP.md` with milestones and owners.
5. Harden LLM usage: add fallback flows and quota-aware request wrapper in `core/llm_router.py`.
6. Add baseline security tasks: keys in OS vault, rotateable encryption keys, minimal polkit policies.

## Roadmap (high level)
- Phase 0 (now): Architecture draft, HAL contract, simulated DeviceManager, tests
- Phase 1 (1–2 months): Packaging scaffolding, service isolation, basic installer integration
- Phase 2 (2–3 months): Hardware drivers/adapters, security audit, CI for building Debian images
- Phase 3 (3–6 months): Production LLM infra, monitoring, audits, and signed releases

## Next immediate tasks I can do now
- Create a HAL interface spec and a simulated `DeviceManager` with tests.
- Add a `ROADMAP.md` with prioritized milestones and owners.
- Implement a LLM fallback wrapper in `core/llm_router.py`.

If you want, I’ll implement the HAL contract and a safe simulated `DeviceManager` next.
