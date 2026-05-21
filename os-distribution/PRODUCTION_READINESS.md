# A.S.T.R.A OS Production Readiness Gate

A.S.T.R.A, the Agentic Spatial Task Reasoning Architecture, is packaged as a Debian bookworm live-build image with the current assistant stack staged under `/opt/jarvis` for compatibility with existing service paths.

## Required Gates Before Company Rollout

1. Source validation
   - `pytest -q`
   - `npm run build` from `frontend/`
   - `bash -n os-distribution/build-iso.sh`
   - `bash -n os-distribution/jarvis-shell-session.sh`
   - `bash -n os-distribution/first-boot-setup.sh`

2. ISO build validation
   - Build on a Debian or Ubuntu machine with `live-build`, `debootstrap`, and `grub-efi-amd64`.
   - Confirm output name matches `astra-os-YYYYMMDD.iso`.
   - Verify generated `.sha256` checksum before writing media.

3. Boot validation
   - Boot in UEFI mode on at least one clean test PC and one virtual machine.
   - Confirm graphical session starts, backend reaches `/api/health`, and the A.S.T.R.A UI opens.
   - Confirm keyboard, network, audio output, microphone input, camera, sleep, restart, and shutdown behavior.

4. Security validation
   - Replace any test token before release imaging.
   - Confirm no `.env`, `.session_token`, database, memory, backup, test report, or node module artifact is present in the ISO payload.
   - Confirm service logs do not expose credentials.

5. Fleet rollout validation
   - Pilot on a small internal hardware set before broad deployment.
   - Save hardware validation, stress, performance, security audit, and failover evidence in `test_reports/`.
   - Keep rollback media available for every target PC model.

## Current Status

The repository contains the ISO build pipeline and A.S.T.R.A branding, but production approval depends on the latest local test run, a successful ISO build, and target-machine boot evidence. Treat the image as a release candidate until those artifacts exist for the exact commit being deployed.
