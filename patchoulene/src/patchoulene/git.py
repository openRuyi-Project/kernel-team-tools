import re
import shlex
import subprocess

RE_HASH_LIKE = re.compile(r"[0-9a-f]+")


class GitCommit:
    commit: str
    message: str

    def __init__(self, commit: str, message: str):
        self.commit = commit
        self.message = message

        assert RE_HASH_LIKE.fullmatch(self.commit)

    def __repr__(self) -> str:
        return f"GitCommit(commit={repr(self.commit)}, message={repr(self.message)})"


class GitRepo:
    directory: str

    def __init__(self, directory: str):
        self.directory = directory

    def _git(
        self, args: list[str], /, input: str | None = "", check: bool = True
    ) -> str:
        full_cmd = ["git", "-C", self.directory, *args]
        proc = subprocess.run(
            full_cmd, input=input, check=check, stdout=subprocess.PIPE, encoding="utf-8"
        )
        return proc.stdout

    def commit_list(self, revs: list[str]) -> list[GitCommit]:
        cmd = shlex.split("log --no-merges --reverse --format='format:%H%n%B' -z")
        output = self._git([*cmd, "--end-of-options", *revs, "--"])

        if not output:
            return []

        def extract(entry):
            commit, message = entry.split("\n", 1)
            return GitCommit(commit=commit, message=message)

        return [extract(ent) for ent in output.split("\0")]

    def commit_info(self, rev: str) -> GitCommit:
        l = self.commit_list([f"{rev}^!"])
        assert len(l) == 1
        return l[0]

    def rev_parse(self, rev: str) -> str:
        return self._git(["rev-parse", "--verify", rev]).rstrip("\n")

    def cat_blob(self, blob: str) -> str:
        cmd = shlex.split("cat-file blob")
        return self._git([*cmd, "--end-of-options", blob])
