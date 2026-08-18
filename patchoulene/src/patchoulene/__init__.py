import datetime
import difflib
import json
import os
import pathlib
import re
import shlex
import subprocess
import sys

from . import b4
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


def prompt_yn(default: bool = False):
    prompt = "[Y/n]? " if default else "[y/N]? "
    while True:
        print(prompt, end="", file=sys.stderr)
        yn = input().strip().lower()
        if yn == "y" or (default and yn == ""):
            print("       (Yes)", file=sys.stderr)
            return True
        elif yn == "n" or (not default and yn == ""):
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
            for r in sorted(replaces[primary], key=lambda r: patch_num[r]):
                print(f"    - [{patch_num[r]}] {r}")
        else:
            print(f'+ New "{clean_subject(c.message)}"')
            print(f"    {primary}")


def db_by_subject(db: dict) -> dict[str, list[str]]:
    by_subject = {}

    for pid, data in db.items():
        if "subject" not in data:
            continue
        if data["subject"] not in by_subject:
            by_subject[data["subject"]] = []
        by_subject[data["subject"]].append(pid)

    return by_subject


def do_record(repo: GitRepo, db: dict, rev1: str, rev2: str):
    is_mainline = parse_base(rev2)[2] == 0

    by_subject = db_by_subject(db)

    for c in repo.commit_list([f"^{rev1}", rev2]):
        upstream = []
        if is_mainline:
            upstream.append(f"commit:{c.commit}")
        upstream.extend(guess_upstream_id(c.message))
        if not upstream:
            continue
        primary = upstream[0]
        clean = clean_subject(c.message)

        possible_matches = set(pid for pid in upstream[1:] if pid in db)
        possible_matches |= set(by_subject.get(clean, []))
        possible_matches -= {primary}

        possible_matches = {
            pid
            for pid in possible_matches
            if pid in db and not db[pid].get("replacement", None)
        }

        is_useful = False

        if possible_matches:
            print(f"Is new patch {primary}", file=sys.stderr)
            print(f"  (found as commit {c.commit})", file=sys.stderr)
            print(f'  "{clean}"', file=sys.stderr)

        for possible in possible_matches:
            old_subject = db[possible].get("subject", "(Unknown)")
            is_identical = " (identical subject)" if old_subject == clean else ""
            print(
                f"... the replacement of patch {possible}?",
                file=sys.stderr,
            )
            is_id_match = possible in upstream[1:]
            if not is_id_match:
                print(f"* (weak match)", file=sys.stderr)
            print(f'  "{old_subject}"{is_identical}', file=sys.stderr)
            if prompt_yn(is_id_match):
                is_useful = True
                db[possible]["replacement"] = primary

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
            print(f'{rev2} has "{clean}"', file=sys.stderr)
            if not is_mainline:
                print(f"  stable commit {c.commit}", file=sys.stderr)
            print(f"  identifier {primary}", file=sys.stderr)
            if "merged" not in db[primary]:
                db[primary]["merged"] = []
            db[primary]["merged"].append(rev2)


NO_COLOR = os.getenv("NO_COLOR", "") or not sys.stdout.isatty()


def color_sel(color_msg: str, msg: str) -> str:
    return msg if NO_COLOR else color_msg


def dim(msg: str) -> str:
    return color_sel(f"\x1b[90m{msg}\x1b[m", msg)


def walk_replacements(db: dict, pid: str) -> set[str]:
    replacements = set()
    todo = {pid}

    while todo:
        pid = todo.pop()

        if pid not in db or not db[pid].get("replacement", None):
            replacements.add(pid)
            continue

        repl = db[pid]["replacement"]
        if not isinstance(repl, list):
            repl = [repl]

        todo.update(repl)

    return replacements


