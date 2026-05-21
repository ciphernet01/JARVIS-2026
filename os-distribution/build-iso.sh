#!/bin/bash
# A.S.T.R.A OS ISO Builder
# Builds bootable Debian live-build ISO with A.S.T.R.A integrated.

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="${ASTRA_BUILD_DIR:-$SCRIPT_DIR/build}"
OUTPUT_DIR="${ASTRA_OUTPUT_DIR:-$SCRIPT_DIR/output}"
CONFIG_DIR="$SCRIPT_DIR/config"
JARVIS_HOME="$SCRIPT_DIR/.."
FRONTEND_BUILD_DIR="${ASTRA_FRONTEND_BUILD_DIR:-${TMPDIR:-/tmp}/astra-frontend-build}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

check_requirements() {
    log_info "Checking build requirements..."
    
    local missing=0
    
    for cmd in live-build lb debootstrap; do
        if ! command -v "$cmd" &> /dev/null; then
            log_error "$cmd not found"
            missing=$((missing + 1))
        fi
    done
    
    if [ $missing -gt 0 ]; then
        log_error "Missing $missing required tools"
        echo "Install with: sudo apt-get install live-build debootstrap"
        return 1
    fi
    
    log_success "All requirements met"
    return 0
}

build_frontend_assets() {
    log_info "Building frontend production assets..."

    if ! command -v npm &> /dev/null; then
        log_error "npm not found; install Node.js/npm before building the final ISO"
        return 1
    fi

    if [ ! -f "$JARVIS_HOME/frontend/package-lock.json" ]; then
        log_error "frontend/package-lock.json not found"
        return 1
    fi

    mkdir -p "$OUTPUT_DIR"
    pushd "$JARVIS_HOME/frontend" > /dev/null
    if [ -d node_modules ] && [ ! -w node_modules ]; then
        log_info "frontend/node_modules is not writable; using existing dependencies"
    else
        npm ci
    fi
    rm -rf "$FRONTEND_BUILD_DIR"
    DISABLE_ESLINT_PLUGIN=true BUILD_PATH="$FRONTEND_BUILD_DIR" REACT_APP_BACKEND_URL="http://localhost:8001" npm run build
    popd > /dev/null

    if [ ! -f "$FRONTEND_BUILD_DIR/index.html" ]; then
        log_error "Frontend build did not produce $FRONTEND_BUILD_DIR/index.html"
        return 1
    fi

    log_success "Frontend assets built"
    return 0
}

preflight_payload() {
    log_info "Running ISO payload preflight checks..."

    local payload="$BUILD_DIR/config/includes.chroot/opt/jarvis"
    local blocked=0

    for required in \
        "$payload/backend/server.py" \
        "$payload/frontend/build/index.html" \
        "$payload/os-distribution/jarvis-shell-session.sh" \
        "$payload/os-distribution/config/jarvis.service"; do
        if [ ! -f "$required" ]; then
            log_error "Missing required payload file: ${required#$payload/}"
            blocked=$((blocked + 1))
        fi
    done

    for forbidden in \
        "$payload/.git" \
        "$payload/.venv" \
        "$payload/.env" \
        "$payload/.session_token" \
        "$payload/frontend/node_modules" \
        "$payload/desktop-overlay/node_modules" \
        "$payload/memory" \
        "$payload/backups" \
        "$payload/test_reports" \
        "$payload/jarvis.db"; do
        if [ -e "$forbidden" ]; then
            log_error "Forbidden payload artifact included: ${forbidden#$payload/}"
            blocked=$((blocked + 1))
        fi
    done

    if [ $blocked -gt 0 ]; then
        log_error "Payload preflight failed with $blocked issue(s)"
        return 1
    fi

    log_success "Payload preflight passed"
    return 0
}

