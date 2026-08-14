# Patchoulene (`patl`)

The openRuyi Linux kernel patch database tool.

## Stability

For now, there is no stability guarantee for Patchoulene whatsoever.
This tool is only intended to be compatible with the `patches.json` file in this repository at the same commit as the tool.
Format migration can and will happen without notice.

## Setup

Example setup: In your Linux Git worktree containing the `.git` directory:

```console
$ echo /patches.json >> .git/info/exclude
$ echo /patl >> .git/info/exclude
$ ln -s .../path/to/patchoulene/patl .
$ ln -s .../path/to/patches.json .
```

To run Patchoulene:

```console
$ ./patl ...
```

## Usage

### Database management

Patchoulene always reads from:

- `patches.json.new`, if it exists, and
- `patches.json`, otherwise.

Patchoulene always writes the new database to `patches.json.new`.

To update the database:

```console
$ diff patches.json patches.json.new    # Review
$ cp patches.json.new patches.json
$ rm patches.json.new    # (Optional)
```

### `check`

```console
$ ./patl check <rev>
```

Check patches in `rev` for potential problems. Use `HEAD` as `rev` to check the current checked out HEAD.

Currently, these problems are diagnosed:

- Message has no identifier

  This commit message has no identifier, and thus is not trackable by Patchoulene.

- Message line '...' confuses git am

  The message contains content that would confuse `git mailsplit` or `git mailinfo`, which means that a patch generated from `git format-patch` on this commit would not be correctly handled by `git am`.

### `status`

```console
$ ./patl status <rev>
```

Check patches in `rev` for possibly outdated patches, based on information in the database.

An example output item is as follows:

```
Commit 677c9368d444 ("riscv: dts: spacemit: k3: add rfkill node for WLAN on Pico-ITX board"):
  mail:20260716213314.3027969-5-aurelien@aurel32.net
  has replacement:
  - "riscv: dts: spacemit: k3: add rfkill node for WLAN"
    mail:20260729172450.1660418-5-aurelien@aurel32.net
```

This shows that the commit `677c9368d444` (which is an ancestor of `rev`) is identified and, according to the database, it has a replacement.

### `walk`

```console
$ ./patl walk <rev>
```

Record patches in `rev`. Write newly found patches to database.

In addition, if patches are found that are potentially replacements for previously known patches, a prompt appears to confirm this:

```
Is new patch commit:4edd70ee6a7d0408a4e3ac921185779e7605f29c
  "mm/sparse-vmemmap: flush_cache_vmap() after hotplugging vmemmap"
... the replacement of patch mail:20260713-mark-after-vmemmap-populate-v6-2-b945ceba29d4@iscas.ac.cn?
  (Identifier matches)
  "mm/sparse-vmemmap: flush_cache_vmap() after hotplugging vmemmap" (identical subject)
[Y/n]?
```

If you say Y, the old patch is regarded as being replaced by the new patch. If you say N, it will be ignored.

It is safe to run `./patl walk <rev>` for the same `rev` multiple times.

### `record`

```console
$ ./patl record <upstream-tag-1> <upstream-tag-2>
```

Record patches that are included between `upstream-tag-1` and `upstream-tag-2`.

Commits in each version in the range of `<upstream-tag-1>...<upstream-tag-2>` are inspected for potential matches in the database.
If any commit hash matches are found, they're added to the database and recorded as being merged in the version matched.
If less precise matches are found, they're prompted for, similar to patch replacements.

For example, `./patl record v7.0 v7.1.2` would check the ranges

- v7.1.1...v7.1.2
- v7.1...v7.1.1
- v7.1-rc7...v7.1
- v7.1-rc6...v7.1-rc7
- (More rc versions omitted)
- v7.1-rc1...v7.1-rc2
- v7.0...v7.1-rc1

It is safe to run `./patl record <upstream-tag-1> <upstream-tag-2>` for the same tags multiple times.

### `diff`

```console
$ ./patl diff <rev1> <rev2>
```

Compare patches between `rev1` and `rev2`, using information in the database.

## Patch series and identifiers

(TODO)

## Database format

The database is, for now, a JSON file following the schema in `patches.schema.json`.
It is intended for both automatic and manual modification.
The format is somewhat version control friendly, but it is not ideal.
Tools intending to modify the `patches.json` automatically *should* preserve the existing key ordering.

## Known issues and future work

- Error handling is unfriendly
- More patch matching heuristics are needed
- JSON is annoying

## Naming

Patchoulene is found in the extract of the Patchouli plant.
The name "patchouli" was already taken so a different name was used.
