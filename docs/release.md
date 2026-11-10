# Releases

This page describes the release data and the CI workflows. For the steps,
see [workflows.md](workflows.md#release). The terms are defined in the
[README](../README.md#terms).

## Overview

| Phase | Steps in [workflows.md](workflows.md#release) | Who | Result |
|---|---|---|---|
| Commit the manifest lines and the `TAG_NAME` changes | 1 to 5 | You | Local commits |
| Push to master | 6 | You | The commits are on master |
| Create the patchset tags | 6 | CI (`manifest.yml`) | `ruyi/v<version>-<n>` tags in openRuyi-Project/linux |
| Push a date tag | 7 | You | The date tag is in this repository |
| Publish the releases | 7 | CI (`release.yml`) | One GitHub release per package, for example `v6.18.63-1.0` |

Push the date tag only after `manifest.yml` is successful. You cannot take
back pushed manifest lines or published releases.

## metadata/maintained-branches

This file lists the `ruyi/X.Y.y` branches of openRuyi-Project/linux that get
new patchset tags. It contains one branch per line. A `#` starts a comment.
`scripts/manifest-update` writes the new manifest lines in the order of
this file.

```
ruyi/7.3.y
ruyi/7.2.y
ruyi/7.0.y
ruyi/6.18.y
```

## metadata/manifest

Each line contains a patchset tag and its commit, separated by one TAB:

```
ruyi/v7.3.4-1	7c961cd3020e50705b7eb39bea70a6063522ef47
```

- `<version>` is the kernel version of the commit. A `.0` version is
  written as `7.2`. A release candidate is written as `7.4-rc3`.
- `<n>` counts the tags of one version. It starts at 1.
- CI reads the file with a TAB separator. Spaces do not work. CI skips
  empty lines and lines that start with `#`.

> The file is append-only. After a push to master, each line becomes a tag
> in openRuyi-Project/linux. Do not change or remove pushed lines. Before
> the push, you can fix a line with `git commit --amend` or `git reset`.
> If a pushed line is wrong, do not edit it. Tell the team and agree on the
> next step.

### Auto-tagging

The workflow `.github/workflows/manifest.yml` runs on a push to master that
changes `metadata/manifest` or the workflow file. You can also start it by
hand (`workflow_dispatch`).

The workflow does these steps:

1. It reads each line of the manifest.
2. It skips a tag that already exists in openRuyi-Project/linux.
3. It stops with an error if a commit does not exist. In this case it pushes
   no tags at all.
4. It creates the missing tags as lightweight tags and pushes them.

The workflow needs the secret `CI_TOKEN` with push access to
openRuyi-Project/linux.

If the run fails because a commit is missing, push that commit to
openRuyi-Project/linux. Then run the workflow again. Do not create the tags
by hand.

### scripts/manifest-update

```
scripts/manifest-update [-a | -A] [-n] [-C <kernel-tree>] [-r <remote>] [-b <file>]
```

The script does these steps for each maintained branch:

1. It fetches `<remote>/<branch>` into the local kernel tree.
2. It reads the version from the `Makefile` of the branch tip.
3. It proposes `ruyi/v<version>-<n>` with the next free `<n>`.
4. It skips a branch whose tip is already in the manifest. It shows
   `unchanged` for it.

The script shows a warning in two cases:

| Warning | What to do |
|---|---|
| The local branch differs from the remote branch. | Push your commits or update the local branch. Only pushed commits can get a tag. |
| The proposed tag already exists in the local kernel tree. | Check if the tag is public: `git ls-remote --tags https://github.com/openRuyi-Project/linux 'ruyi/v*'`. If it is public but not in the manifest, ask the team before you continue. |

Do not use `-a` while a warning is shown.

| Option | Description |
|---|---|
| none | Show the new lines only. |
| `-a` | Add the lines and commit `manifest: add <v1>/<v2>/... tag` with a sign-off. The script stops if the manifest has uncommitted changes. |
| `-A` | Add the lines without a commit. |
| `-n` | Do not fetch. Use the remote-tracking refs as they are. |
| `-C <kernel-tree>` | Kernel tree. The default is `$KERNEL_DIR`, else `~/code/kernel/linux/ruyi-linux`. |
| `-r <remote>` | Remote name of openRuyi-Project/linux in that tree. The default is `$KERNEL_REMOTE`, else `ruyi`. |
| `-b <file>` | Branch list. The default is `metadata/maintained-branches`. |

If you cannot fetch over SSH, compare the remote state with the local refs:

```sh
git ls-remote https://github.com/openRuyi-Project/linux 'refs/heads/ruyi/*'
git -C ~/code/kernel/linux/ruyi-linux rev-parse ruyi/ruyi/7.3.y   # one per branch
```

Use `-n` only if each branch has the same commit in both outputs.

## TAG_NAME

`configs/<package>/config.env` selects the patchset tag of a package:

```
TAG_NAME=v7.3.4-1
```

Change it in a separate commit after the manifest commit, for example
`configs: linux: env: bump TAG_NAME to v7.3.4-1`.

## GitHub releases

The workflow `.github/workflows/release.yml` runs on each push. For each
package under `configs/`, it does these steps:

1. It reads `TAG_NAME` from `config.env`.
2. It checks out `ruyi/<TAG_NAME>` from openRuyi-Project/linux. If the tag
   does not exist yet, the run fails.
3. It finds the base tag (`TAG_NAME` without `-<n>`) in the stable tree, or
   else in the mainline tree. It generates the patch series from the base
   tag to `ruyi/<TAG_NAME>`.
4. It exports each config with `scripts/annotations --export`.
5. It packs the result as `<package>-<TAG_NAME>.tar.gz`.

The workflow fetches only the history after `v6.18`. A `TAG_NAME` with an
older base cannot produce a patch series.

> A push of a valid date tag publishes releases for all packages at once.
> You cannot take them back.

The workflow always uploads the tarballs as a workflow artifact. It
publishes GitHub releases only when the pushed ref is a tag in the format
`YYYY.MM.DD.HH.MM` with a valid date and time. For any other ref, it only
uploads the artifact.

For each date tag, the workflow creates one release for each package. The
release name is `<TAG_NAME>.<r>`, for example `v7.3.4-1.0` and
`v6.18.63-1.0`. `<r>` starts at 0. Each new date tag increases `<r>` of
every package by 1, even if its `TAG_NAME` did not change. The release
points to the commit of the date tag.

To publish, see step 7 in [workflows.md](workflows.md#release).
