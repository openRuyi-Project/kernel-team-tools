import difflib
import json
import pathlib
import re
import shlex
import subprocess
import sys

from .message import *
from .git import GitCommit, GitRepo


def series_entry(c: GitCommit):
    lines = []
    guessed = guess_id(c.message)
    if guessed:
        lines.append(f"# {guessed[0]}")
    lines.append(f"{sanitize_subject(clean_subject(c.message))}.patch")
    return "".join(l + "\n" for l in lines)


def do_check_messages(repo: GitRepo, revs: list[str]):
    commits = repo.commit_list(revs)
    for c in commits:
        problems = check_message(c.message)
        if not problems:
            continue
        print(f'Commit {c.commit[:12]} ("{clean_subject(c.message)}")')
        for p in problems:
            print(f"- {p}")
        print()


def guess_base(repo: GitRepo, rev: str) -> str:
    canon_rev = repo.rev_parse(rev)
    file = repo.cat_blob(f"{canon_rev}:Makefile")
    data = {}
    for line in file.splitlines():
        m = re.fullmatch(r"([A-Z]+) = ([^\s]+)", line)
        if m is None:
            continue
        data[m[1]] = m[2]
    if any(k not in data for k in ("VERSION", "PATCHLEVEL", "SUBLEVEL")):
        raise RuntimeError(f"Failed to guess rev for {rev} ({canon_rev})")
    sub = "" if data["SUBLEVEL"] == "0" else f".{data['SUBLEVEL']}"
    return f"v{data['VERSION']}.{data['PATCHLEVEL']}{sub}{data.get('EXTRAVERSION', '')}"


def parse_base(tag: str) -> tuple[int, int, int, int]:
    # Examples:
    #
    # - Mainline releases:  7.1         -> (7, 1, 0, 0)
    # - Mainline rc:        7.0-rc1     -> (7, 0, 0, 1)
    # - Stable releases:    7.1.4       -> (7, 1, 4, 0)
    # - Stable rc:          7.1.4-rc1   -> (7, 1, 4, 1)
    m = re.fullmatch(r"v(\d+)\.(\d+)(?:\.(\d+))?(?:-rc(\d+))?", tag)
    assert m is not None, f"Weird tag {tag}"
    return (int(m[1]), int(m[2]), int(m[3] or "0"), int(m[4] or "0"))


def base_is_contained_in(tag1: str, tag2: str) -> bool:
    w1, x1, y1, z1 = parse_base(tag1)
    w2, x2, y2, z2 = parse_base(tag2)
    if (y1 and z1) or (y2 and z2):
        # No assumptions about stable rc releases
        return False

    if y1 == 0:
        # tag1 is a mainline release, so only need to compare the mainline part
        return (w1, x1, z1 == 0, z1) <= (w2, x2, z2 == 0, z2)

    # tag1 is a stable release
    if (w1, x1) != (w2, x2):
        # Not the same stable branch
        return False
    return y1 <= y2


def read_patch_db():
    try:
        with open("patches.json.new", "rb") as f:
            return json.load(f)
    except FileNotFoundError:
        try:
            with open("patches.json", "rb") as f:
                return json.load(f)
        except FileNotFoundError:
            return {}


def write_patch_db(db):
    with open("patches.json.new", "w") as f:
        print("Writing to patches.json.new", file=sys.stderr)
        json.dump(db, f, indent=4)
        f.write("\n")


def prompt_yn():
    while True:
        yn = input("[Y/n]? ").strip().lower()
        if yn in ("y", ""):
            print("       (Yes)", file=sys.stderr)
            return True
        elif yn == "n":
            print("       (No)", file=sys.stderr)
            return False


def do_diff_commits(
    commits1: list[GitCommit],
    commits2: list[GitCommit],
    base2: str,
    pre: str = "(before)",
    post: str = "(after)",
):
    cl1 = [g[0] for c in commits1 if (g := guess_id(c.message))]
    cl2 = [g[0] for c in commits2 if (g := guess_id(c.message))]
    cs1, cs2 = set(cl1), set(cl2)
    assert len(cl1) == len(cs1), f"{pre} contains duplicate patches"
    assert len(cl2) == len(cs2), f"{post} contains duplicate patches"

    new_patches = cs2 - cs1
    removed_patches = cs1 - cs2
    replacements = {}
    replaces = {}

    db = read_patch_db()
    for removed in removed_patches:
        remaining = {removed}
        grabbed = set()
        merged = set()
        while remaining:
            p = remaining.pop()

            if p in cs2:
                grabbed.add(p)
                continue

            if p not in db:
                break

            merged_bases = [
                m for m in db[p].get("merged", []) if base_is_contained_in(m, base2)
            ]
            if merged_bases:
                merged.add((p, merged_bases[0]))
                continue

            if db[p].get("replacement", None) is None:
                break
            elif isinstance(db[p]["replacement"], list):
                remaining.update(db[p]["replacement"])
            else:
                remaining.add(db[p]["replacement"])
        else:
            replacements[removed] = (grabbed, merged)
            new_patches -= grabbed
            for g in grabbed:
                if g not in replaces:
                    replaces[g] = set()
                replaces[g].add(removed)

    # First pass, only collect patch numbers

    patch_num = {}

    for c in commits1:
        guessed = guess_id(c.message)
        if not guessed:
            continue
        primary = guessed[0]
        if primary in replacements:
            gs, ms = replacements[primary]
            if gs:
                patch_num[primary] = len(patch_num) + 1

    for c in commits2:
        guessed = guess_id(c.message)
        if not guessed:
            continue
        primary = guessed[0]
        if primary in replaces:
            patch_num[primary] = len(patch_num) + 1

    # Now we actually print everything

    print(f"Removals from {pre}")
    if not removed_patches:
        print("  (None)")

    for c in commits1:
        guessed = guess_id(c.message)
        if not guessed:
            continue
        primary = guessed[0]
        if primary not in removed_patches:
            continue
        if primary in replacements:
            gs, ms = replacements[primary]
            prefix = f"[{patch_num[primary]}] Replaced" if gs else "Merged"
            print(f'  {prefix} "{clean_subject(c.message)}"')
            print(f"    - {primary}")
            for g in gs:
                print(f"    + [{patch_num[g]}] {g}")
            for m, base in ms:
                print(f"      in {base} ({m})")
        else:
            print(f'- Removed "{clean_subject(c.message)}"')
            print(f"    {primary}")

    print()
    print(f"Additions to {post}")
    if not new_patches and not replaces:
        print("  (None)")

    for c in commits2:
        guessed = guess_id(c.message)
        if not guessed:
            continue
        primary = guessed[0]
        if primary not in new_patches and primary not in replaces:
            continue
        if primary in replaces:
            print(f'  [{patch_num[primary]}] Replacement "{clean_subject(c.message)}"')
            print(f"    + {primary}")
            for r in replaces[primary]:
                print(f"    - [{patch_num[r]}] {r}")
        else:
            print(f'+ New "{clean_subject(c.message)}"')
            print(f"    {primary}")


