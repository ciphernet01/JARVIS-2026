# A.S.T.R.A ISO Build Host

Use a clean Debian 12 (bookworm) amd64 host or disposable VM. The first
reproducible-build target is Debian 12; other distributions are not release
builders until separately validated.

The canonical automated implementation is `.github/workflows/astra-iso.yml`,
which runs these steps inside a privileged Debian 12 container.

## Required host packages

```bash
sudo apt-get update
sudo apt-get install --yes \
  live-build \
  debootstrap \
  grub-efi-amd64-bin \
  grub-pc-bin \
  mtools \
  dosfstools \
  xorriso \
  squashfs-tools \
  qemu-system-x86 \
  ovmf \
  python3 \
  python3-pip \
  nodejs \
  npm
```

Record exact package versions in CI with:

```bash
dpkg-query -W -f='${Package}\t${Version}\n' > build-host-packages.tsv
```

## Validation and build

```bash
./os-distribution/build-iso.sh --validate-only
ASTRA_NONINTERACTIVE=1 ./os-distribution/build-iso.sh --non-interactive
./scripts/qemu_boot_smoke.sh os-distribution/output/astra-os-YYYYMMDD.iso
```

The build produces the ISO, a `.sha256` file, and a
`.iso.provenance.json` record. CI must retain all three plus
`build-host-packages.tsv`.

The build resolves `requirements.runtime.txt` into Linux/Python 3.11 wheels,
hashes every artifact, and installs the runtime with `--no-index` inside the
image. First boot performs no network dependency installation. The build still
uses live Debian repositories and npm, so byte-for-byte
reproducibility is not yet guaranteed. Pinning repository snapshots remains
required before a production release.
