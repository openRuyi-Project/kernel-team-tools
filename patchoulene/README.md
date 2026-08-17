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

### `mail-check`

```console
$ ./patl mail-check
```

Check mailing lists for new versions of patches and patch series, and save to `mail-check.json`.
Use `./patl mail-match` to interactively add replacement information from `mail-check.json`

### `mail-match`

```console
$ ./patl mail-match `file`
```

The `file` argument is optional; if omitted, it defaults to `mail-check.json`, which is the default output file name of `./patl mail-check`.

Interactively merge data from the `mail-check.json` file into the patch database.
For each patch or patch series version update, a replacement view and a prompt would appear.
The patches are matched heuristically by subject initially.
You can edit, accept, discard each replacement item on each prompt.

<details>

<summary>Detailed example</summary>

The view is divided into four sections.
Firstly, the current version shows the current known version of the series.
Patches are shown with their currently matched replacements, if any.

Some patches may not be eligible for replacement.
These patches are shown with parentheses around their subjects.
The reason will be shown as well.

```
Current version:
    (A1) [PATCH 1/4] riscv: defconfig: enable RFKILL and RFKILL_GPIO
         mail:20260716213314.3027969-2-aurelien@aurel32.net
         -> (B1) [PATCH v2 1/4] riscv: defconfig: enable RFKILL and RFKILL_GPIO
        ([PATCH 2/4] riscv: dts: spacemit: k3: add rfkill node for Bluetooth on Pico-ITX board) (has replacement)
         -> riscv: dts: spacemit: k3: add rfkill node for Bluetooth on Pico-ITX board
            mail:20260729172450.1660418-3-aurelien@aurel32.net
    (A3) [PATCH 3/4] riscv: dts: spacemit: k3: add USB3 B and C controllers for Pico-ITX board
         mail:20260716213314.3027969-4-aurelien@aurel32.net
         -> (B3) [PATCH v2 3/4] riscv: dts: spacemit: k3: add USB3 B and C controllers for Pico-ITX board
    (A4) [PATCH 4/4] riscv: dts: spacemit: k3: add rfkill node for WLAN on Pico-ITX board
         mail:20260716213314.3027969-5-aurelien@aurel32.net
         (no replacement)
```

Secondly, the replacement series is shown.

```
Replacement version:
    (B1) [PATCH v2 1/4] riscv: defconfig: enable RFKILL and RFKILL_GPIO
         mail:20260729172450.1660418-2-aurelien@aurel32.net
    (B2) [PATCH v2 2/4] riscv: dts: spacemit: k3: add rfkill node for Bluetooth on Pico-ITX board
         mail:20260729172450.1660418-3-aurelien@aurel32.net
    (B3) [PATCH v2 3/4] riscv: dts: spacemit: k3: add USB3 B and C controllers for Pico-ITX board
         mail:20260729172450.1660418-4-aurelien@aurel32.net
    (B4) [PATCH v2 4/4] riscv: dts: spacemit: k3: add rfkill node for WLAN
         mail:20260729172450.1660418-5-aurelien@aurel32.net
```

Then the current replacement is shown again, concisely as a matrix.
Here, it means that patch A1 corresponds to B1, and A3 corresponds to B3.
Patch A4 has no replacement.

```
Matrix:
    1 = 1
    3 = 3
    4 =

1/3 patches missing replacement
```

Finally, the prompt shows available actions. You can type a letter and enter to perform one of these actions

- `y`: Accept the replacements as shown.
  This is also the default action performed if you type enter without a letter.
- `n`: Discard the entire matrix. No replacements will be recorded.
- `c`: If both series have the same number of patches, this creates a replacement matrix that matches patch A1 with B1, A2 with B2, etc.

You can also type a matrix row to edit the replacement of a certain patch.
For example, to say that patch A2 corresponds to B2 and B3, type `2=2,3`.
To delete the replacement for patch A1, type `1=`.

```
(Y)es, accept this replacement matrix
(N)o, decline this replacement matrix
Match (c)orresponding patches by number
[Y/n/c/(matrix row)]?
```

(If there's no replacement for this series at all, the prompt will be different to highlight this fact.)

```
(Y)es, accept that no replacements will be recorded
[Y/(matrix row)]?
```

In this case, we can verify that patch A4 corresponds to B4.
Therefore, we type `4=4`.
Alternatively, since both series have four patches, `c` also performs the same action.
This results in:

```
Current version:
    (A1) [PATCH 1/4] riscv: defconfig: enable RFKILL and RFKILL_GPIO
         mail:20260716213314.3027969-2-aurelien@aurel32.net
         -> (B1) [PATCH v2 1/4] riscv: defconfig: enable RFKILL and RFKILL_GPIO
        ([PATCH 2/4] riscv: dts: spacemit: k3: add rfkill node for Bluetooth on Pico-ITX board) (has replacement)
         -> riscv: dts: spacemit: k3: add rfkill node for Bluetooth on Pico-ITX board
            mail:20260729172450.1660418-3-aurelien@aurel32.net
    (A3) [PATCH 3/4] riscv: dts: spacemit: k3: add USB3 B and C controllers for Pico-ITX board
         mail:20260716213314.3027969-4-aurelien@aurel32.net
         -> (B3) [PATCH v2 3/4] riscv: dts: spacemit: k3: add USB3 B and C controllers for Pico-ITX board
    (A4) [PATCH 4/4] riscv: dts: spacemit: k3: add rfkill node for WLAN on Pico-ITX board
         mail:20260716213314.3027969-5-aurelien@aurel32.net
         -> (B4) [PATCH v2 4/4] riscv: dts: spacemit: k3: add rfkill node for WLAN

Replacement version:
    (B1) [PATCH v2 1/4] riscv: defconfig: enable RFKILL and RFKILL_GPIO
         mail:20260729172450.1660418-2-aurelien@aurel32.net
    (B2) [PATCH v2 2/4] riscv: dts: spacemit: k3: add rfkill node for Bluetooth on Pico-ITX board
         mail:20260729172450.1660418-3-aurelien@aurel32.net
    (B3) [PATCH v2 3/4] riscv: dts: spacemit: k3: add USB3 B and C controllers for Pico-ITX board
         mail:20260729172450.1660418-4-aurelien@aurel32.net
    (B4) [PATCH v2 4/4] riscv: dts: spacemit: k3: add rfkill node for WLAN
         mail:20260729172450.1660418-5-aurelien@aurel32.net

Matrix:
    1 = 1
    3 = 3
    4 = 4

(Y)es, accept this replacement matrix
(N)o, decline this replacement matrix
Match (c)orresponding patches by number
[Y/n/c/(matrix row)]?
```

The replacement matrix is now complete and correct.
Type enter or `y` then enter to accept this replacement.

</details>

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
