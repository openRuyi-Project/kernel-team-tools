# Workflows

This page gives the steps for the common tasks. Run the commands from the
root of this repository unless a step says otherwise. The terms are defined
in the [README](../README.md#terms).

- [Prepare kernel trees](#prepare-kernel-trees)
- [Enable or change options](#enable-or-change-options)
- [Kernel version bump](#kernel-version-bump)
- [Release](#release)
- [Build an RPM locally](#build-an-rpm-locally)
- [Clean up stale annotations](#clean-up-stale-annotations)
- [Commit conventions](#commit-conventions)

## Prepare kernel trees

Make one worktree for each package. The `X.Y` version of the worktree must
be the same as the `X.Y` of the `TAG_NAME` of the package. Do not build
inside these worktrees. `scripts/config` stops if it finds an in-tree
`.config`. `scripts/config` and `scripts/mkrpm` build out of tree.

1. Go to your main clone of openRuyi-Project/linux and fetch. In these
   examples, the remote of openRuyi-Project/linux is `ruyi`. The
   remote-tracking branch of `ruyi/7.3.y` is therefore `ruyi/ruyi/7.3.y`.

   ```sh
   cd ~/code/kernel/linux/ruyi-linux
   git fetch ruyi
   ```
2. Add one worktree for each package. `linux` uses the 7.3 branch and
   `linux-lts` uses the 6.18 branch:

   ```sh
   git worktree add ~/code/kernel/linux/linux-7.3  ruyi/ruyi/7.3.y
   git worktree add ~/code/kernel/linux/linux-6.18 ruyi/ruyi/6.18.y
   ```
3. Optional: fetch the upstream version tags. `scripts/mkrpm` needs them
   for the commit count in the version string. See
   [mkrpm.md](mkrpm.md#versions). For example, with a remote `stable` for
   the stable tree:

   ```sh
   git fetch stable tag v6.18.63
   ```

To update a worktree later:

1. Run `git -C ~/code/kernel/linux/ruyi-linux fetch ruyi`.
2. Run `git -C ~/code/kernel/linux/linux-7.3 checkout --detach ruyi/ruyi/7.3.y`.

## Enable or change options

1. Run menuconfig for the package:

   ```sh
   scripts/config menu -p linux -C ~/code/kernel/linux/linux-7.3
   ```

   The script asks about each config. Answer `Y` for each config that you
   want to edit. The script opens menuconfig for it. Answer `n` for the
   other configs. For them, the script runs syncconfig and does not open
   menuconfig. Their annotations can still change. To edit only one config,
   add `-a <arch>` and `-f <flavour>`, for example `-a riscv64 -f rva20`.
2. Read the result with `git diff configs/`. The values that you set in
   `riscv64/generic` go to the baseline (`'riscv64'`), and rva20 inherits
   them. The values that you set in `riscv64/rva20` go to the flavour key
   `'riscv64-rva20'`. See [annotations.md](annotations.md#keys).
3. If the change also applies to the other package, repeat steps 1 and 2
   with `-p linux-lts -C ~/code/kernel/linux/linux-6.18`.
4. Commit. See [Commit conventions](#commit-conventions).

If you know the exact options and values, you can also set them with the
annotations tool. See [annotations.md](annotations.md#commands).

Set errata for non-RVA23 CPUs only in the flavour key `'riscv64-rva20'`, and
add a note. See [annotations.md](annotations.md#rva20-only-options).

## Kernel version bump

### New stable version of a maintained branch

Use this procedure when a branch moves to a new upstream version, for
example from 6.18.62 to 6.18.63.

1. Update the worktree of the branch. See
   [Prepare kernel trees](#prepare-kernel-trees).
2. Update all configs of the package:

   ```sh
   scripts/config sync -p linux-lts -C ~/code/kernel/linux/linux-6.18
   ```

   In a terminal, the script asks about each new option. Without a
   terminal, new options get their Kconfig defaults.
3. Read `git diff`. If a new option needs a value other than the default,
   change it with `scripts/config menu` or the annotations tool. Give
   arch-independent options the same value on riscv64 and x86_64. If you are
   not sure, compare with the same option in the other package.
4. Commit, for example `configs: linux-lts: syncconfig for v6.18.63`.

### New X.Y version of linux

Use this procedure when `linux` moves to a new `X.Y` version, for example
from 7.3 to 7.4. `scripts/config` refuses a 7.4 tree while the `TAG_NAME` of
`linux` is 7.3. The steps therefore change `TAG_NAME` locally before the
sync, and push everything together.

1. Fetch and add a worktree for the new branch:

   ```sh
   git -C ~/code/kernel/linux/ruyi-linux fetch ruyi
   git -C ~/code/kernel/linux/ruyi-linux worktree add ~/code/kernel/linux/linux-7.4 ruyi/ruyi/7.4.y
   ```
2. Add `ruyi/7.4.y` to `metadata/maintained-branches`. Remove a branch only
   after the team agrees to stop its maintenance. Commit the change.
3. Do steps 1 to 4 of [Release](#release). Do not push yet. The local
   `TAG_NAME` of `linux` is now 7.4.
4. Update all configs of `linux` with the new tree:

   ```sh
   scripts/config sync -p linux -C ~/code/kernel/linux/linux-7.4
   ```
5. Read `git diff` and commit, for example `configs: linux: syncconfig for v7.4`.
6. Do steps 5 to 7 of [Release](#release). In step 5, the commits of steps
   2 and 5 above are also expected.

## Release

A release has two parts. First, CI creates the patchset tags in
openRuyi-Project/linux. Then you publish the GitHub releases of this
repository. You cannot take back pushed manifest lines or published
releases. Steps 6 and 7 are the irreversible steps. See
[release.md](release.md) for the details.

1. Make sure that the maintained branches are pushed in
   openRuyi-Project/linux.
2. Show the next patchset tags:

   ```sh
   scripts/manifest-update
   ```

   If the script prints a warning, do not continue. Fix the cause first.
   See [release.md](release.md#scriptsmanifest-update).
3. Add the lines to the manifest and commit them:

   ```sh
   scripts/manifest-update -a
   ```
4. For each package, set `TAG_NAME` to its new tag without the `ruyi/`
   prefix. Make one commit per package. Replace `<new-tag>` with the tag
   from step 2, for example `v7.3.4-1`:

   ```sh
   sed -i 's/^TAG_NAME=.*/TAG_NAME=<new-tag>/' configs/linux/config.env
   git commit -s -m "configs: linux: env: bump TAG_NAME to <new-tag>" configs/linux/config.env
   ```
5. Check the commits with `git log origin/master..`. Make sure that:
   - there is one manifest commit, and its tags are the tags from step 2,
   - each package has one `TAG_NAME` commit with its new tag,
   - there are no unrelated commits.

   Before the push, you can still fix a commit with `git commit --amend` or
   `git reset`.
6. Push to master. This step is irreversible: each manifest line becomes a
   public tag. Open the Actions page of this repository and wait until the
   `manifest.yml` run is successful. If it fails, see
   [release.md](release.md#auto-tagging).

   The same push also starts `release.yml`. That run can fail because the
   new patchset tags do not exist yet. This failure is expected and
   publishes nothing. Only the result of `manifest.yml` is important here.
7. Publish the GitHub releases. This step is irreversible. Do it once, after
   step 6 is successful. The command tags the pushed `origin/master`:

   ```sh
   git fetch origin
   t=$(date +%Y.%m.%d.%H.%M); git tag "$t" origin/master && git push origin "$t"
   ```

   When `release.yml` is successful, the Releases page shows one new
   release for each package, for example `v7.3.4-1.0`. If it fails, see
   [release.md](release.md#github-releases).

## Build an RPM locally

1. Prepare a kernel tree. See [Prepare kernel trees](#prepare-kernel-trees).
2. Build. Always give the package with `-p`:

   ```sh
   scripts/mkrpm -p linux-lts ~/code/kernel/linux/linux-6.18
   ```
3. Find the packages in `build/<package>-<arch>-<flavour>/RPMS/`.

See [mkrpm.md](mkrpm.md) for the arch, flavour and toolchain options.

## Clean up stale annotations

Over time, the annotations get entries that have no effect. An option can
be removed from the kernel. An option can also be impossible to enable on
one arch. These entries do not change the configs. They show up as
`changed from <value> to -` in the config check of `scripts/config`. See
[config.md](config.md#read-the-config-check).

1. Generate the configs before the change and keep a copy:

   ```sh
   scripts/config genconfigs -p linux -C ~/code/kernel/linux/linux-7.3
   rm -rf /tmp/configs-before && cp -r build/configs/linux /tmp/configs-before
   ```
2. Show the config check:

   ```sh
   scripts/config sync -p linux -C ~/code/kernel/linux/linux-7.3
   ```
3. For each option that shows `to -`, decide:

   | Case | Action |
   |---|---|
   | No Kconfig file defines the option. `git -C ~/code/kernel/linux/linux-7.3 grep -n -E '^\s*(menu)?config X$' -- '*Kconfig*'` shows nothing. | Delete all lines of the option from the annotations. |
   | The option shows `to -` in every config of one arch. | Remove all keys of that arch: the arch key (`--arch <arch> --write null --config CONFIG_X`) and each flavour key (add `--flavour <flavour>`). |
   | The option shows `to -` only in some configs of an arch. | Keep it. Another flavour uses it. |
4. Generate the configs again and compare:

   ```sh
   scripts/config genconfigs -p linux -C ~/code/kernel/linux/linux-7.3
   diff -r /tmp/configs-before build/configs/linux
   ```

   The diff must be empty. If it is not empty, a removed entry still had an
   effect. Restore that entry and do step 3 again.
5. Commit, for example `configs: linux: drop stale options`.

## Commit conventions

| Change | Subject |
|---|---|
| Option values | `configs: <package>: <what> for <board or feature>` |
| Kernel version bump | `configs: <package>: syncconfig for v<version>` |
| `TAG_NAME` | `configs: <package>: env: bump TAG_NAME to <new-tag>` |
| Manifest | `manifest: add <v1>/<v2>/... tag`, for example `manifest: add 7.3.4-1/6.18.63-1 tag`. `scripts/manifest-update -a` writes it. |
| Scripts, metadata, docs | `scripts: ...`, `metadata: ...`, `docs: ...` |

Make one commit per package. Split option changes by board or feature.
Always sign off with `git commit -s`. Keep the body short.