prepare_environment() {
    log_info "Preparing build environment..."

    if [ -e "$BUILD_DIR" ] && [ ! -w "$BUILD_DIR" ]; then
        log_error "Build directory is not writable: $BUILD_DIR"
        echo "Use sudo, remove the stale build directory, or set ASTRA_BUILD_DIR to a writable path."
        return 1
    fi

    if [ -e "$OUTPUT_DIR" ] && [ ! -w "$OUTPUT_DIR" ]; then
        log_error "Output directory is not writable: $OUTPUT_DIR"
        echo "Use sudo, fix ownership, or set ASTRA_OUTPUT_DIR to a writable path."
        return 1
    fi
    
    # Clean previous builds
    if [ -d "$BUILD_DIR" ]; then
        log_info "Cleaning previous build..."
        rm -rf "$BUILD_DIR" || return 1
    fi
    
    # Create directories
    mkdir -p "$BUILD_DIR/config"
    mkdir -p "$BUILD_DIR/config/package-lists"
    mkdir -p "$BUILD_DIR/config/includes.chroot/opt/jarvis"
    mkdir -p "$OUTPUT_DIR"
    
    # Copy configuration
    cp "$CONFIG_DIR/live-build.conf" "$BUILD_DIR/config/"
    cp "$CONFIG_DIR/packages.list" "$BUILD_DIR/"
    
    # Copy JARVIS code directly into the live filesystem payload.
    tar -C "$JARVIS_HOME" \
        --exclude ".git" \
        --exclude ".pytest_cache" \
        --exclude ".tmp" \
        --exclude ".testtmp" \
        --exclude ".venv" \
        --exclude ".env" \
        --exclude ".env.*" \
        --exclude ".session_token" \
        --exclude "__pycache__" \
        --exclude "*.pyc" \
        --exclude "*.log" \
        --exclude "*.db" \
        --exclude "backups" \
        --exclude "captures" \
        --exclude "frontend/build" \
        --exclude "frontend/node_modules" \
        --exclude "desktop-overlay/node_modules" \
        --exclude "memory" \
        --exclude "os-distribution/build" \
        --exclude "os-distribution/output" \
        --exclude "test_reports" \
        -cf - . | tar -C "$BUILD_DIR/config/includes.chroot/opt/jarvis" -xf -

    rm -rf "$BUILD_DIR/config/includes.chroot/opt/jarvis/frontend/build"
    mkdir -p "$BUILD_DIR/config/includes.chroot/opt/jarvis/frontend/build"
    cp -a "$FRONTEND_BUILD_DIR/." "$BUILD_DIR/config/includes.chroot/opt/jarvis/frontend/build/"

    preflight_payload || return 1
    
    log_success "Build environment prepared"
}

configure_live_build() {
    log_info "Configuring live-build..."
    
    cd "$BUILD_DIR"
    
    # Initialize live-build config
    lb config \
        --ignore-system-defaults \
        --mode debian \
        --architectures amd64 \
        --binary-images iso-hybrid \
        --bootloader grub-efi \
        --archive-areas "main contrib non-free non-free-firmware" \
        --debian-installer live \
        --distribution bookworm \
        --keyring-packages "debian-archive-keyring" \
        --mirror-bootstrap "https://deb.debian.org/debian" \
        --mirror-chroot "https://deb.debian.org/debian" \
        --mirror-binary "https://deb.debian.org/debian" \
        --mirror-chroot-security "https://security.debian.org/debian-security" \
        --mirror-binary-security "https://security.debian.org/debian-security" \
        --firmware-binary true \
        --firmware-chroot true \
        --iso-application "A.S.T.R.A OS" \
        --iso-volume "ASTRA_OS" \
        --linux-flavours generic \
        --security false
    
    log_success "Live-build configured"
}

add_packages() {
    log_info "Adding packages to build..."
    
    cd "$BUILD_DIR"
    
    # Read and add packages
    cat packages.list | while read -r package; do
        [ -z "$package" ] && continue
        [ "${package:0:1}" = "#" ] && continue
        echo "$package" >> config/package-lists/live.list.chroot
    done
    
    log_success "Packages added to build list"
}