def do_status(db: dict, commits: list[GitCommit], rev):
    for c in commits:
        clean = clean_subject(c.message)
        guessed = guess_id(c.message)
        if not guessed:
            continue
        primary = guessed[0]

        if primary not in db:
            print(f'Patch "{clean}":', file=sys.stderr)
            print(
                f"- This patch has not been recorded, please run './patl walk {rev}'",
                file=sys.stderr,
            )
            continue

        replacements = walk_replacements(db, primary)

        if replacements != {primary}:
            print(f'Commit {c.commit[:12]} ("{clean}"):')
            print(f"  {dim(primary)}")
            print(f"  has replacement:")
            for pid in replacements:
                subject = db.get(pid, {}).get("subject", "???")
                subject_suffix = ""
                if "subject" in db.get(pid, {}) and subject == clean:
                    subject_suffix = " (identical subject)"
                suffix = ""
                if pid in db and (merged := db[pid].get("merged", [])):
                    suffix = f" (merged {', '.join(merged)})"
                print(f'  - "{subject}"{subject_suffix}')
                print(f"    {dim(pid)}{suffix}")
            print()


def do_mail_check(db: dict[str, dict]) -> list[dict[str, list[dict[str, str]]]]:
    result = []
    checked = set()

    for pid, data in db.items():
        if data.get("replacement", None):
            continue

        if (m := re.fullmatch(r"mail:(\S+)", pid)) is None:
            continue

        msgid = m[1]

        if msgid in checked:
            print(
                f'Already checked "{data.get("subject", "???")}" {msgid}',
                file=sys.stderr,
            )
            continue
        else:
            print(f'Checking "{data.get("subject", "???")}" {msgid}', file=sys.stderr)

        if (res := b4.check_msgid(msgid)) is None:
            continue

        this_thread, latest_thread = res
        this_ids = [m.message_id() for m in this_thread]
        latest_ids = [m.message_id() for m in latest_thread]

        checked.update(this_ids)
        if set(this_ids) == set(latest_ids):
            continue

        print(f"Patches:", file=sys.stderr)
        for m in this_thread:
            print(f"  {m.clean_subject()}", file=sys.stderr)
            print(f"    https://patch.msgid.link/{m.message_id()}", file=sys.stderr)
        print(f"... may have replacement:", file=sys.stderr)
        for m in latest_thread:
            print(f"  {m.clean_subject()}", file=sys.stderr)
            print(f"    https://patch.msgid.link/{m.message_id()}", file=sys.stderr)

        result.append(
            {
                "current": [m.headers for m in this_thread],
                "replacement": [m.headers for m in latest_thread],
            }
        )

    return result


