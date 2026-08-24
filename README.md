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

