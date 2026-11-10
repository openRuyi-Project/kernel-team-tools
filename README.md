# kernel-team-tools

This repository contains the tools and metadata of the openRuyi kernel team.
It keeps the config policy of the `linux` (mainline) and `linux-lts`
packages, the release metadata, and helper scripts.

## Documentation

| Task | Page |
|---|---|
| Learn the terms used in all pages | [Terms](#terms) below |
| Enable, disable or change config options | [workflows.md](docs/workflows.md#enable-or-change-options) |
| Update the configs after a kernel version bump | [workflows.md](docs/workflows.md#kernel-version-bump) |
| Release new patchset tags and a GitHub release | [workflows.md](docs/workflows.md#release) |
| Build an RPM locally | [workflows.md](docs/workflows.md#build-an-rpm-locally), [mkrpm.md](docs/mkrpm.md) |
| Remove stale entries from the annotations | [workflows.md](docs/workflows.md#clean-up-stale-annotations) |
| Understand the annotations format and tool | [annotations.md](docs/annotations.md) |
| Look up `scripts/config` details | [config.md](docs/config.md) |
| Look up release and CI details | [release.md](docs/release.md) |

## Terms

| Term | Meaning |
|---|---|
| option | One Kconfig symbol, for example `CONFIG_DRM_POWERVR`. |
| package | `linux` or `linux-lts`. Each package has its own directory under `configs/`. |
| arch | `riscv64` or `x86_64`. |
| flavour | A variant of an arch: `generic` or `rva20`. |
| config | The full `.config` that the scripts generate for one arch and one flavour. Each package has three configs. |
| config name | `<arch>-<flavour>` (`riscv64-rva20`) in the annotations header and in file names. `<arch>/<flavour>` (`riscv64/rva20`) in the output of `scripts/config`. |
| generic, rva20 | `riscv64-generic` is for RVA23 machines. `riscv64-rva20` is for older machines and also enables the errata for non-RVA23 CPUs. `x86_64` has only `generic`. |
| config check | The comparison of a final config with the annotations (`scripts/annotations --check`). `scripts/config` runs it at the end. |
| annotations | The file `configs/<package>/annotations`. It gives the value of each option for each arch and flavour. See [annotations.md](docs/annotations.md). |
| key | The name in a policy that a value belongs to. The arch key (`'riscv64'`) holds the baseline. A flavour key (`'riscv64-rva20'`) holds a value for one flavour. |
| baseline | The value of an option in the arch key. The generic flavour uses the baseline. Other flavours use the baseline unless they have a flavour key. |
| arch-independent option | An option that is not specific to one arch. It normally has the same value on riscv64 and x86_64. |
| patchset tag | A tag `ruyi/v<version>-<n>` in openRuyi-Project/linux, for example `ruyi/v6.18.63-1`. CI creates it from `metadata/manifest`. |
| `TAG_NAME` | The value in `configs/<package>/config.env` that selects the patchset tag of the package, without the `ruyi/` prefix (`v6.18.63-1`). |
| maintained branch | A `ruyi/X.Y.y` branch of openRuyi-Project/linux that gets new patchset tags. `metadata/maintained-branches` lists them. |
| kernel tree | A checkout of openRuyi-Project/linux. Use one git worktree for each package. |
| date tag | A tag `YYYY.MM.DD.HH.MM` in this repository. A push of a date tag publishes the GitHub releases. |

## Repository layout

| Path | Contents |
|---|---|
| `configs/<package>/annotations` | Option values per arch and flavour |
| `configs/<package>/config.env` | `TAG_NAME` of the package |
| `metadata/manifest` | Patchset tags and their commits |
| `metadata/maintained-branches` | `ruyi/X.Y.y` branches that get new patchset tags |
| `scripts/config` | Runs syncconfig or menuconfig on the configs and writes the result back to the annotations |
| `scripts/annotations`, `scripts/kconfig/` | The annotations tool, copied from Ubuntu. Do not change these files. |
| `scripts/manifest-update` | Adds the next patchset tags to `metadata/manifest` |
| `scripts/mkrpm` | Builds the linux RPM packages from a kernel tree |
| `spec/` | Spec templates for `scripts/mkrpm` |
| `patch-db/`, `patchoulene/` | Patch database and its tool `patl`. See [patchoulene/README.md](patchoulene/README.md). |
| `.github/workflows/` | `manifest.yml` creates the patchset tags. `release.yml` publishes the GitHub releases. |
| `build/` | Build output. Git ignores it. |

## Quick reference

The commands use one kernel worktree for each package. See
[Prepare kernel trees](docs/workflows.md#prepare-kernel-trees).

```sh
# Change options with menuconfig and write them back
scripts/config menu -p linux -C ~/code/kernel/linux/linux-7.3

# Get new options after a kernel version bump
scripts/config sync -p linux-lts -C ~/code/kernel/linux/linux-6.18

# Show the next patchset tags. Check them before you commit them with -a.
scripts/manifest-update

# Build an RPM locally
scripts/mkrpm -p linux-lts ~/code/kernel/linux/linux-6.18
```

Do not push `metadata/manifest` before you read
[Release](docs/workflows.md#release). Pushed lines become public tags.
