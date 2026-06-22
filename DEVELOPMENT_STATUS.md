# A.S.T.R.A OS Development Status

Last updated: 2026-06-22

This is the canonical engineering handoff for active development. Read this
file first, then `ROADMAP.md`, before relying on historical `PHASE*.md` reports.

## Product direction

A.S.T.R.A is a Debian-based agentic operating environment, not a new kernel.
Debian Linux owns scheduling, memory, filesystems, drivers, networking, and
process isolation. A.S.T.R.A adds the intelligence runtime, policy-controlled
system orchestration, hardware abstraction, perception, and spatial interface.

Legacy `jarvis` paths and API headers remain where changing them would break
compatibility. New product-facing work should use the A.S.T.R.A name.

## Current architecture

```text
React spatial shell / voice / vision
                 |
          FastAPI backend (astra user)
                 |
      Agent, memory, skills, LLM router
           |                   |
 Local/cloud inference   Unix control socket
                               |
                 Root control broker
                               |
                  systemd / HAL / hardware
```

Important boundaries:

- Application code is staged read-only under `/opt/jarvis`.
- Mutable runtime state belongs under `/var/lib/astra`.
- The backend and spatial shell run as the unprivileged `astra` account.
- Root operations must pass through the deny-by-default control broker.
- The LLM never receives a general root shell.

## Completed foundation slices

### Distribution baseline

- Added the canonical OS roadmap and executable distribution preflight.
- Fixed the development launcher virtual-environment detection bug.
- Enabled Debian security repositories and SHA-256 release checksums.
- Added separate hardened backend and spatial-shell systemd services.
- Added creation of the `astra` system identity during image build/first boot.

### Privileged control plane

- Added a peer-authenticated Unix-socket broker under `modules/control`.
- Policy is deny-by-default; arbitrary commands and parameters are rejected.
- Initial allowlist supports broker health and status/restart for A.S.T.R.A's
  own systemd services.
- Mutations require confirmation, a reason, and a request ID.
- Broker decisions are written to append-only JSONL audit records.
- The broker runs as root in its own hardened unit with an empty capability
  bounding set; the backend remains unprivileged.

### Local intelligence runtime

- Added one OpenAI-compatible adapter for Ollama, vLLM, and llama.cpp servers.
- Local inference is the default configuration; cloud providers are optional
  fallbacks rather than required dependencies.
- Added model/runtime capability discovery through `GET /v1/models`.
- Added authenticated backend reporting at `GET /api/ai/runtime`.
- Capability reports distinguish endpoint reachability, advertised models, and
  whether the configured model is actually present.
- Tool-calling support is reported as unknown until explicitly verified.
- Core package imports are lazy so configuration and local inference do not
  require cloud SDKs.

### Phase 1 build and boot tooling

- Added `--non-interactive` and `--validate-only` ISO builder modes for CI.
- Corrected build-host requirement detection to check the actual `lb` command.
- Documented the Debian 12 build host and required packages in
  `os-distribution/BUILD_HOST.md`.
- Added SHA-256 artifact provenance containing version metadata, source commit,
  dirty-tree state, build environment, and hashes of critical build inputs.
- Added a hardened oneshot boot-readiness unit that requires the broker and
  backend to be active before emitting `ASTRA_BOOT_READY` to the serial console.
- Added a QEMU harness that boots headlessly and treats that serial marker as
  the automated smoke-test gate.

### Self-contained image runtime

- Added `requirements.runtime.txt` as the Linux image dependency boundary.
- The Debian 12 build host resolves Python 3.11 binary wheels before assembling
  the live filesystem.
- Every wheel is recorded with filename, size, and SHA-256 in a deterministic
  manifest that is copied into `/usr/share/doc/astra`.
- The image build creates `/opt/astra/venv` and installs strictly with
  `--no-index` from the staged wheelhouse.
- `jarvis.service` executes `/opt/astra/venv/bin/python`; it no longer relies on
  mutable host Python packages.
- First boot performs no apt, pip, npm, or model downloads. Updates and optional
  model assets must arrive through the controlled A.S.T.R.A update workflow.

### ISO continuous integration

- Added `.github/workflows/astra-iso.yml` with separate validation and build
  jobs.
- The build job uses a privileged Debian 12 container so the release builder
  matches the documented target instead of inheriting Ubuntu host packages.
