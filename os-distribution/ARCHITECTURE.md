# JARVIS OS Architecture & Build Guide

## System Architecture

```
┌─────────────────────────────────────────────────────────┐
│                  JARVIS Core (Brain)                    │
│                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  │
│  │ LLM Router   │  │ ReActAgent   │  │ LLMFactory   │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  │
│                                                          │
│  Decision Engine • Task Orchestration • System Control  │
└─────────────────────────────────────────────────────────┘
         ↓ FastAPI REST Layer (port 8001) ↓
┌─────────────────────────────────────────────────────────┐
│         OS Service Managers (19 Endpoints)              │
│                                                          │
│  🎵 AudioManager    • Volume, Microphone, Devices       │
│  👁️ CameraManager   • Snapshots, Face Detection         │
│  ⚡ PowerManager    • Sleep, Restart, Shutdown          │
│  🌐 NetworkManager  • Interfaces, WiFi, Connectivity    │
│  🔧 ServiceManager  • Process Lifecycle                 │
│  🖥️ DeviceManager   • Hardware Telemetry                │
│                                                          │
└─────────────────────────────────────────────────────────┘
         ↓ System Integration Layer ↓
┌─────────────────────────────────────────────────────────┐
│  Systemd Services • Voice Shell • Hardware Abstraction  │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │ JARVIS Service (jarvis.service)                 │    │
│  │ - Starts on boot as core system process         │    │
│  │ - Manages all OS-level operations               │    │
│  │ - Restarts automatically on failure             │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
│  ┌─────────────────────────────────────────────────┐    │
│  │ Voice Shell (jarvis-shell)                      │    │
│  │ - Primary user interaction interface            │    │
│  │ - Direct command routing to JARVIS core         │    │
│  │ - Interactive prompt with command history      │    │
│  └─────────────────────────────────────────────────┘    │
│                                                          │
└─────────────────────────────────────────────────────────┘
         ↓ System Layer ↓
┌─────────────────────────────────────────────────────────┐
│           Debian Linux + systemd                        │
│                                                          │
│  - Custom Debian bookworm live-build ISO               │
│  - PulseAudio for voice I/O                            │
│  - NetworkManager for connectivity                      │
│  - All drivers and firmware pre-integrated             │
│                                                          │
└─────────────────────────────────────────────────────────┘
```

## Build Process

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt-get install live-build debootstrap grub-efi-amd64

