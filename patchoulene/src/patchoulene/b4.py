import re
import shlex
import subprocess
import sys


class PatchHeader:
    headers: dict[str, str]

    def __init__(self, headers: dict[str, str]):
        self.headers = headers

    def __repr__(self):
        return f"PatchHeader({self.headers!r})"

    def message_id(self) -> str:
        msgid_hdr = self.headers.get("message-id", None)
        assert msgid_hdr is not None
        assert len(msgid_hdr) > 2 and msgid_hdr[0] == "<" and msgid_hdr[-1] == ">"
        return msgid_hdr[1:-1]

    def subject(self) -> str:
        subject = self.headers.get("subject", None)
        assert subject is not None
        return subject

    def clean_subject(self) -> str:
        subject = self.subject()
        return re.sub(r"^(?:\[[^]]+\])*\s+", "", subject)


def parse_mbox_headers(mbox: str) -> list[PatchHeader]:
    parsing, last_key = True, None
    mails = []
    for line in mbox.splitlines():
        if line.startswith("From "):
            parsing, last_key = True, None
            mails.append({})
        elif parsing:
            if line.isspace() or not line:
                parsing = False
            elif m := re.match(r"^([A-Za-z0-9-]+): (.*)", line):
                assert mails
                mails[-1][m[1].lower()] = m[2]
                last_key = m[1].lower()
            elif line[0] == " ":
                assert mails
                assert last_key is not None
                assert last_key in mails[-1]
                mails[-1][last_key] += " " + line[1:]
            else:
                raise ValueError(f"Weird line {line!r}")
    return [PatchHeader(h) for h in mails]


def call_process(args: list[str]) -> str:
    try:
        return subprocess.check_output(args, encoding="utf-8", stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        e.add_note(e.stderr)
        raise


B4_USER_AGENT = "github.com/openRuyi-Project/kernel-team-tools"


def check_msgid(msgid: str) -> tuple[list[PatchHeader], list[PatchHeader]] | None:
    CMD = [
        *shlex.split("b4 -c"),
        f"lore.useragentplus={B4_USER_AGENT}",
        *shlex.split("am --no-add-trailers -o -"),
    ]

    try:
        this_thread = call_process([*CMD, "--", msgid])
        latest_thread = call_process([*CMD, "--check-newer-revisions", "--", msgid])
    except subprocess.CalledProcessError as e:
        print("*** b4 failed vvvvvv", file=sys.stderr)
        for note in e.__notes__:
            print(note, file=sys.stderr)
        print("*** b4 failed ^^^^^^", file=sys.stderr)

        return None

    this_thread_info = parse_mbox_headers(this_thread)
    latest_thread_info = parse_mbox_headers(latest_thread)

    this_ids = [m.message_id() for m in this_thread_info]

    if msgid not in this_ids:
        print(f"Can't handle weird threading in {msgid}", file=sys.stderr)
        return None

    return (this_thread_info, latest_thread_info)