- CI builds the frontend, resolves and hashes the Python wheelhouse, builds the
  ISO, and boots it through the serial QEMU smoke harness.
- Evidence upload runs even after failure and retains the ISO/checksum/provenance
  when present, wheel manifest, host package inventory, build log, and QEMU
  serial log.
- Concurrency cancellation prevents obsolete builds for the same branch from
  consuming the full ISO build window.

## Verification snapshot

Last successful focused verification:

```bash
python3 -m pytest -q \
  tests/test_local_runtime.py \
  tests/test_llm_factory.py \
  tests/test_llm.py
# 9 passed

python3 scripts/validate_distribution.py --strict
# 6 passed, 0 warnings, 0 failures

python3 -m py_compile \
  core/__init__.py \
  modules/llm/local_runtime.py \
  backend/server.py
```

Control-plane verification from the preceding slice:

```bash
python3 -m pytest -q \
  tests/test_control_broker.py \
  tests/test_distribution_preflight.py
# 7 passed
```

Phase 1 tooling verification:

```bash
./os-distribution/build-iso.sh --validate-only
# 5 passed, 0 warnings, 0 failures

python3 -m pytest -q \
  tests/test_iso_provenance.py \
  tests/test_distribution_preflight.py \
  tests/test_local_runtime.py \
  tests/test_control_broker.py
# 13 passed
```

Offline-runtime verification:

```bash
python3 -m pytest -q \
  tests/test_wheelhouse_manifest.py \
  tests/test_iso_provenance.py \
  tests/test_distribution_preflight.py
# 5 passed
```

CI workflow verification:

```bash
python3 -m pytest -q \
  tests/test_iso_workflow.py \
  tests/test_distribution_preflight.py \
  tests/test_iso_provenance.py \
  tests/test_wheelhouse_manifest.py
# 7 passed
```

The complete suite requires the dependencies in `requirements.linux.txt` and
`backend/requirements.txt`. Backend integration tests are disabled by default
through their test configuration.

## Runtime configuration

Recommended local development variables:

```bash
LLM_PROVIDER=local
LLM_MODEL=qwen2.5-coder:7b
LOCAL_LLM_BASE_URL=http://localhost:11434/v1
LOCAL_LLM_API_KEY=local
```

The runtime is protocol-driven: the model name above is an example, not a
mandatory dependency. Model-weight licenses must be reviewed separately from
the inference-server license.

## Known limitations

- No reproducible ISO has been built in the current environment because
  `live-build`, `debootstrap`, `npm`, and QEMU are unavailable here.
- The QEMU boot harness exists but has not yet been executed against a newly
  built ISO.
- The GitHub ISO workflow has been validated structurally but has not yet
  produced a successful remote build artifact in this development session.
- The wheelhouse uses constrained direct requirements plus an artifact hash
  manifest; a reviewed fully pinned transitive lock remains desirable.
- The control broker only manages A.S.T.R.A service status/restart; package,
  network, power, and hardware mutations remain outside the broker until their
  policies and rollback behavior are defined.
- Tool-calling capability is not yet probed per local model.
- Two historical LLM stacks still exist. New local-runtime work should target
  `modules/llm/local_runtime.py`; compatibility code should be removed only
  after call sites are migrated and tested.
- Hardware validation exists, but production hardware-in-the-loop evidence is
  still required.

## Next engineering target

Run and stabilize the Phase 1 CI boot gate:

1. Trigger `A.S.T.R.A ISO Build and Boot` on GitHub Actions.
2. Inspect `ci-build.log` and `qemu-serial.log` from the uploaded artifact.
3. Fix any dependency, shared-library, live-build, or service-ordering failures.
4. Repeat until the serial log contains
   `ASTRA_BOOT_READY broker=active backend=active`.
5. Record the successful workflow run and artifact hashes here.

Do not expand privileged broker actions until each action has an explicit
allowlist, confirmation policy, audit schema, timeout, and failure/rollback
behavior.

## Handoff checklist

Before starting work:

1. Run `git status --short`; preserve unrelated developer changes.
2. Read this file and `ROADMAP.md`.
3. Run `python3 scripts/validate_distribution.py --strict`.
4. Run the focused tests for the subsystem being changed.
5. Update this document with completed behavior, verification, limitations,
   and the next concrete target before handing work off.