# Fedora/RHEL
sudo dnf install live-images debootstrap grub2-efi-x64
```

### Build Steps

1. **Configure Live-Build** (`config/live-build.conf`)
   - Architecture: amd64
   - Bootloader: GRUB EFI
   - Debian distribution: bookworm
   - Firmware support: enabled

2. **Add Packages** (`config/packages.list`)
   - Debian base + development tools
   - Python 3 runtime + dependencies
   - Audio/video libraries
   - Networking tools

3. **Integrate JARVIS**
   - Copy JARVIS code to `/opt/jarvis`
   - Install systemd service
   - Register voice shell

4. **First-Boot Setup** (`first-boot-setup.sh`)
   - Update system packages
   - Configure audio system
   - Initialize database
   - User enrollment
   - Timezone/network setup

5. **Boot Sequence** (`boot-init.sh`)
   - System health checks
   - JARVIS core verification
   - Voice shell launch

### Building the ISO

```bash
cd os-distribution
chmod +x build-iso.sh
sudo ./build-iso.sh
```

Output: `output/jarvis-os-YYYYMMDD.iso`

### Installation

1. **Write to USB**
   ```bash
   sudo dd if=jarvis-os-*.iso of=/dev/sdX bs=4M
   sync
   ```

2. **Boot from USB**
   - Insert USB on target machine
   - Enter boot menu (F12, Esc, or Del)
   - Select USB drive

3. **First-Boot Setup**
   - Runs automatically on first boot
   - Configure timezone, username, network
   - JARVIS core initialization

4. **Ready for Use**
   - Voice interface online
   - Web dashboard: http://localhost:3000
   - API endpoint: http://localhost:8001

## System Components Summary

| Component | Files | Purpose |
|-----------|-------|---------|
| **Core** | backend/server.py | FastAPI with 19 OS endpoints |
| **Managers** | modules/services/*.py | Audio, Camera, Power, Network, Device, Service |
| **Voice Shell** | jarvis-shell | Primary interactive interface |
| **Systemd** | config/jarvis.service | Core system service |
| **Boot** | boot-init.sh | Post-boot initialization |
| **Setup** | first-boot-setup.sh | First-boot configuration |
| **Builder** | build-iso.sh | ISO creation automation |

## Configuration Files

- `config/live-build.conf` - Live-build configuration
- `config/packages.list` - Debian packages to include
- `config/jarvis.service` - Systemd unit file
- `.gitignore` - Build artifacts to ignore

## Directory Structure

```
os-distribution/
├── README.md                  # Distribution overview
├── ARCHITECTURE.md            # This file
├── build-iso.sh              # ISO builder script
├── boot-init.sh              # Boot initialization
├── first-boot-setup.sh       # First-boot wizard
├── jarvis-shell              # Voice shell interface
├── config/
│   ├── live-build.conf       # Live-build settings
│   ├── packages.list         # Debian packages
│   └── jarvis.service        # Systemd service
├── build/                    # Build area (generated)
└── output/                   # ISO output (generated)
```

## System Requirements

### Minimum (Recommended)
- **CPU**: 2+ cores (preferably with AES-NI for security)
- **RAM**: 4GB (2GB minimum for boot)
- **Disk**: 20GB SSD (for responsive voice processing)
- **Audio**: Microphone + speakers (USB device supported)
- **Network**: Ethernet or WiFi (configured at first boot)

### Build Machine
- Ubuntu 22.04 LTS or Debian bookworm
- 30GB free disk space (for ISO build)
- 4GB RAM minimum
- Internet connection (for package downloads)

## Performance Tuning

### Voice Processing
- PulseAudio configured for low-latency
- DSP filters for microphone enhancement
- Real-time priority for audio threads

### System Response
- JARVIS core runs with elevated priority
- Service manager pooling every 5 seconds
- Network state refresh aligned with telemetry

### Resource Usage
- Typical boot: 45-60 seconds
- Memory usage: 500MB-1.5GB idle
- CPU during voice processing: varies by model

## Security Considerations

- JARVIS service requires token authentication (X-JARVIS-TOKEN)
- Local filesystem access controlled by systemd ProtectSystem
- Audio/camera devices only accessible to JARVIS service user
- All operations logged to /var/log/jarvis

## Troubleshooting

### ISO Build Fails
```bash
# Check live-build installation
lb --version

# Clean and retry
rm -rf build/ && sudo ./build-iso.sh
```

### First-Boot Setup Hangs
- Check network connectivity
- Verify disk space (20GB minimum)
- Check /var/log/jarvis for errors

### Voice Shell Not Responding
- Verify JARVIS service running: `systemctl status jarvis`
- Check API connectivity: `curl http://localhost:8001/api/health`
- View service logs: `journalctl -u jarvis -f`

### Audio Not Working
- Check PulseAudio status: `pactl info`
- List devices: `pactl list short sources/sinks`
- Set default device: `pactl set-default-sink <name>`

## Next Phases

1. **Testing & Validation**
   - ISO boot testing
   - Hardware compatibility testing
   - Voice recognition accuracy

2. **Optimization**
   - Kernel boot time reduction
   - Memory footprint optimization
   - Voice latency improvement

3. **Distribution**
   - Official download mirrors
   - Checksums and signatures
   - Installation documentation

4. **Ecosystem**
   - Third-party app marketplace
   - Community extensions
   - Hardware certification program