add_jarvis_integration() {
    log_info "Integrating A.S.T.R.A into image..."
    
    # Create hooks for post-build customization
    mkdir -p "$BUILD_DIR/config/hooks/normal"
    
    cat > "$BUILD_DIR/config/hooks/normal/2000-jarvis-install.hook.chroot" << 'HOOK'
#!/bin/bash
# Install A.S.T.R.A into image

set -e

JARVIS_INSTALL_DIR="/opt/jarvis"
mkdir -p "$JARVIS_INSTALL_DIR"

echo "A.S.T.R.A payload staged at $JARVIS_INSTALL_DIR"

# Install systemd service
if [ -f "$JARVIS_INSTALL_DIR/os-distribution/config/jarvis.service" ]; then
    cp "$JARVIS_INSTALL_DIR/os-distribution/config/jarvis.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable jarvis.service
    echo "A.S.T.R.A service enabled"
fi

# Set up voice shell
if [ -f "$JARVIS_INSTALL_DIR/os-distribution/jarvis-shell" ]; then
    chmod +x "$JARVIS_INSTALL_DIR/os-distribution/jarvis-shell"
    ln -sf "$JARVIS_INSTALL_DIR/os-distribution/jarvis-shell" /usr/local/bin/jarvis-shell
    echo "Voice shell installed"
fi

if [ -f "$JARVIS_INSTALL_DIR/os-distribution/jarvis-shell-session.sh" ]; then
    chmod +x "$JARVIS_INSTALL_DIR/os-distribution/jarvis-shell-session.sh"
    ln -sf "$JARVIS_INSTALL_DIR/os-distribution/jarvis-shell-session.sh" /usr/local/bin/jarvis-shell-session
    echo "Graphical shell session installed"
fi

# First-boot setup
if [ -f "$JARVIS_INSTALL_DIR/os-distribution/first-boot-setup.sh" ]; then
    chmod +x "$JARVIS_INSTALL_DIR/os-distribution/first-boot-setup.sh"
    ln -sf "$JARVIS_INSTALL_DIR/os-distribution/first-boot-setup.sh" /usr/local/bin/jarvis-first-boot
fi

echo "A.S.T.R.A integration complete"
HOOK
    
    chmod +x "$BUILD_DIR/config/hooks/normal/2000-jarvis-install.hook.chroot"
    
    log_success "A.S.T.R.A integration hooks added"
}

build_iso() {
    log_info "Building ISO image (this may take 10-30 minutes)..."
    
    cd "$BUILD_DIR"
    
    # Mount /proc and /sys for debootstrap
    sudo lb build 2>&1 | tee build.log
    
    if [ -f live-image-amd64.hybrid.iso ]; then
        mv live-image-amd64.hybrid.iso "$OUTPUT_DIR/astra-os-$(date +%Y%m%d).iso"
        log_success "ISO image created"
        return 0
    else
        log_error "ISO build failed"
        return 1
    fi
}

create_checksums() {
    log_info "Creating checksums..."
    
    cd "$OUTPUT_DIR"
    
    for iso in *.iso; do
        sha256sum "$iso" > "$iso.sha256"
        md5sum "$iso" > "$iso.md5"
    done
    
    log_success "Checksums created"
}

main() {
    echo -e "${BLUE}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║    A.S.T.R.A OS ISO Builder                        ║"
    echo "║    Agentic Spatial Task Reasoning Architecture     ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    
    # Run build steps
    check_requirements || exit 1
    build_frontend_assets || exit 1
    prepare_environment || exit 1
    configure_live_build || exit 1
    add_packages || exit 1
    add_jarvis_integration || exit 1
    
    echo -e "\n${YELLOW}Ready to build ISO${NC}"
    echo "This requires root/sudo and will take 10-30 minutes"
    echo ""
    echo "Continue (y/n)?"
    read -r CONTINUE
    
    if [[ "$CONTINUE" != "y" && "$CONTINUE" != "Y" ]]; then
        log_info "Build cancelled"
        exit 0
    fi
    
    build_iso || exit 1
    create_checksums
    
    echo ""
    echo -e "${GREEN}"
    echo "╔════════════════════════════════════════════════════╗"
    echo "║    Build Complete! ✓                              ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    
    echo ""
    echo "ISO images available in: $OUTPUT_DIR"
    ls -lh "$OUTPUT_DIR"/*.iso
    
    echo ""
    echo "Next steps:"
    echo "1. Write to USB: sudo dd if=*.iso of=/dev/sdX bs=4M"
    echo "2. Boot from USB on target machine"
    echo "3. Follow first-boot setup wizard"
}

main "$@"
