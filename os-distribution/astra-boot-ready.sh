#!/bin/bash
set -euo pipefail

required=(astra-control-broker.service jarvis.service)
for unit in "${required[@]}"; do
    if ! systemctl is-active --quiet "$unit"; then
        echo "ASTRA_BOOT_FAILED unit=$unit" >&2
        exit 1
    fi
done

marker="ASTRA_BOOT_READY broker=active backend=active"
echo "$marker"
if [ -w /dev/ttyS0 ]; then
    echo "$marker" > /dev/ttyS0
fi