def do_record(repo: GitRepo, db: dict, rev1: str, rev2: str):
    is_mainline = parse_base(rev2)[2] == 0
    for c in repo.commit_list([f"^{rev1}", rev2]):
        upstream = []
        if is_mainline:
            upstream.append(f"commit:{c.commit}")
        upstream.extend(guess_upstream_id(c.message))
        if not upstream:
            continue
        primary = upstream[0]
        clean = clean_subject(c.message)

        is_useful = False

        for secondary in upstream[1:]:
            if secondary in db:
                if db[secondary].get("replacement", None):
                    continue
                old_subject = db[secondary].get("subject", "(Unknown)")
                is_identical = " (identical subject)" if old_subject == clean else ""
                print(f"Is new patch {primary}", file=sys.stderr)
                print(f"  (stable branch commit {c.commit})", file=sys.stderr)
                print(f'  "{clean}"', file=sys.stderr)
                print(
                    f"... the replacement of patch {secondary}?",
                    file=sys.stderr,
                )
                print(f'  "{old_subject}"{is_identical}', file=sys.stderr)
                if prompt_yn():
                    is_useful = True
                    db[secondary]["replacement"] = primary

        if is_useful and primary not in db:
            db[primary] = {
                "subject": clean,
            }

        if primary in db:
            known_merged = any(
                base_is_contained_in(m, rev2) for m in db[primary].get("merged", [])
            )
            if known_merged:
                continue
            print(
                f'{c.commit[:12]} ("{clean}") merged in {rev2}',
                file=sys.stderr,
            )
            if "merged" not in db[primary]:
                db[primary]["merged"] = []
            db[primary]["merged"].append(rev2)


def main():
    repo = GitRepo(".")
    match sys.argv[1:]:
        case ["check", ref]:
            base = guess_base(repo, ref)
            print(f"Base for {ref} is {base}", file=sys.stderr)
            do_check_messages(repo, [f"^refs/tags/{base}", ref])
        case ["diff", rev1, rev2]:
            base1 = guess_base(repo, rev1)
            print(f"Base for {rev1} is {base1}", file=sys.stderr)
            base2 = guess_base(repo, rev2)
            print(f"Base for {rev2} is {base2}", file=sys.stderr)

            commits1 = repo.commit_list([f"^refs/tags/{base1}", rev1])
            commits2 = repo.commit_list([f"^refs/tags/{base2}", rev2])
            do_diff_commits(commits1, commits2, base2, pre=rev1, post=rev2)
        case ["walk", ref]:
            base = guess_base(repo, ref)
            print(f"Base for {ref} is {base}", file=sys.stderr)
            db = read_patch_db()
            for c in repo.commit_list([f"^refs/tags/{base}", ref]):
                guess = guess_id(c.message)
                if not guess:
                    continue
                primary = guess[0]
                clean = clean_subject(c.message)
                if primary not in db:
                    db[primary] = {
                        "subject": clean,
                    }

                for secondary in guess[1:]:
                    if secondary in db:
                        if db[secondary].get("replacement", None):
                            continue
                        old_subject = db[secondary].get("subject", "(Unknown)")
                        is_identical = (
                            " (identical subject)" if old_subject == clean else ""
                        )
                        print(f"Is new patch {primary}", file=sys.stderr)
                        print(f'  "{clean}"', file=sys.stderr)
                        print(
                            f"... the replacement of patch {secondary}?",
                            file=sys.stderr,
                        )
                        print(f"  (Identifier matches)", file=sys.stderr)
                        print(f'  "{old_subject}"{is_identical}', file=sys.stderr)
                        if prompt_yn():
                            db[secondary]["replacement"] = primary
            write_patch_db(db)

        case ["record", rev1, rev2]:
            db = read_patch_db()
            assert base_is_contained_in(rev1, rev2)
            while not base_is_contained_in(rev2, rev1):
                pre = guess_base(repo, f"{rev2}^1")
                print(f"Checking {pre}...{rev2}", file=sys.stderr)
                do_record(repo, db, pre, rev2)
                rev2 = pre
            write_patch_db(db)

        case _:
            print(f"Bad usage", file=sys.stderr)
            sys.exit(1)
