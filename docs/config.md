# scripts/config

`scripts/config` generates each config from the annotations. It runs a
kconfig target on each config. Then it writes the changed values back to
the annotations. The terms are defined in the [README](../README.md#terms).

```
scripts/config <command> [-p <package>] [-a <arch>] [-f <flavour>] [-C <kernel-tree>] [--force]
```

## Examples

```sh
# menuconfig for each config of linux. The script asks Y/n for each config.
scripts/config menu -p linux -C ~/code/kernel/linux/linux-7.3

# menuconfig for riscv64/rva20 only
scripts/config menu -p linux -a riscv64 -f rva20 -C ~/code/kernel/linux/linux-7.3

# After a kernel version bump: update each config of linux-lts
scripts/config sync -p linux-lts -C ~/code/kernel/linux/linux-6.18

# Write the full configs to build/configs/linux-lts/
scripts/config genconfigs -p linux-lts -C ~/code/kernel/linux/linux-6.18
```

## Commands

| Command | Short name | Use it to |
|---|---|---|
| `editconfigs` | `menu` | Change options with menuconfig. |
| `updateconfigs` | `sync` | Get new options after a kernel version bump. |
| `defaultconfigs` | | Give all new options their default value without questions. |
| `genconfigs` | | Write the full configs to `build/configs/<package>/config.<arch>-<flavour>`. It does not change the annotations. |

`menu` asks `Do you want to edit config: <arch>/<flavour>? [Y/n]` for each
config. `Y` runs menuconfig. `n` runs syncconfig, or olddefconfig if stdin
is not a terminal. menuconfig needs a terminal. If you give the answers on
stdin, answer only `n`. If an answer is missing, the script stops.

`sync` runs syncconfig. In a terminal, syncconfig asks about each new
option. Without a terminal, the script runs olddefconfig instead, and new
options get their default values.

`genconfigs` runs olddefconfig on each config. Its output can differ from
the raw `--export` output that `release.yml` and `scripts/mkrpm` use. To
see the config that CI uses, run `scripts/annotations --export`. See
[annotations.md](annotations.md#read).

## Options

| Option | Default | Description |
|---|---|---|
| `-p <package>` | `linux` | Package under `configs/` |
| `-a <arch>` | all arches | Process only the configs of this arch |
| `-f <flavour>` | all flavours | Process only the configs of this flavour |
| `-C <kernel-tree>` | `$KERNEL_DIR`, else `~/code/kernel/linux/ruyi-linux` | Kernel tree. Always give the worktree of the package. |
| `--force` | | Do not compare the tree version with `TAG_NAME` |

Without `-a` and `-f`, the script processes all configs in the order of the
`# FLAVOUR:` header. In this order, generic comes before rva20.

If the target arch is not the host arch, the script sets `CROSS_COMPILE` to
`<arch>-linux-gnu-`. You can set `CROSS_COMPILE` in the environment instead.

## Kernel tree

The script checks the tree that you give with `-C`:

- The `X.Y` version of the tree (`VERSION.PATCHLEVEL` in its `Makefile`)
  must be the same as the `X.Y` of the `TAG_NAME` in
  `configs/<package>/config.env`. `--force` turns off this check.
- The tree must not contain an in-tree build (`.config` or
  `include/config/`). The script builds out of tree in
  `build/kconfig-<package>-<arch>-<flavour>`.

To prepare the trees, see
[workflows.md](workflows.md#prepare-kernel-trees).

## How the script writes back

1. The script exports the config from the annotations. It keeps a copy as
   `.config.annotations`.
2. The script runs the kconfig target.
3. The script compares the result with `.config.annotations`. It writes each
   option with a different or new value to the annotations with
   `scripts/annotations --update`.
   - For a generic config, it writes the baseline (`'riscv64'`). The other
     flavours inherit the value.
   - For other flavours, it writes the flavour key (`'riscv64-rva20'`).
4. The script does not remove options that are no longer in the result. It
   does not write toolchain version options.
5. The script runs a config check for each config and shows `git diff --stat`.

The script uses `--update` with the changed options only. It does not use
`--import`, because `--import` can keep `'riscv64-generic'` keys. See
[annotations.md](annotations.md#known-pitfalls).

### Update of one non-generic flavour

`sync -f rva20` writes new options to `'riscv64-rva20'` only. The baseline
does not get them. The script shows a warning when this occurs. To correct
it, commit or stash your other changes to the annotations. Then run
`git checkout configs/<package>/annotations` and run `sync` without `-f`.

## Read the config check

```
Running config-check for all configurations ...
  x86_64/generic: all good
  riscv64/generic:
    CONFIG_ERRATA_PICOHEART_AMOCASQ changed from n to -: policy<{'riscv64': 'n', 'riscv64-rva20': 'y'}>)
    1 config options have been changed, review them with `git diff`
```

`riscv64/generic` is the config `riscv64-generic`. Each line
`changed from <expected> to <actual>` names an option whose value in the
final config is different from the annotations.

After a write-back, the remaining lines normally end with `to -`. The option
is not in the final config. These lines do not change the config. There are
two causes:

| Cause | What to do |
|---|---|
| A dependency of the option is not met. | If you wanted to enable this option, enable its dependencies too. |
| The kernel does not define the option any more. | See [workflows.md](workflows.md#clean-up-stale-annotations). |
