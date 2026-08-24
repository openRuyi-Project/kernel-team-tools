# kernel-team-tools

Tools for the openRuyi kernel team: kernel config management (annotations),
local RPM builds (rpm-build), and patchset release tracking (manifest).

## Repository layout

| Path | Contents |
|---|---|
| `annotations/` | The annotations config management tool (Python CLI) |
| `configs/linux/` | Annotations and `config.env` for the `linux` package (mainline tracking) |
| `configs/linux-lts/` | Annotations and `config.env` for the `linux-lts` package (LTS tracking) |
| `manifest` | `ruyi/v<version>-<n> <commit>` pairs mapping each patchset release to a kernel commit |
| `spec/` | Spec templates used by rpm-build: `linux.spec` (ruyi layout), `kernel.spec` (openEuler layout) |
| `rpm-build` | Script that builds RPM packages locally from a kernel source tree |

Both packages define three flavours (see the annotations file header):

```
# ARCH: x86_64 riscv64
# FLAVOUR: x86_64-generic riscv64-generic riscv64-rva20
```

## Kernel config management (annotations)

`annotations/annotations` manages per-arch/per-flavour kernel config policy.
Each option has one policy line (keyed by arch/flavour), optionally with a note:

```
CONFIG_ERRATA_THEAD_CMO          policy<{'riscv64': 'n', 'riscv64-rva20': 'y'}>
CONFIG_ERRATA_THEAD_CMO          note<'Errata for non-RVA23 machines'>
```

Policy key conventions:

- A bare arch key (e.g. `'riscv64'`) is the architecture baseline; it applies to
  every flavour that has no more specific key. **The generic flavour's value
  lives in the bare arch key** — do not write `riscv64-generic` (redundant keys
  are compacted away on save).
- An `<arch>-<flavour>` compound key (e.g. `'riscv64-rva20'`) overrides the
  baseline for that flavour. Lookup order: `<arch>-<flavour>` → bare `<arch>`.

Value semantics: `'y'`/`'m'` map to `CONFIG_X=y/m`, `'n'` to
`# CONFIG_X is not set`, and `'-'` leaves the option out of the generated
.config entirely.

All commands below need `-f` pointing at an annotations file (the repo has no
`debian/debian.env`, so autodetection does not work). Arch is `x86_64` or
`riscv64`.

### Export: generate a .config from annotations

```sh
./annotations/annotations -f configs/linux/annotations \
    --arch riscv64 --flavour generic --export > config.riscv64
./annotations/annotations -f configs/linux/annotations \
    --arch riscv64 --flavour rva20 --export > config.riscv64-rva20
```

`--flavour` defaults to `generic`. Add `--config CONFIG_X` to export a single
option.

### Import: merge a full .config into annotations

Use when you have a complete .config (e.g. from `make defconfig`) and want to
rewrite the policy for one arch/flavour wholesale. Both `--arch` and
`--flavour` are required:

```sh
./annotations/annotations -f configs/linux/annotations \
    --arch riscv64 --flavour generic --import /path/to/new.config
```

### Update: resync only the options present in a .config

Use after changing a handful of options to push the delta back into
annotations. Only the options present in FILE are touched; toolchain version
options (CONFIG_GCC_VERSION, CONFIG_CC_VERSION_TEXT, ...) are skipped
automatically:

```sh
# Resync every option that appears in partial.config
./annotations/annotations -f configs/linux/annotations \
    --arch riscv64 --flavour rva20 --update /path/to/partial.config

# Resync a single option
./annotations/annotations -f configs/linux/annotations \
    --arch riscv64 --update /path/to/partial.config --config CONFIG_FOO

# Set a value directly, no .config involved ('null' removes the policy
# for that arch/flavour)
./annotations/annotations -f configs/linux/annotations \
    --arch riscv64 --write y --config CONFIG_FOO
```

Note: if an updated option carries a note, the note is rewritten to
`TODO: update note` with a warning — review the `git diff` afterwards and
rewrite the note.

### Check and query

```sh
# Validate a .config against the annotations (exit code 1 on mismatch)
./annotations/annotations -f configs/linux/annotations \
    --arch riscv64 --flavour rva20 --check config.riscv64-rva20

# Query the value of a single option
./annotations/annotations -f configs/linux/annotations \
    --arch riscv64 --flavour rva20 --query --config CONFIG_ERRATA_THEAD_CMO
```

After editing, run `--export` followed by `--check` to confirm the round trip
is consistent, then review with `git diff`.

## Local RPM builds (rpm-build)

`rpm-build` builds the openRuyi linux RPM packages directly from a kernel
source directory (e.g. an openRuyi-Project/linux worktree checked out at
`ruyi/<version>.y`, patches already part of the tree): it generates the config
from the annotations, packs Source0/Source1, injects values into the
repository spec template and runs rpmbuild. Prerequisites: rpmbuild, gcc,
bison, flex, make, perl, python3, tar, xz, zstd, cpio (cross builds also need
a target-arch toolchain).

### Common usage

```sh
# riscv64 generic cross build (the default arch)
./rpm-build ~/code/kernel/linux/ruyi-linux

# rva20 flavour (non-RVA23 CPU errata are enabled only here)
./rpm-build --flavour rva20 ~/code/kernel/linux/ruyi-linux

# x86_64
./rpm-build --arch x86_64 ~/code/kernel/linux/ruyi-linux

# Use your own .config, bypassing annotations (mutually exclusive
# with --flavour)
./rpm-build --config my.config ~/code/kernel/linux/ruyi-linux

# LLVM/clang build (version suffix probed automatically, e.g. LLVM=-21;
# or set it explicitly with --llvm)
./rpm-build --toolchain clang ~/code/kernel/linux/ruyi-linux

# Print the rpmbuild invocation without building
./rpm-build --dry-run ~/code/kernel/linux/ruyi-linux
```

See `./rpm-build --help` for the full option list (cross prefix probing,
jobs, release suffix, iteration override, tools/devel subpackage toggles,
...).

### Versioning and the work directory

- The kernel release carries git information (following the kernel's own
  scripts/setlocalversion convention): N commits past the version tag yield a
  `-00199-g<sha>` suffix, uncommitted changes add `-dirty`, a non-git
  directory gets `+`. The RPM Release mirrors the same information in
  rpm-legal characters (e.g. `2.0.00199.g<sha>.3`) plus an auto-incrementing
  iteration number: identical inputs keep the same number, any change bumps
  it, `--iteration N` overrides it, and removing the work directory resets
  the counter.
- The work directory defaults to `./rpm-work`; packages land in `RPMS/` and
  `SRPMS/`. `--reuse` reuses the previous Source0 tarball and config (it
  refuses on provenance mismatch) — handy when only the sources changed.
- Cross builds (`--arch` different from the host) disable the tools/devel
  subpackages by default (they need a full target-arch userspace toolchain);
  native builds enable them. Override with `--with-tools`/`--with-devel`.
- `--distro oe` switches to the openEuler layout spec template
  (`spec/kernel.spec`: /boot layout, SUBLEVEL moved into Release); the
  default is the ruyi layout (`spec/linux.spec`).
- The cross-compile environment variables `ARCH`, `CROSS_COMPILE`,
  `RUST_TARGET` and `RUST_LIB_SRC` are recognised as defaults; command line
  options win.
