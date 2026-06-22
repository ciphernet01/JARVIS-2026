# A.S.T.R.A Operating System Distribution

Prototype bootable Debian-based environment for A.S.T.R.A, the Agentic Spatial
Task Reasoning Architecture. The image still stages immutable application code
under `/opt/jarvis` for compatibility, while runtime state belongs under
`/var/lib/astra`.

The distribution is currently a prototype. Use the repository-level
`ROADMAP.md` for canonical phase gates and run the static preflight before an
image build:

```bash
python scripts/validate_distribution.py
```

## Architecture

```
┌─────────────────────────────────────────────────┐
│         JARVIS AI Core (Brain)                  │
│    - LLM Router & ReActAgent                    │
│    - Decision Engine                             │
│    - System Orchestration                        │
└─────────────────────────────────────────────────┘
           ↓↓↓ System Control ↓↓↓
┌─────────────────────────────────────────────────┐
│  OS Service Layer                               │
│  ├─ AudioManager (⚙️ Voice I/O)                 │
│  ├─ CameraManager (👁️ Vision)                   │
│  ├─ PowerManager (⚡ Power)                     │
│  ├─ NetworkManager (🌐 Connectivity)           │
│  ├─ ServiceManager (🔧 Processes)              │
│  └─ DeviceManager (🖥️ Hardware)                │
└─────────────────────────────────────────────────┘
           ↓↓↓ System Calls ↓↓↓
┌─────────────────────────────────────────────────┐
│  Debian Linux Kernel                            │
│  - Custom voice-optimized kernel                │
│  - Systemd service management                   │
│  - Hardware abstraction layer                   │
└─────────────────────────────────────────────────┘
```

## Build Process

### 1. Live-Build Configuration
- Debian bookworm base
- Custom kernel with voice support
- Minimal desktop environment (lightweight)
- JARVIS as primary system controller

### 2. System Integration
- JARVIS runs as systemd service
- All OS operations routed through JARVIS
- Voice-first interface (primary)
- Traditional CLI fallback

### 3. Boot Sequence
```
1. BIOS/UEFI → Bootloader (GRUB)
2. Linux Kernel loads
3. systemd starts services
4. JARVIS service activates (PID 1 equivalent)
5. Audio system initializes
6. Voice interface ready
```

### 4. First-Boot Experience
- Hardware detection
- User enrollment & voice training
- Initial system calibration
- Network setup

## Quick Start

### Build ISO
```bash
cd os-distribution
chmod +x build-iso.sh
./build-iso.sh
```

Production rollout gates are tracked in `PRODUCTION_READINESS.md`.

### Installation
- Boot from JARVIS ISO
- Follow first-boot setup wizard
- Complete voice enrollment
- System ready for interaction

## Phase 7 Operator Documents

Use these documents for release-candidate distribution and support:

- `RELEASE_NOTES.md` - current release-candidate scope, evidence requirements, and known warnings
- `USER_MANUAL.md` - operator startup, safety, recovery, validation, and troubleshooting guide
- `PATCH_UPDATE_PROCESS.md` - reversible patch process with required validation gates
- `SUPPORT_WORKFLOW.md` - triage levels, intake checklist, escalation package, and closure checklist
- `VERSION.json` - current package metadata for release-candidate builds

Current readiness should be judged from `ROADMAP_CURRENT_STATUS.md` plus the latest saved release evidence bundle under `test_reports/release_evidence/`.

Generate packaging metadata:

```powershell
python generate_release_manifest.py --notes "release candidate manifest"
```

Plan a patch from two manifests:

```powershell
python plan_update.py os-distribution/manifests/current.json os-distribution/manifests/candidate.json
```

Dry-run a manifest-backed patch payload:

```powershell
python apply_update.py os-distribution/manifests/current.json os-distribution/manifests/candidate.json candidate-payload
```

## System Components

| Component | Role | Status |
|-----------|------|--------|
| JARVIS Core | System Intelligence | ✅ Ready |
| AudioManager | Voice I/O Control | ✅ Ready |
| CameraManager | Vision Processing | ✅ Ready |
| PowerManager | Power Operations | ✅ Ready |
| NetworkManager | Connectivity | ✅ Ready |
| ServiceManager | Process Management | ✅ Ready |
| DeviceManager | Hardware Telemetry | ✅ Ready |

## Configuration Files

- `config/lb_config` - Live-build debconf settings
- `includes/etc/systemd/system/jarvis.service` - JARVIS systemd unit
- `packages.list` - Required Debian packages
- `build-iso.sh` - ISO build automation
- `install-first-boot.sh` - First-boot setup

## System Requirements (Target)

- CPU: 2+ cores (voice processing)
- RAM: 4GB+ (JARVIS + AI models)
- Disk: 20GB minimum
- Audio: Microphone + speakers
- Network: Ethernet or WiFi

## Development

The active release-candidate workflow includes:

- Focused service tests
- Frontend production build
- Security audit
- Performance baseline
- Failover drill
- Release evidence bundle
- Target-machine hardware validation and stress reports

## Next Steps

1. ✅ Configure live-build
2. ✅ Create systemd service
3. ✅ Set up boot integration
4. ✅ Build first ISO
5. ✅ Test on hardware
6. ✅ Release distribution