def do_mail_match(data: list[dict]):
    db = read_patch_db()
    for entry in data:
        current: list[b4.PatchHeader]
        replacement: list[b4.PatchHeader]
        proc = lambda ps: [b4.PatchHeader(h) for h in ps]
        current, replacement = proc(entry["current"]), proc(entry["replacement"])

        ids = [f"mail:{h.message_id()}" for h in current]
        if all(p not in db or db[p].get("replacement", None) for p in ids):
            continue

        curr_keys = [h.clean_subject() for h in current]
        rep_keys = [h.clean_subject() for h in replacement]
        if len(rep_keys) != len(set(rep_keys)):
            print("Duplicates in patch list?", file=sys.stderr)
        rep_map = {subj: idx for idx, subj in enumerate(rep_keys)}

        valid = [pid in db and not db[pid].get("replacement", None) for pid in ids]
        matrix: list[list[int] | None]
        matrix = [None] * len(current)

        # Guess an initial match based on subjects
        for i in range(len(curr_keys)):
            if valid[i] and curr_keys[i] in rep_map:
                matrix[i] = [rep_map[curr_keys[i]]]

        print("-" * 60, file=sys.stderr)
        while True:
            print("Current version:", file=sys.stderr)
            for idxa, ha in enumerate(current):
                if not valid[idxa]:
                    if ids[idxa] not in db:
                        why_invalid = "(not in db)"
                    else:
                        why_invalid = "(has replacement)"
                    print(
                        f"        {dim(f'({ha.subject()}) {why_invalid}')}",
                        file=sys.stderr,
                    )

                    if ids[idxa] in db:
                        assert "replacement" in db[ids[idxa]]
                        rs = db[ids[idxa]]["replacement"]
                        if not isinstance(rs, list):
                            rs = [rs]
                        for r in rs:
                            if info := db.get(r):
                                print(
                                    f"         {dim('->')} {dim(info.get('subject', '???'))}",
                                    file=sys.stderr,
                                )
                                print(f"            {dim(r)}", file=sys.stderr)
                            else:
                                print(
                                    f"         {dim('->')} {dim(r)} {dim('(Unknown patch???)')}",
                                    file=sys.stderr,
                                )
                    continue
                print(f"  {f'(A{idxa + 1})':>6} {ha.subject()}", file=sys.stderr)
                print(f"         {dim(f'mail:{ha.message_id()}')}", file=sys.stderr)
                row = matrix[idxa]
                if row is not None:
                    for idxb in row:
                        subj_b = replacement[idxb].subject()
                        print(f"         -> (B{idxb + 1}) {subj_b}", file=sys.stderr)
                else:
                    print(f"         (no replacement)", file=sys.stderr)

            print(file=sys.stderr)
            print("Replacement version:", file=sys.stderr)
            for idxb, hb in enumerate(replacement):
                print(f"  {f'(B{idxb + 1})':>6} {hb.subject()}", file=sys.stderr)
                print(f"         {dim(f'mail:{hb.message_id()}')}", file=sys.stderr)

            print(file=sys.stderr)
            print("Matrix:", file=sys.stderr)
            for idxa in range(len(current)):
                if not valid[idxa]:
                    continue
                if matrix[idxa] is not None:
                    assert matrix[idxa]
                mx = matrix[idxa] or []
                mstr = f"{idxa + 1} ={''.join(' ' + str(ib + 1) for ib in mx)}"
                print(f"    {mstr}", file=sys.stderr)

            print(file=sys.stderr)

            valids = sum(valid)
            missing = sum(valid[i] and not matrix[i] for i in range(len(current)))

            if missing == valids:
                print(f"None of {valids} patch(es) have replacement", file=sys.stderr)
                print(file=sys.stderr)
            elif missing:
                print(
                    f"{missing}/{valids} patches missing replacement", file=sys.stderr
                )
                print(file=sys.stderr)

            valid_options = []
            valid_keys = []

            if any(matrix):
                valid_options.append("(Y)es, accept this replacement matrix")
                valid_keys.append("y")
                valid_options.append("(N)o, decline this replacement matrix")
                valid_keys.append("n")
            else:
                valid_options.append(
                    "(Y)es, accept that no replacements will be recorded"
                )
                valid_keys.append("y")

            if len(current) == len(replacement):
                valid_options.append("Match (c)orresponding patches by number")
                valid_keys.append("c")

            for opt in valid_options:
                print(opt, file=sys.stderr)

            while True:
                match_row = None
                more_keys = "".join("/" + k for k in valid_keys if k != "y")
                print(f"[Y{more_keys}/(matrix row)]? ", end="", file=sys.stderr)
                key = input().strip()

                if key == "":
                    assert "y" in valid_keys
                    key = "y"
                    break

                if key.lower() in valid_keys:
                    key = key.lower()
                    break

                if match_row := re.fullmatch(r"(\d+)\s*=((?:[,\s]*(?:\d+))*)", key):
                    a = int(match_row[1])
                    bs = match_row[2].strip()
                    bs = re.split(r"[,\s]", bs) if bs else []
                    bs = [int(x) for x in bs]
                    if not (1 <= a <= len(current)) or not valid[a - 1]:
                        print(f"Invalid row number {a}", file=sys.stderr)
                        continue
                    bad = False
                    for b in bs:
                        if not (1 <= b <= len(replacement)):
                            print(f"Invalid replacement {b}", file=sys.stderr)
                            bad = True
                    if bad:
                        continue
                    a, bs = a - 1, [b - 1 for b in bs]

                    break

                print(f"Unrecognized action {key!r}", file=sys.stderr)

            if match_row:
                if bs:
                    matrix[a] = sorted(set(bs))
                else:
                    matrix[a] = None
                continue

            assert key in valid_keys

            match key:
                case "y":
                    print(f"(Accepted)", file=sys.stderr)
                    for i in range(len(current)):
                        row = matrix[i]

                        if not valid[i] or not row:
                            continue

                        cur_pid = f"mail:{current[i].message_id()}"
                        rs = [replacement[r] for r in row]

                        for r in rs:
                            rid = f"mail:{r.message_id()}"
                            if rid not in db:
                                db[rid] = {"subject": r.clean_subject()}

                        rids = [f"mail:{r.message_id()}" for r in rs]
                        assert "replacement" not in db[cur_pid]
                        if len(rids) == 1:
                            db[cur_pid]["replacement"] = rids[0]
                        else:
                            db[cur_pid]["replacement"] = rids
                    break
                case "n":
                    print(f"(Ignored)", file=sys.stderr)
                    break
                case "c":
                    for i in range(len(current)):
                        if valid[i]:
                            matrix[i] = [i]

            print(file=sys.stderr)

    write_patch_db(db)


