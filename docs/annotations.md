# Annotations

The annotations file `configs/<package>/annotations` gives the value of each
option for each arch and flavour. The file format and the tool come from
Ubuntu's kernel packaging. The terms are defined in the
[README](../README.md#terms).

> Do not change `scripts/annotations` or `scripts/kconfig/`. They are copied
> from Ubuntu, and they must stay replaceable by a newer Ubuntu version.

For normal work, use [`scripts/config`](config.md). It runs the tool for
you. This page describes the format and the direct tool commands.

## Format

The header lists the arches and the configs:

```
# ARCH: x86_64 riscv64
# FLAVOUR: x86_64-generic riscv64-generic riscv64-rva20
```

The `# FLAVOUR:` line contains config names (`<arch>-<flavour>`).

Each option has one `policy` line. It can also have one `note` line:

```
CONFIG_ERRATA_THEAD_CMO                         policy<{'riscv64': 'n', 'riscv64-rva20': 'y'}>
CONFIG_ERRATA_THEAD_CMO                         note<'Errata for non-RVA23 machines'>
```

## Keys

A policy maps keys to values. There are two types of keys:

| Key | Example | Use |
|---|---|---|
| Arch key | `'riscv64'` | The baseline of the arch. The generic flavour uses it. |
| Flavour key | `'riscv64-rva20'` | A value for one flavour only. It replaces the baseline for that flavour. |

The tool finds a value in this order: first `<arch>-<flavour>`, then
`<arch>`.

Rules:

- Write the value of the generic flavour in the arch key. Do not write
  `'riscv64-generic'`.
- Give arch-independent options the same value on riscv64 and x86_64. Use a
  different value only for a riscv64-specific reason.

## Values

| Value | Line in the config |
|---|---|
| `'y'`, `'m'` | `CONFIG_X=y`, `CONFIG_X=m` |
| `'n'` | `# CONFIG_X is not set` |
| other string, for example `'512'` or `'"text"'` | `CONFIG_X=512`, `CONFIG_X="text"` |
| `'-'` | No line. The option is not in the config. |
| no key for the arch | No line, the same as `'-'`. |

## rva20-only options

`riscv64-generic` is for RVA23 machines. Errata for non-RVA23 CPUs are
enabled only in the flavour key `'riscv64-rva20'`. Give each such entry a
note that tells why:

```
CONFIG_ERRATA_SIFIVE_H_0_6_1                    policy<{'riscv64': 'n', 'riscv64-rva20': 'y'}>
CONFIG_ERRATA_SIFIVE_H_0_6_1                    note<'P550 implements H-extension draft 0.6.1 - non-RVA23'>
```

Keep these entries in the first block of the file, directly after the
header. The other options follow in alphabetical order.

## Commands

Give the annotations file with `-f`. The examples use this shell variable:

```sh
A="scripts/annotations -f configs/linux/annotations"
```

### Read

These commands do not change the file. `--flavour` is optional and its
default is `generic`.

```sh
mkdir -p build

# Generate a full config
$A --arch riscv64 --flavour rva20 --export > build/config.riscv64-rva20

# Show the value of one option
$A --arch riscv64 --flavour rva20 --query --config CONFIG_ERRATA_THEAD_CMO

# Compare a config with the annotations (exit code 1 if they differ)
$A --arch riscv64 --flavour rva20 --check build/config.riscv64-rva20
```

### Write

To change the generic flavour, do not give `--flavour`. See
[Known pitfalls](#known-pitfalls).

```sh
# Set the baseline of one arch
$A --arch riscv64 --write m --config CONFIG_FOO

# Set a value for one flavour only
$A --arch riscv64 --flavour rva20 --write y --config CONFIG_FOO

# Remove the value of one arch (or of one flavour, with --flavour)
$A --arch x86_64 --write null --config CONFIG_FOO

# Write back the options that a (partial) config contains
$A --arch riscv64 --update changes.config
```

### Known pitfalls

| Pitfall | Result | What to do |
|---|---|---|
| `--write` without `--arch` | The tool writes the same value for every arch. | Always give `--arch`. |
| `--write null` for a key that does not exist | The tool stops with `KeyError`. The file does not change. | Use `--query` first. Remove a flavour key with `--flavour`. |
| `--update` or `--write` with `--flavour generic` | If the value differs from the other flavours, the tool keeps a `'riscv64-generic'` key. rva20 does not inherit that value. | Leave out `--flavour` for generic. If the key is already there, save your other changes to the file, run `git checkout` on the file and do the change again. |
| `--import` | It replaces all values of one config and needs `--flavour`. For generic, it can keep a `'riscv64-generic'` key. | Use `scripts/config` or `--update`. |
| Toolchain version options (`CONFIG_CC_VERSION_TEXT`, ...) | `--update` and `scripts/config` skip them. `--write` and `--import` write them. | Do not set them by hand. |
| Option with a note | `--update` can change the note to `TODO: update note`. | Write the note again before you commit. |

You can also edit the file in a text editor. Keep the column alignment:
`policy<` and `note<` start in column 49. After the edit, run
`$A --arch riscv64 --export > /dev/null` and `$A --arch x86_64 --export > /dev/null`.
Both commands must exit with 0. If not, the error message names the line
to correct.
