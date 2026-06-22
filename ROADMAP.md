# A.S.T.R.A OS Engineering Roadmap

This is the canonical implementation roadmap for the Debian-based A.S.T.R.A
operating environment. Historical `PHASE*.md` files describe earlier JARVIS
application work; they are evidence, not the OS release plan.

For the current implementation snapshot, verification commands, known gaps,
and next developer handoff, read `DEVELOPMENT_STATUS.md`.

## Engineering principles

- Build on the supported Debian Linux kernel before considering custom patches.
- Keep the agent runtime unprivileged; mediate privileged operations through a
  narrow, authenticated policy service.
- Every mutating capability must be authorized, auditable, reversible where
  possible, and testable against simulation.
- A phase is complete only when its acceptance gate is reproducible in CI or on
  documented target hardware.

## Phase 0 — Baseline and reproducibility (active)

Deliverables:

- One canonical React/FastAPI development entrypoint.
- Static distribution preflight and shell syntax validation.
- Pinned Debian release, package inputs, Python dependencies, and frontend lockfile.
- Honest separation between implemented behavior and release claims.

Gate: `python scripts/validate_distribution.py` and focused tests pass on Debian.

## Phase 1 — Bootable Debian image

Status: active. Non-interactive build controls, provenance generation, serial
readiness marker, and QEMU smoke harness exist; an actual clean-host build and
boot artifact are still required.

Deliverables:

- Reproducible `live-build` configuration for BIOS and UEFI targets.
- A.S.T.R.A branding, kernel command line, systemd targets, and recovery entry.
- Automated QEMU smoke test proving the image reaches `multi-user.target`.
- SHA-256 manifest and build provenance for every image.

Gate: a clean builder produces an ISO that boots in QEMU without manual steps.

## Phase 2 — Core runtime packaging

Deliverables:

- Debian packages for the runtime, web interface, configuration, and services.
- Dedicated system users, immutable application files, writable state directories,
  upgrade/rollback scripts, and migration handling.
- Separate backend, spatial-shell, and first-boot systemd units.

Gate: install, upgrade, rollback, and purge succeed in a disposable Debian VM.

## Phase 3 — Privileged control plane

Deliverables:

- Authenticated broker for package, service, network, power, and device mutations.
- Deny-by-default RBAC/polkit policy with human confirmation for high-risk actions.
- Structured append-only audit events and emergency safe mode.

Gate: the agent runtime has no root privileges and cannot bypass the broker.

## Phase 4 — HAL and hardware adapters

Deliverables:

- Versioned HAL contract and simulated adapter.
- Linux adapters for input, audio, video, storage, network, power, sensors, and GPUs.
- Capability discovery, hot-plug events, timeouts, and fault containment.

Gate: contract tests pass in simulation and on the supported hardware matrix.

## Phase 5 — Agentic operating runtime

Deliverables:

- Planner/executor separation, durable tasks, cancellation, budgets, and retries.
- Local-first model routing, memory governance, provenance, and tool-result validation.
- Multi-agent orchestration constrained by identity and policy.

Gate: representative infrastructure tasks complete safely under injected failures.

## Phase 6 — Spatial interaction environment

Deliverables:

- Boot-to-shell user session, accessible keyboard fallback, voice, vision, gestures,
  notifications, and explicit consent indicators for sensors.
- User enrollment and secure per-user preferences.

Gate: end-to-end interaction tests pass without requiring cloud connectivity.

## Phase 7 — Infrastructure fabric

Deliverables:

- Enrolled-node identity, inventory, remote execution, scheduling, secrets delivery,
  telemetry, and policy distribution.
- Offline behavior, quorum rules, and fleet recovery procedures.

Gate: a staged multi-node environment survives controller and network failures.

## Phase 8 — Security and release engineering

Deliverables:

- Secure Boot strategy, signed APT repository, SBOM, vulnerability scanning,
  reproducible artifacts, key rotation, incident response, and recovery media.

Gate: a signed release passes security review and disaster-recovery rehearsal.

## Phase 9 — Hardware certification and production rollout

Deliverables:

- Supported hardware matrix, thermal/stress evidence, performance budgets,
  staged deployment rings, support lifecycle, and update SLAs.

Gate: release evidence is captured across every certified target configuration.
