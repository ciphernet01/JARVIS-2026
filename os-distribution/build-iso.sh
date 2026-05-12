#!/bin/bash
# JARVIS OS ISO Builder
# Builds bootable Debian live-build ISO with JARVIS integrated

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
OUTPUT_DIR="$SCRIPT_DIR/output"
CONFIG_DIR="$SCRIPT_DIR/config"
JARVIS_HOME="$SCRIPT_DIR/.."

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

prepare_environment() {
    log_info "Preparing build environment..."
    
    # Clean previous builds
    if [ -d "$BUILD_DIR" ]; then
        log_info "Cleaning previous build..."
        rm -rf "$BUILD_DIR"
    fi
    
    # Create directories
    mkdir -p "$BUILD_DIR/config"
    mkdir -p "$OUTPUT_DIR"
    
    # Copy configuration
    cp "$CONFIG_DIR/live-build.conf" "$BUILD_DIR/config/"
    cp "$CONFIG_DIR/packages.list" "$BUILD_DIR/"
    
    # Copy JARVIS code
    cp -r "$JARVIS_HOME" "$BUILD_DIR/jarvis-code"
    
    log_success "Build environment prepared"
}

configure_live_build() {
    log_info "Configuring live-build..."
    
    cd "$BUILD_DIR"
    
    # Initialize live-build config
    lb config \
        --architectures amd64 \
        --binary-format iso-hybrid \
        --bootloader grub-efi \
        --archive-areas "main contrib non-free non-free-firmware" \
        --debian-installer live \
        --distribution bookworm \
        --firmware-binary true \
        --firmware-chroot true \
        --iso-application "JARVIS Neural OS" \
        --iso-volume "JARVIS_OS" \
        --linux-flavours generic \
        --security true
    
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
    log_info "Integrating JARVIS into image..."
    
    # Create hooks for post-build customization
    mkdir -p "$BUILD_DIR/config/hooks/normal"
    
    cat > "$BUILD_DIR/config/hooks/normal/2000-jarvis-install.hook.chroot" << 'HOOK'
#!/bin/bash
# Install JARVIS into image

set -e

JARVIS_INSTALL_DIR="/opt/jarvis"
mkdir -p "$JARVIS_INSTALL_DIR"

# Copy JARVIS code to image
if [ -d /tmp/jarvis-code ]; then
    cp -r /tmp/jarvis-code/* "$JARVIS_INSTALL_DIR/"
    log_success "JARVIS installed to $JARVIS_INSTALL_DIR"
fi

# Install systemd service
if [ -f "$JARVIS_INSTALL_DIR/os-distribution/config/jarvis.service" ]; then
    cp "$JARVIS_INSTALL_DIR/os-distribution/config/jarvis.service" /etc/systemd/system/
    systemctl daemon-reload
    systemctl enable jarvis.service
    echo "JARVIS service enabled"
fi

# Set up voice shell
if [ -f "$JARVIS_INSTALL_DIR/os-distribution/jarvis-shell" ]; then
    chmod +x "$JARVIS_INSTALL_DIR/os-distribution/jarvis-shell"
    ln -sf "$JARVIS_INSTALL_DIR/os-distribution/jarvis-shell" /usr/local/bin/jarvis-shell
    echo "Voice shell installed"
fi

# First-boot setup
if [ -f "$JARVIS_INSTALL_DIR/os-distribution/first-boot-setup.sh" ]; then
    chmod +x "$JARVIS_INSTALL_DIR/os-distribution/first-boot-setup.sh"
    ln -sf "$JARVIS_INSTALL_DIR/os-distribution/first-boot-setup.sh" /usr/local/bin/jarvis-first-boot
fi

echo "JARVIS integration complete"
HOOK
    
    chmod +x "$BUILD_DIR/config/hooks/normal/2000-jarvis-install.hook.chroot"
    
    log_success "JARVIS integration hooks added"
}

build_iso() {
    log_info "Building ISO image (this may take 10-30 minutes)..."
    
    cd "$BUILD_DIR"
    
    # Mount /proc and /sys for debootstrap
    sudo lb build 2>&1 | tee build.log
    
    if [ -f live-image-amd64.hybrid.iso ]; then
        mv live-image-amd64.hybrid.iso "$OUTPUT_DIR/jarvis-os-$(date +%Y%m%d).iso"
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
    echo "║    JARVIS OS ISO Builder                           ║"
    echo "║    Building Bootable Neural Operating System      ║"
    echo "╚════════════════════════════════════════════════════╝"
    echo -e "${NC}"
    echo ""
    
    # Run build steps
    check_requirements || exit 1
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
