#!/usr/bin/env bash
set -euo pipefail

ISO_PATH="${1:-}"
TIMEOUT_SECONDS="${ASTRA_QEMU_TIMEOUT:-180}"

if [ -z "$ISO_PATH" ] || [ ! -f "$ISO_PATH" ]; then
    echo "Usage: $0 path/to/astra.iso" >&2
    exit 2
fi
if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
    echo "qemu-system-x86_64 is required" >&2
    exit 2
fi

LOG_FILE="${ASTRA_QEMU_LOG:-}"
REMOVE_LOG=0
if [ -z "$LOG_FILE" ]; then
    LOG_FILE="$(mktemp -t astra-qemu-boot.XXXXXX.log)"
    REMOVE_LOG=1
else
    mkdir -p "$(dirname "$LOG_FILE")"
    : > "$LOG_FILE"
fi
cleanup() {
    if [ "$REMOVE_LOG" = "1" ]; then
        rm -f "$LOG_FILE"
    fi
}
trap cleanup EXIT

ACCEL="tcg"
if [ -r /dev/kvm ] && [ -w /dev/kvm ]; then
    ACCEL="kvm"
fi

set +e
timeout "$TIMEOUT_SECONDS" qemu-system-x86_64 \
    -accel "$ACCEL" \
    -machine q35 \
    -m "${ASTRA_QEMU_MEMORY_MB:-4096}" \
    -smp "${ASTRA_QEMU_CPUS:-2}" \
    -cdrom "$ISO_PATH" \
    -boot d \
    -display none \
    -serial stdio \
    -no-reboot \
    2>&1 | tee "$LOG_FILE"
QEMU_STATUS=${PIPESTATUS[0]}
set -e

if python3 "$(dirname "$0")/check_boot_ready_log.py" "$LOG_FILE"; then
    echo "A.S.T.R.A QEMU boot smoke passed"
    exit 0
fi

echo "A.S.T.R.A QEMU boot smoke failed (qemu status: $QEMU_STATUS)" >&2
tail -80 "$LOG_FILE" >&2
exit 1