def main():
    repo = GitRepo(".")
    match sys.argv[1:]:
        case ["check", ref]:
            base = guess_base(repo, ref)
            print(f"Base for {ref} is {base}", file=sys.stderr)
            do_check_messages(repo, [f"^refs/tags/{base}", ref])
        case ["status", rev]:
            base = guess_base(repo, rev)
            print(f"Base for {rev} is {base}", file=sys.stderr)
            commits = repo.commit_list([f"^refs/tags/{base}", rev])
            db = read_patch_db()
            do_status(db, commits, rev)
        case ["mail-check"]:
            db = read_patch_db()
            result_file = "mail-check.json"
            result = do_mail_check(db)
            if result:
                with open(result_file, "w") as f:
                    print(f"Writing to {result_file}", file=sys.stderr)
                    json.dump(result, f, indent=4)
                    f.write("\n")
            else:
                print("No updates found", file=sys.stderr)
        case ["mail-match"]:
            with open("mail-check.json", "rb") as f:
                data = json.load(f)
            do_mail_match(data)
        case ["mail-match", jsonfile]:
            with open(jsonfile, "rb") as f:
                data = json.load(f)
            do_mail_match(data)
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
            by_subject = db_by_subject(db)

            for c in repo.commit_list([f"^refs/tags/{base}", ref]):
                guess = guess_id(c.message)
                if not guess:
                    continue
                primary = guess[0]
                replacements = walk_replacements(db, primary)

                clean = clean_subject(c.message)
                if primary not in db:
                    db[primary] = {
                        "subject": clean,
                    }

                id_matches = set(pid for pid in guess[1:] if pid in db)
                possible_matches = id_matches | set(by_subject.get(clean, []))
                possible_matches -= {primary}

                possible_matches = {
                    pid
                    for pid in possible_matches
                    if pid in db
                    and pid not in replacements
                    and not db[pid].get("replacement", None)
                }

                for possible in possible_matches:
                    old_subject = db[possible].get("subject", "(Unknown)")
                    is_identical = (
                        " (identical subject)" if old_subject == clean else ""
                    )
                    print(f"Is new patch {primary}", file=sys.stderr)
                    print(f'  "{clean}"', file=sys.stderr)
                    print(f"... the replacement of patch {possible}?", file=sys.stderr)
                    if possible not in id_matches:
                        print(f"* (weak match)", file=sys.stderr)
                    print(f'  "{old_subject}"{is_identical}', file=sys.stderr)
                    if prompt_yn():
                        db[possible]["replacement"] = primary

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
