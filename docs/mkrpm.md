# scripts/mkrpm

`scripts/mkrpm` builds the openRuyi linux RPM packages from a kernel tree.
Use a worktree of `ruyi/X.Y.y`. The tree already contains the openRuyi
patchset. The terms are defined in the [README](../README.md#terms).

The script supports two spec layouts: ruyi (the default) and openEuler
(`--distro oe`).

The script does these steps:

1. It generates the config from the annotations, or it uses the file that
   you give with `--config`.
2. It packs the source tree as Source0
   (`linux-<version><git suffix>.tar.xz`, see [Versions](#versions)).
3. For the ruyi layout, it also makes a Source1 tarball with the config and
   an empty patch series. The series is empty because the patches are
   already in Source0. The openEuler layout has no Source1. It gets the
   config as `SOURCES/mkrpm.config`.
4. It writes a spec from `spec/linux.spec` (ruyi layout) or
   `spec/kernel.spec` (openEuler layout).
5. It runs `rpmbuild`.

```
scripts/mkrpm [options] <kernel-tree>
```

> Always give the package with `-p`. The default package is `linux`. The
> script does not compare the tree version with the package. A 6.18 tree
> without `-p linux-lts` is built with the `linux` annotations.

## Examples

```sh
K=~/code/kernel/linux/linux-6.18

scripts/mkrpm -p linux-lts $K                          # riscv64 generic
scripts/mkrpm -p linux-lts --flavour rva20 $K          # riscv64 rva20
scripts/mkrpm -p linux-lts --arch x86_64 $K            # x86_64
scripts/mkrpm -p linux-lts --toolchain clang $K        # LLVM build
scripts/mkrpm -p linux-lts --distro oe $K              # openEuler layout
scripts/mkrpm -p linux-lts --dry-run $K                # show the rpmbuild command only
scripts/mkrpm --config my.config --arch x86_64 $K      # your own config, no annotations
```

## Requirements

| Build | Tools |
|---|---|
| All builds | rpmbuild, gcc, bison, flex, make, perl, python3, tar, xz, zstd, cpio |
| Cross build (target arch is not the host arch) | `<prefix>gcc`, `<prefix>ld.bfd`, `<prefix>objcopy` |
| `--toolchain clang` | clang, clang++, ld.lld and the llvm tools, with the same version suffix |

The script checks these tools before the build. `--skip-preflight` turns
off this check. It does not turn off the search for an LLVM toolchain. The
script stops if `--toolchain clang` finds no complete LLVM toolchain.

## Options

| Option | Default | Description |
|---|---|---|
| `-p, --package <package>` | `linux` | Annotations package under `configs/` |
| `-a, --arch <arch>` | `$ARCH`, else `riscv64` | Target arch: `riscv64` or `x86_64` |
| `-f, --flavour <flavour>` | `generic` | Flavour from the annotations |
| `-c, --config <file>` | | Use this config instead of the annotations. You cannot use it with `--flavour`. |
| `--distro ruyi\|oe` | `ruyi` | Spec layout |
| `-w, --workdir <dir>` | `build/<package>-<arch>-<flavour>` | rpmbuild top directory. See [Work directory](#work-directory). |
| `--reuse` | | Use Source0 and the config of the last run again. See the warning below. |
| `--toolchain gcc\|clang` | `gcc` | `clang` builds with `LLVM=`. The packages get a `.clang` tag. |
| `--llvm <value>` | found automatically | `LLVM=` value, for example `1` or `-21` |
| `--cross-prefix <prefix>` | found automatically | Cross toolchain prefix. The script tries `$CROSS_COMPILE`, `<arch>-openruyi-linux-gnu-`, `<arch>-unknown-linux-gnu-` and `<arch>-linux-gnu-`, in this order. |
| `-j, --jobs <n>` | `nproc` | Parallel jobs |
| `-r, --release-suffix <text>` | | Extra part in the RPM Release field, for example `local` |
| `-i, --iteration <n>` | automatic | Iteration number. See [Versions](#versions). |
| `--with-tools`, `--without-tools` | on for a native build, off for a cross build | tools subpackage. Only the ruyi layout uses this option. |
| `--with-devel`, `--without-devel` | on for a native build, off for a cross build | devel subpackage |
| `--dry-run` | | Prepare everything and show the rpmbuild command. Do not build. |
| `--skip-preflight` | | Do not check the required tools |

The script reads these environment variables. Command line options have
priority.

| Variable | Effect |
|---|---|
| `ARCH` | Default arch. Only `riscv` and `x86_64` are used. Other values, for example `x86`, give a warning and the script uses `riscv64`. |
| `CROSS_COMPILE` | Default cross prefix |
| `RUST_LIB_SRC` | Passed to the kernel build |
| `RUST_TARGET` | Recorded only. It has no effect. |

To check them, run `env | grep -E '^(ARCH|CROSS_COMPILE|RUST_LIB_SRC)='`.
The work directory name shows the arch that the script used.

> Do not use `--reuse` after you change the sources or the annotations.
> `--reuse` uses the old Source0 if the file name is the same, and new
> uncommitted changes do not change the file name. It also uses the old
> config, so it does not include annotations changes. With `--config`, the
> script copies the config again on each run.

## Versions

Example for a tree 928 commits after `v6.18.63`:

| Part | Example | Source |
|---|---|---|
| Kernel version | `6.18.63` | `Makefile` of the tree |
| Patchset number | `1` | The script looks for a manifest line with the tree HEAD commit and the tree version. It uses `<n>` of that line. Else it uses 1. |
| Config version | `0` | Fixed at 0 in the script |
| Git suffix | `-00928-g8ce7b0823e27` | Commits after the upstream tag, and the commit ID |
| Iteration | `1` | Build counter, see below |

The kernel release is `6.18.63-1.0-00928-g8ce7b0823e27-1`. The RPM Release
field contains the same data in RPM characters: `1.0.00928.g8ce7b0823e27.1`.

Git suffix:

- The commit count needs the annotated upstream tag `v<version>` in the
  local repository. Without it, the suffix is only `-g<commit>`.
- Uncommitted changes to tracked files add `-dirty`. Untracked files do not
  add `-dirty`, but Source0 contains them if git does not ignore them.
  Before you share a package, run `git status` in the tree and remove files
  that must not be published.
- A tree that is not a git repository gets `+`.

Iteration:

- The script keeps one counter for each kernel version, git suffix, arch,
  flavour, package and toolchain.
- A new commit or a change of the `-dirty` state starts a new counter at 1.
- With the same git suffix, a change of Source0 or the config adds 1. The
  same input keeps the same number.
- `--iteration <n>` sets the number.
- The counters are stored in the work directory. If you remove the work
  directory, the counters start again. A later build can then get an RPM
  Release field that you already shared. Use `--iteration <n>` to prevent
  this.

## Work directory

The default work directory is `build/<package>-<arch>-<flavour>` in this
repository. With `--config`, the last part is `config` instead of the
flavour. `--distro oe` adds `-oe`. `--toolchain clang` adds `-clang`.

| Command | Work directory |
|---|---|
| `scripts/mkrpm $K` | `build/linux-riscv64-generic` |
| `scripts/mkrpm -p linux-lts --flavour rva20 $K` | `build/linux-lts-riscv64-rva20` |
| `scripts/mkrpm --config my.config --arch x86_64 $K` | `build/linux-x86_64-config` |
| `scripts/mkrpm --distro oe --toolchain clang $K` | `build/linux-riscv64-generic-oe-clang` |

The packages are in `<work directory>/RPMS/` and `<work directory>/SRPMS/`.
