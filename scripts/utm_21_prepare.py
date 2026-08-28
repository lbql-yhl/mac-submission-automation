#!/usr/bin/env python3
"""Prepare one selected GitHub branch for UTM-21 without visual automation."""

from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import urllib.parse
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator, Protocol


PROJECT_SOURCE_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_SOURCE_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_SOURCE_ROOT))

from scripts.utm_env_download_assets import (  # noqa: E402
    DEFAULT_BASE_URL,
    FeishuClient,
    GitHubRepositoryClient,
    _extract_github_repository_zip,
    _link_value,
    parse_github_repo_url,
    parse_base_url,
    select_exact_record,
    load_credentials,
)
from scripts.ssh_password import password_environment, scp_args, ssh_args  # noqa: E402
from scripts.notion_api import api_from_env  # noqa: E402
from services import feishu_bot  # noqa: E402
from services.project_paths import PROJECT_ROOT, SHARED_DIR  # noqa: E402


ALLOWED_BRANCHES = ("main", "dev", "release")
CODE_URL_FIELD = "代码 URL"
PLACEHOLDER_TARGETS = {
    "5372311233": "app_id",
    "jltest.test.test": "bundle_id",
    "uildbet.brovaxtere": "bundle_id",
    "xycoins.2027.test": "bundle_id",
    "org.toolbox.fastcleaner": "bundle_id",
}
BUNDLE_ID_RE = re.compile(r"[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")
PLACEHOLDER_PATTERN = re.compile(
    b"|".join(re.escape(value.encode("ascii")) for value in PLACEHOLDER_TARGETS)
)


class UTM21Error(RuntimeError):
    """Raised when UTM-21 cannot prove one safe branch preparation state."""


class MissingCodeURL(UTM21Error):
    """Raised after the exact Feishu row has no usable code URL."""


@dataclass(frozen=True, repr=False)
class ReplacementIdentifiers:
    app_id: str
    bundle_id: str

    def __post_init__(self) -> None:
        if (
            re.fullmatch(r"[0-9]+", self.app_id) is None
            or self.app_id in PLACEHOLDER_TARGETS
        ):
            raise UTM21Error("NOTION_APP_ID_INVALID")
        if (
            BUNDLE_ID_RE.fullmatch(self.bundle_id) is None
            or self.bundle_id in PLACEHOLDER_TARGETS
        ):
            raise UTM21Error("NOTION_BUNDLE_ID_INVALID")


def load_notion_identifiers(
    api: Any,
    *,
    parent_title: str,
    page_title: str,
    app_name: str,
    vm_user: str,
) -> ReplacementIdentifiers:
    final_directory_name(app_name)
    if not parent_title or any(character in parent_title for character in "\r\n\x00"):
        raise UTM21Error("NOTION_PARENT_IDENTITY_INVALID")
    if not re.fullmatch(r"[a-z]{4}", vm_user):
        raise UTM21Error("VM_USER_INVALID")
    if page_title != f"{app_name}-{vm_user}":
        raise UTM21Error("NOTION_PAGE_IDENTITY_MISMATCH")

    snapshots: list[tuple[str, str, str]] = []
    try:
        api.verify_parent(parent_title)
        for _index in range(2):
            snapshot = (
                str(api.read_field(page_title, "应用信息", "应用名: ") or "").strip(),
                str(api.read_field(page_title, "账号信息", "APP_ID：") or "").strip(),
                str(api.read_field(page_title, "应用信息", "正式包名: ") or "").strip(),
            )
            if snapshot[0] != app_name:
                raise UTM21Error("NOTION_PAGE_APP_MISMATCH")
            snapshots.append(snapshot)
            api.verify_parent(parent_title)
    except UTM21Error:
        raise
    except Exception as exc:
        raise UTM21Error("NOTION_IDENTIFIER_READ_FAILED") from exc
    if len(snapshots) != 2 or snapshots[0] != snapshots[1]:
        raise UTM21Error("NOTION_IDENTIFIERS_UNSTABLE")
    return ReplacementIdentifiers(snapshots[0][1], snapshots[0][2])


def identifier_hashes(identifiers: ReplacementIdentifiers) -> dict[str, str]:
    return {
        "app_id": hashlib.sha256(identifiers.app_id.encode("utf-8")).hexdigest(),
        "bundle_id": hashlib.sha256(identifiers.bundle_id.encode("utf-8")).hexdigest(),
    }


def replace_identifier_bytes(
    content: bytes,
    identifiers: ReplacementIdentifiers,
) -> tuple[bytes, dict[str, int]]:
    replacements = {
        placeholder.encode("ascii"): getattr(identifiers, target)
        .encode("utf-8")
        for placeholder, target in PLACEHOLDER_TARGETS.items()
    }
    counts = {
        placeholder: content.count(placeholder.encode("ascii"))
        for placeholder in PLACEHOLDER_TARGETS
    }
    replaced = PLACEHOLDER_PATTERN.sub(
        lambda match: replacements[match.group(0)],
        content,
    )
    return replaced, counts


def final_directory_name(app_name: str) -> str:
    value = str(app_name or "")
    if (
        not value
        or value in {".", ".."}
        or Path(value).name != value
        or "/" in value
        or "\\" in value
        or "\x00" in value
    ):
        raise UTM21Error("APPLICATION_NAME_INVALID")
    return f"{value}-git"


def select_code_url(records: Iterable[dict[str, Any]], app_name: str) -> str:
    final_directory_name(app_name)
    selected = select_exact_record(records, app_name)
    fields = selected.get("fields")
    if not isinstance(fields, dict):
        raise UTM21Error("APPLICATION_FIELDS_INVALID")
    try:
        value = _link_value(fields.get(CODE_URL_FIELD), CODE_URL_FIELD)
    except ValueError as exc:
        raise MissingCodeURL("CODE_URL_MISSING") from exc
    parse_github_repo_url(value)
    return value


def parse_branch_ref(output: str, branch: str) -> str:
    if branch not in ALLOWED_BRANCHES:
        raise UTM21Error("BRANCH_REF_INVALID")
    expected_ref = f"refs/heads/{branch}"
    rows = [line.split() for line in str(output or "").splitlines() if line.strip()]
    if (
        len(rows) != 1
        or len(rows[0]) != 2
        or rows[0][1] != expected_ref
        or re.fullmatch(r"[0-9a-f]{40}", rows[0][0]) is None
    ):
        raise UTM21Error("BRANCH_REF_INVALID")
    return rows[0][0]


class GitHubBranchZipClient:
    def __init__(
        self,
        *,
        run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        download_zip: Callable[[str, str], bytes] | None = None,
    ) -> None:
        self._run_command = run_command
        if download_zip is None:
            repository_client = GitHubRepositoryClient(run_command=run_command)
            download_zip = repository_client._download_repository_zip
        self._download_zip = download_zip

    def retrieve_branch_zip(self, repo_url: str, branch: str) -> tuple[str, bytes]:
        parse_github_repo_url(repo_url)
        if branch not in ALLOWED_BRANCHES:
            raise UTM21Error("BRANCH_REF_INVALID")
        environment = dict(os.environ)
        environment["GIT_TERMINAL_PROMPT"] = "0"
        command = [
            "/usr/bin/git",
            "ls-remote",
            "--exit-code",
            "--refs",
            "--",
            repo_url,
            f"refs/heads/{branch}",
        ]
        result = self._run_command(
            command,
            text=True,
            capture_output=True,
            check=False,
            shell=False,
            timeout=60,
            env=environment,
        )
        if result.returncode != 0:
            raise UTM21Error("BRANCH_REF_INVALID")
        commit_sha = parse_branch_ref(result.stdout, branch)
        archive = self._download_zip(repo_url, commit_sha)
        if not isinstance(archive, bytes) or not archive:
            raise UTM21Error("BRANCH_ZIP_INVALID")
        return commit_sha, archive


def extract_repository_zip(archive: bytes | Path, destination: Path) -> None:
    if isinstance(archive, Path):
        try:
            details = archive.lstat()
            if (
                not stat.S_ISREG(details.st_mode)
                or stat.S_ISLNK(details.st_mode)
                or details.st_nlink != 1
            ):
                raise UTM21Error("BRANCH_ZIP_UNSAFE")
            archive_data = archive.read_bytes()
        except OSError as exc:
            raise UTM21Error("BRANCH_ZIP_UNSAFE") from exc
    else:
        archive_data = archive
    if not isinstance(archive_data, bytes) or not archive_data:
        raise UTM21Error("BRANCH_ZIP_INVALID")
    _extract_github_repository_zip(archive_data, Path(destination))


def directory_manifest(root: Path) -> list[dict[str, object]]:
    root = Path(root)
    try:
        root_stat = root.lstat()
    except OSError as exc:
        raise UTM21Error("DIRECTORY_MANIFEST_ROOT_INVALID") from exc
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
        raise UTM21Error("DIRECTORY_MANIFEST_ROOT_INVALID")
    manifest: list[dict[str, object]] = []
    for candidate in sorted(
        root.rglob("*"), key=lambda path: path.relative_to(root).as_posix()
    ):
        try:
            candidate_stat = candidate.lstat()
        except OSError as exc:
            raise UTM21Error("DIRECTORY_ENTRY_UNSAFE") from exc
        if stat.S_ISLNK(candidate_stat.st_mode):
            raise UTM21Error("DIRECTORY_ENTRY_UNSAFE")
        if stat.S_ISDIR(candidate_stat.st_mode):
            continue
        if not stat.S_ISREG(candidate_stat.st_mode) or candidate_stat.st_nlink != 1:
            raise UTM21Error("DIRECTORY_ENTRY_UNSAFE")
        digest = hashlib.sha256()
        with candidate.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        manifest.append(
            {
                "path": candidate.relative_to(root).as_posix(),
                "size": candidate_stat.st_size,
                "sha256": digest.hexdigest(),
                "executable": bool(candidate_stat.st_mode & 0o111),
            }
        )
    if not manifest:
        raise UTM21Error("DIRECTORY_MANIFEST_EMPTY")
    return manifest


def replacement_manifest(
    root: Path,
    identifiers: ReplacementIdentifiers,
) -> tuple[list[dict[str, object]], dict[str, int]]:
    raw_manifest = directory_manifest(root)
    transformed_manifest: list[dict[str, object]] = []
    totals = {placeholder: 0 for placeholder in PLACEHOLDER_TARGETS}
    for raw_entry in raw_manifest:
        relative_path = str(raw_entry["path"])
        candidate = Path(root) / relative_path
        try:
            details = candidate.lstat()
            if (
                not stat.S_ISREG(details.st_mode)
                or stat.S_ISLNK(details.st_mode)
                or details.st_nlink != 1
            ):
                raise UTM21Error("DIRECTORY_ENTRY_UNSAFE")
            content = candidate.read_bytes()
        except OSError as exc:
            raise UTM21Error("DIRECTORY_ENTRY_UNSAFE") from exc
        transformed, counts = replace_identifier_bytes(content, identifiers)
        for placeholder, count in counts.items():
            totals[placeholder] += count
        transformed_manifest.append(
            {
                "path": relative_path,
                "size": len(transformed),
                "sha256": hashlib.sha256(transformed).hexdigest(),
                "executable": bool(details.st_mode & 0o111),
            }
        )
    return transformed_manifest, totals


def _manifests_share_structure(
    first: list[dict[str, object]],
    second: list[dict[str, object]],
) -> bool:
    return bool(first) and len(first) == len(second) and all(
        left.get("path") == right.get("path")
        and left.get("executable") == right.get("executable")
        for left, right in zip(first, second, strict=True)
    )


def _manifest_is_replacement_state(
    raw_manifest: list[dict[str, object]],
    expected_manifest: list[dict[str, object]],
    current_manifest: list[dict[str, object]],
) -> bool:
    if (
        not _manifests_share_structure(raw_manifest, expected_manifest)
        or not _manifests_share_structure(raw_manifest, current_manifest)
    ):
        return False
    return all(
        current == raw or current == expected
        for raw, expected, current in zip(
            raw_manifest,
            expected_manifest,
            current_manifest,
            strict=True,
        )
    )


@dataclass(frozen=True)
class RunLedger:
    path: Path
    run_digest: str

    @classmethod
    def for_run(cls, runtime_root: Path, run_id: str) -> "RunLedger":
        value = str(run_id or "")
        if not value or any(character in value for character in "\r\n\x00"):
            raise UTM21Error("RUN_ID_INVALID")
        root = Path(runtime_root)
        if root.exists() and (root.is_symlink() or not root.is_dir()):
            raise UTM21Error("RUN_LEDGER_ROOT_UNSAFE")
        root.mkdir(mode=0o700, parents=True, exist_ok=True)
        root.chmod(0o700)
        digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        return cls(path=root / f"{digest}.json", run_digest=digest)

    def read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        try:
            details = self.path.lstat()
            if (
                not stat.S_ISREG(details.st_mode)
                or stat.S_ISLNK(details.st_mode)
                or details.st_nlink != 1
            ):
                raise UTM21Error("RUN_LEDGER_UNSAFE")
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise UTM21Error("RUN_LEDGER_INVALID") from exc
        if not isinstance(payload, dict) or payload.get("run_digest") != self.run_digest:
            raise UTM21Error("RUN_LEDGER_INVALID")
        return payload

    def write(self, state: dict[str, Any]) -> None:
        payload = {**state, "run_digest": self.run_digest}
        self.path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{self.path.name}.",
            suffix=".tmp",
            dir=self.path.parent,
        )
        temporary = Path(temporary_name)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                descriptor = -1
                json.dump(payload, stream, ensure_ascii=False, sort_keys=True)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            self.path.chmod(0o600)
        finally:
            if descriptor >= 0:
                os.close(descriptor)
            temporary.unlink(missing_ok=True)


@contextmanager
def materialized_run_archive(
    archive: bytes,
    ledger: RunLedger,
) -> Iterator[Path]:
    if not isinstance(archive, bytes) or not archive:
        raise UTM21Error("BRANCH_ZIP_INVALID")
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".utm-21-{ledger.run_digest[:16]}-",
        suffix=".zip",
        dir=ledger.path.parent,
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(archive)
            stream.flush()
            os.fsync(stream.fileno())
        yield temporary
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)


def archive_manifest(archive: Path, ledger: RunLedger) -> list[dict[str, object]]:
    with tempfile.TemporaryDirectory(
        prefix=f".utm-21-proof-{ledger.run_digest[:16]}-",
        dir=ledger.path.parent,
    ) as proof_root:
        proof = Path(proof_root) / "source"
        extract_repository_zip(archive, proof)
        return directory_manifest(proof)


def _source_state_matches(
    state: dict[str, Any],
    *,
    app_name: str,
    branch: str,
    commit_sha: str,
    host_directory: str,
) -> bool:
    return (
        state.get("app_name") == app_name
        and state.get("branch") == branch
        and state.get("commit_sha") == commit_sha
        and state.get("host_directory") == host_directory
    )


def install_host_code(
    *,
    archive: bytes,
    shared_root: Path,
    app_name: str,
    run_id: str,
    branch: str,
    commit_sha: str,
    ledger: RunLedger,
) -> tuple[Path, list[dict[str, object]]]:
    name = final_directory_name(app_name)
    if branch not in ALLOWED_BRANCHES or re.fullmatch(r"[0-9a-f]{40}", commit_sha) is None:
        raise UTM21Error("SOURCE_IDENTITY_INVALID")
    if hashlib.sha256(str(run_id).encode("utf-8")).hexdigest() != ledger.run_digest:
        raise UTM21Error("RUN_LEDGER_MISMATCH")
    shared_root = Path(shared_root)
    try:
        root_stat = shared_root.lstat()
    except OSError as exc:
        raise UTM21Error("SHARED_ROOT_UNSAFE") from exc
    if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
        raise UTM21Error("SHARED_ROOT_UNSAFE")
    target = shared_root / name
    temporary = shared_root / f".utm-21-{ledger.run_digest[:16]}-{name}"
    state = ledger.read()
    if target.exists() or target.is_symlink():
        if target.is_symlink() or not target.is_dir():
            raise UTM21Error("HOST_TARGET_CONFLICT")
        current = directory_manifest(target)
        source_matches = _source_state_matches(
            state,
            app_name=app_name,
            branch=branch,
            commit_sha=commit_sha,
            host_directory=name,
        )
        if source_matches and state.get("host_manifest") == current:
            return target, current
        result_unknown = (
            source_matches
            and "host_manifest" not in state
            and state.get("host_temporary") == temporary.name
            and not temporary.exists()
            and not temporary.is_symlink()
        )
        if not result_unknown:
            raise UTM21Error("HOST_TARGET_CONFLICT")
        with materialized_run_archive(archive, ledger) as archive_path:
            expected = archive_manifest(archive_path, ledger)
        if current != expected:
            raise UTM21Error("HOST_TARGET_CONFLICT")
        ledger.write({**state, "host_temporary": "", "host_manifest": current})
        return target, current

    if temporary.exists() or temporary.is_symlink():
        if (
            temporary.is_symlink()
            or not temporary.is_dir()
            or state.get("host_temporary") != temporary.name
            or not _source_state_matches(
                state,
                app_name=app_name,
                branch=branch,
                commit_sha=commit_sha,
                host_directory=name,
            )
        ):
            raise UTM21Error("HOST_TEMPORARY_CONFLICT")
        shutil.rmtree(temporary)
    base_state = {
        "app_name": app_name,
        "branch": branch,
        "commit_sha": commit_sha,
        "host_directory": name,
        "host_temporary": temporary.name,
    }
    ledger.write(base_state)
    try:
        with materialized_run_archive(archive, ledger) as archive_path:
            extract_repository_zip(archive_path, temporary)
            manifest = directory_manifest(temporary)
            os.replace(temporary, target)
            if directory_manifest(target) != manifest:
                raise UTM21Error("HOST_MANIFEST_MISMATCH")
    except BaseException:
        if temporary.is_dir() and not temporary.is_symlink():
            shutil.rmtree(temporary)
        raise
    ledger.write({**base_state, "host_temporary": "", "host_manifest": manifest})
    return target, manifest


class GuestTransport(Protocol):
    def verify_identity(self) -> None: ...
    def path_state(self, path: str) -> str: ...
    def copy_tree(self, source: Path, temporary_path: str) -> None: ...
    def manifest(self, remote_path: str) -> list[dict[str, object]]: ...
    def replace_identifiers(
        self,
        remote_path: str,
        identifiers: ReplacementIdentifiers,
        raw_manifest: list[dict[str, object]],
        expected_manifest: list[dict[str, object]],
    ) -> dict[str, int]: ...
    def promote(self, temporary_path: str, final_path: str) -> None: ...
    def remove_owned_temporary(self, remote_path: str) -> None: ...


REMOTE_MANIFEST_SCRIPT = r'''
# UTM21_MANIFEST
import hashlib
import json
import os
import stat
import sys
from pathlib import Path

root = Path(sys.argv[1])
root_stat = root.lstat()
if not stat.S_ISDIR(root_stat.st_mode) or stat.S_ISLNK(root_stat.st_mode):
    raise SystemExit(81)
manifest = []
for candidate in sorted(root.rglob('*'), key=lambda path: path.relative_to(root).as_posix()):
    details = candidate.lstat()
    if stat.S_ISLNK(details.st_mode):
        raise SystemExit(82)
    if stat.S_ISDIR(details.st_mode):
        continue
    if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
        raise SystemExit(83)
    digest = hashlib.sha256()
    with candidate.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    manifest.append({
        'path': candidate.relative_to(root).as_posix(),
        'size': details.st_size,
        'sha256': digest.hexdigest(),
        'executable': bool(details.st_mode & 0o111),
    })
if not manifest:
    raise SystemExit(84)
print(json.dumps(manifest, ensure_ascii=False, sort_keys=True))
'''.strip()


REMOTE_REPLACEMENT_SCRIPT = r'''
# UTM21_REPLACE_IDENTIFIERS
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path

placeholders = {
    b'5372311233': 'app_id',
    b'jltest.test.test': 'bundle_id',
    b'uildbet.brovaxtere': 'bundle_id',
    b'xycoins.2027.test': 'bundle_id',
    b'org.toolbox.fastcleaner': 'bundle_id',
}
pattern = re.compile(b'|'.join(re.escape(value) for value in placeholders))
payload = json.load(sys.stdin)
if not isinstance(payload, dict) or set(payload) != {
    'app_id', 'bundle_id', 'raw_manifest', 'expected_manifest'
}:
    raise SystemExit(91)
app_id = payload['app_id']
bundle_id = payload['bundle_id']
if not isinstance(app_id, str) or re.fullmatch(r'[0-9]+', app_id) is None:
    raise SystemExit(92)
if not isinstance(bundle_id, str) or re.fullmatch(
    r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+', bundle_id
) is None:
    raise SystemExit(93)
if app_id in {value.decode('ascii') for value in placeholders}:
    raise SystemExit(94)
if bundle_id in {value.decode('ascii') for value in placeholders}:
    raise SystemExit(95)
replacements = {
    source: payload[target].encode('utf-8') for source, target in placeholders.items()
}

def manifest_index(value):
    if not isinstance(value, list) or not value:
        raise SystemExit(96)
    result = {}
    for entry in value:
        if not isinstance(entry, dict):
            raise SystemExit(96)
        relative = entry.get('path')
        path = Path(relative) if isinstance(relative, str) else Path('.')
        if (
            not isinstance(relative, str)
            or not relative
            or path.is_absolute()
            or path.as_posix() != relative
            or any(part in {'', '.', '..'} for part in path.parts)
            or relative in result
            or not isinstance(entry.get('size'), int)
            or entry['size'] < 0
            or re.fullmatch(r'[0-9a-f]{64}', str(entry.get('sha256') or '')) is None
            or not isinstance(entry.get('executable'), bool)
        ):
            raise SystemExit(96)
        result[relative] = entry
    return result

raw_by_path = manifest_index(payload['raw_manifest'])
expected_by_path = manifest_index(payload['expected_manifest'])
if set(raw_by_path) != set(expected_by_path):
    raise SystemExit(97)
for relative in raw_by_path:
    if raw_by_path[relative]['executable'] != expected_by_path[relative]['executable']:
        raise SystemExit(97)

root = Path(sys.argv[1])
root_details = root.lstat()
if not stat.S_ISDIR(root_details.st_mode) or stat.S_ISLNK(root_details.st_mode):
    raise SystemExit(98)
candidates = []
for candidate in sorted(root.rglob('*'), key=lambda path: path.relative_to(root).as_posix()):
    details = candidate.lstat()
    if stat.S_ISLNK(details.st_mode):
        raise SystemExit(99)
    if stat.S_ISDIR(details.st_mode):
        continue
    if not stat.S_ISREG(details.st_mode) or details.st_nlink != 1:
        raise SystemExit(100)
    candidates.append((candidate, details))
if {candidate.relative_to(root).as_posix() for candidate, _details in candidates} != set(raw_by_path):
    raise SystemExit(101)

counts = {source.decode('ascii'): 0 for source in placeholders}
for candidate, details in candidates:
    relative = candidate.relative_to(root).as_posix()
    content = candidate.read_bytes()
    current = {
        'path': relative,
        'size': len(content),
        'sha256': hashlib.sha256(content).hexdigest(),
        'executable': bool(details.st_mode & 0o111),
    }
    expected = expected_by_path[relative]
    if current == expected:
        continue
    if current != raw_by_path[relative]:
        raise SystemExit(102)
    per_file = {
        source.decode('ascii'): content.count(source) for source in placeholders
    }
    transformed = pattern.sub(lambda match: replacements[match.group(0)], content)
    transformed_entry = {
        'path': relative,
        'size': len(transformed),
        'sha256': hashlib.sha256(transformed).hexdigest(),
        'executable': bool(details.st_mode & 0o111),
    }
    if transformed_entry != expected:
        raise SystemExit(103)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix='.utm-21-replace-', dir=candidate.parent
    )
    temporary = Path(temporary_name)
    try:
        os.fchmod(descriptor, stat.S_IMODE(details.st_mode))
        with os.fdopen(descriptor, 'wb') as stream:
            descriptor = -1
            stream.write(transformed)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, candidate)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        temporary.unlink(missing_ok=True)
    for placeholder, count in per_file.items():
        counts[placeholder] += count
print(json.dumps(counts, ensure_ascii=False, sort_keys=True))
'''.strip()


class SSHGuestTransport:
    def __init__(
        self,
        vm_user: str,
        vm_ip: str,
        *,
        run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
        environment_factory: Callable[[], dict[str, str]] = password_environment,
    ) -> None:
        if not re.fullmatch(r"[a-z]{4}", vm_user):
            raise UTM21Error("VM_USER_INVALID")
        try:
            ipaddress.ip_address(vm_ip)
        except ValueError as exc:
            raise UTM21Error("VM_IP_INVALID") from exc
        self.vm_user = vm_user
        self.vm_ip = vm_ip
        self.home = f"/Users/{vm_user}"
        self.downloads = f"{self.home}/Downloads"
        self._run_command = run_command
        self._environment_factory = environment_factory

    def _run(
        self,
        command: list[str],
        *,
        timeout: int = 120,
        input_text: str | None = None,
    ) -> str:
        kwargs: dict[str, Any] = {
            "text": True,
            "capture_output": True,
            "check": False,
            "shell": False,
            "timeout": timeout,
            "env": self._environment_factory(),
        }
        if input_text is not None:
            kwargs["input"] = input_text
        result = self._run_command(command, **kwargs)
        if result.returncode != 0:
            raise UTM21Error("GUEST_COMMAND_FAILED")
        return str(result.stdout or "")

    def _ssh(
        self,
        remote_command: str,
        *,
        timeout: int = 120,
        input_text: str | None = None,
    ) -> str:
        return self._run(
            ssh_args(self.vm_user, self.vm_ip, connect_timeout=5) + [remote_command],
            timeout=timeout,
            input_text=input_text,
        )

    def _require_download_path(self, remote_path: str, *, temporary: bool = False) -> None:
        path = Path(remote_path)
        if path.parent.as_posix() != self.downloads or not path.name:
            raise UTM21Error("GUEST_PATH_INVALID")
        if temporary and re.fullmatch(r"[.]utm-21-[0-9a-f]{16}-.+", path.name) is None:
            raise UTM21Error("GUEST_TEMPORARY_INVALID")

    def verify_identity(self) -> None:
        user = shlex.quote(self.vm_user)
        home = shlex.quote(self.home)
        downloads = shlex.quote(self.downloads)
        remote = " && ".join(
            (
                f"test \"$(/usr/bin/id -un)\" = {user}",
                f"test \"$HOME\" = {home}",
                f"test -d {downloads}",
                f"test ! -L {downloads}",
            )
        )
        self._ssh("/bin/zsh -lc " + shlex.quote(remote), timeout=30)

    def path_state(self, path: str) -> str:
        self._require_download_path(path)
        quoted = shlex.quote(path)
        script = (
            f"if test ! -e {quoted} && test ! -L {quoted}; then "
            "printf 'UTM21_PATH_STATE=missing\\n'; "
            f"elif test -L {quoted}; then printf 'UTM21_PATH_STATE=symlink\\n'; "
            f"elif test -d {quoted}; then printf 'UTM21_PATH_STATE=directory\\n'; "
            "else printf 'UTM21_PATH_STATE=other\\n'; fi"
        )
        output = self._ssh("/bin/zsh -lc " + shlex.quote(script), timeout=30).strip()
        state = output.rsplit("=", 1)[-1]
        if state not in {"missing", "symlink", "directory", "other"}:
            raise UTM21Error("GUEST_PATH_STATE_INVALID")
        return state

    def copy_tree(self, source: Path, temporary_path: str) -> None:
        self._require_download_path(temporary_path, temporary=True)
        if not source.is_dir() or source.is_symlink():
            raise UTM21Error("HOST_SOURCE_INVALID")
        command = scp_args(
            self.vm_user,
            self.vm_ip,
            source,
            shlex.quote(temporary_path),
            connect_timeout=8,
        )
        command.insert(2, "-r")
        self._run(command, timeout=1800)

    def manifest(self, remote_path: str) -> list[dict[str, object]]:
        self._require_download_path(remote_path)
        command = (
            "/usr/bin/python3 -c "
            + shlex.quote(REMOTE_MANIFEST_SCRIPT)
            + " "
            + shlex.quote(remote_path)
        )
        output = self._ssh(command, timeout=300)
        try:
            payload = json.loads(output)
        except json.JSONDecodeError as exc:
            raise UTM21Error("GUEST_MANIFEST_INVALID") from exc
        if not isinstance(payload, list) or not payload:
            raise UTM21Error("GUEST_MANIFEST_INVALID")
        return payload

    def replace_identifiers(
        self,
        remote_path: str,
        identifiers: ReplacementIdentifiers,
        raw_manifest: list[dict[str, object]],
        expected_manifest: list[dict[str, object]],
    ) -> dict[str, int]:
        self._require_download_path(remote_path)
        if not _manifests_share_structure(raw_manifest, expected_manifest):
            raise UTM21Error("REPLACEMENT_MANIFEST_INVALID")
        payload = json.dumps(
            {
                "app_id": identifiers.app_id,
                "bundle_id": identifiers.bundle_id,
                "raw_manifest": raw_manifest,
                "expected_manifest": expected_manifest,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        command = (
            "/usr/bin/python3 -c "
            + shlex.quote(REMOTE_REPLACEMENT_SCRIPT)
            + " "
            + shlex.quote(remote_path)
        )
        output = self._ssh(command, timeout=1800, input_text=payload)
        try:
            result = json.loads(output)
        except json.JSONDecodeError as exc:
            raise UTM21Error("GUEST_REPLACEMENT_RESULT_INVALID") from exc
        if (
            not isinstance(result, dict)
            or set(result) != set(PLACEHOLDER_TARGETS)
            or any(
                not isinstance(value, int) or isinstance(value, bool) or value < 0
                for value in result.values()
            )
        ):
            raise UTM21Error("GUEST_REPLACEMENT_RESULT_INVALID")
        return result

    def promote(self, temporary_path: str, final_path: str) -> None:
        self._require_download_path(temporary_path, temporary=True)
        self._require_download_path(final_path)
        temporary = shlex.quote(temporary_path)
        final = shlex.quote(final_path)
        script = " && ".join(
            (
                f"test -d {temporary}",
                f"test ! -L {temporary}",
                f"test ! -e {final}",
                f"test ! -L {final}",
                f"/bin/mv -- {temporary} {final}",
            )
        )
        self._ssh("/bin/zsh -lc " + shlex.quote(script), timeout=60)

    def remove_owned_temporary(self, remote_path: str) -> None:
        self._require_download_path(remote_path, temporary=True)
        quoted = shlex.quote(remote_path)
        script = (
            f"test ! -L {quoted} && test -d {quoted} && /bin/rm -rf -- {quoted}"
        )
        self._ssh("/bin/zsh -lc " + shlex.quote(script), timeout=60)


def deliver_guest_code(
    *,
    source: Path,
    app_name: str,
    vm_user: str,
    vm_ip: str,
    run_id: str,
    commit_sha: str,
    ledger: RunLedger,
    transport: GuestTransport,
    accepted_final_manifest: list[dict[str, object]] | None = None,
) -> dict[str, str]:
    name = final_directory_name(app_name)
    if not re.fullmatch(r"[a-z]{4}", vm_user):
        raise UTM21Error("VM_USER_INVALID")
    try:
        ipaddress.ip_address(vm_ip)
    except ValueError as exc:
        raise UTM21Error("VM_IP_INVALID") from exc
    if hashlib.sha256(str(run_id).encode("utf-8")).hexdigest() != ledger.run_digest:
        raise UTM21Error("RUN_LEDGER_MISMATCH")
    source = Path(source)
    if source.name != name:
        raise UTM21Error("HOST_SOURCE_INVALID")
    host_manifest = directory_manifest(source)
    if accepted_final_manifest is not None and not _manifests_share_structure(
        host_manifest, accepted_final_manifest
    ):
        raise UTM21Error("REPLACEMENT_MANIFEST_INVALID")
    state = ledger.read()
    if (
        state.get("app_name") != app_name
        or state.get("commit_sha") != commit_sha
        or state.get("host_directory") != name
        or state.get("host_manifest") != host_manifest
    ):
        raise UTM21Error("HOST_SOURCE_UNBOUND")
    final_path = f"/Users/{vm_user}/Downloads/{name}"
    temporary_path = (
        f"/Users/{vm_user}/Downloads/.utm-21-{ledger.run_digest[:16]}-{name}"
    )
    transport.verify_identity()
    final_state = transport.path_state(final_path)
    if final_state == "directory":
        guest_manifest = transport.manifest(final_path)
        target_bound = (
            state.get("vm_user") == vm_user
            and state.get("vm_ip") == vm_ip
            and state.get("guest_path") == final_path
        )
        exact_raw = (
            target_bound
            and state.get("guest_manifest") == host_manifest
            and guest_manifest == host_manifest
        )
        if exact_raw:
            return {"guest_path": final_path, "manifest_match": "exact"}
        replacement_bound = (
            accepted_final_manifest is not None
            and target_bound
            and state.get("replacement_status") in {"running", "verified"}
            and state.get("expected_guest_manifest") == accepted_final_manifest
        )
        if replacement_bound and guest_manifest == accepted_final_manifest:
            return {
                "guest_path": final_path,
                "manifest_match": "replacement_exact",
            }
        if (
            replacement_bound
            and _manifest_is_replacement_state(
                host_manifest,
                accepted_final_manifest,
                guest_manifest,
            )
        ):
            return {
                "guest_path": final_path,
                "manifest_match": "replacement_partial",
            }
        result_unknown = (
            target_bound
            and "guest_manifest" not in state
            and state.get("guest_temporary") == temporary_path
            and guest_manifest == host_manifest
            and transport.path_state(temporary_path) == "missing"
        )
        if not result_unknown:
            raise UTM21Error("GUEST_TARGET_CONFLICT")
        ledger.write(
            {
                **state,
                "guest_temporary": "",
                "guest_manifest": guest_manifest,
            }
        )
        return {"guest_path": final_path, "manifest_match": "exact"}
    if final_state != "missing":
        raise UTM21Error("GUEST_TARGET_CONFLICT")
    temporary_state = transport.path_state(temporary_path)
    if temporary_state != "missing":
        if not (
            temporary_state == "directory"
            and state.get("guest_temporary") == temporary_path
            and state.get("vm_user") == vm_user
            and state.get("vm_ip") == vm_ip
        ):
            raise UTM21Error("GUEST_TEMPORARY_CONFLICT")
        transport.remove_owned_temporary(temporary_path)
    ledger.write(
        {
            **state,
            "vm_user": vm_user,
            "vm_ip": vm_ip,
            "guest_path": final_path,
            "guest_temporary": temporary_path,
        }
    )
    transport.copy_tree(source, temporary_path)
    copied_manifest = transport.manifest(temporary_path)
    if copied_manifest != host_manifest:
        transport.remove_owned_temporary(temporary_path)
        raise UTM21Error("GUEST_MANIFEST_MISMATCH")
    transport.promote(temporary_path, final_path)
    fresh_manifest = transport.manifest(final_path)
    if fresh_manifest != host_manifest:
        raise UTM21Error("GUEST_MANIFEST_MISMATCH")
    final_state_payload = {
        **ledger.read(),
        "vm_user": vm_user,
        "vm_ip": vm_ip,
        "guest_path": final_path,
        "guest_temporary": "",
        "guest_manifest": fresh_manifest,
    }
    ledger.write(final_state_payload)
    return {"guest_path": final_path, "manifest_match": "exact"}


def _replacement_counts_valid(counts: dict[str, int]) -> bool:
    return set(counts) == set(PLACEHOLDER_TARGETS) and all(
        isinstance(value, int) and not isinstance(value, bool) and value >= 0
        for value in counts.values()
    )


def apply_guest_replacements(
    *,
    guest_path: str,
    raw_manifest: list[dict[str, object]],
    expected_manifest: list[dict[str, object]],
    replacement_counts: dict[str, int],
    identifiers: ReplacementIdentifiers,
    vm_user: str,
    vm_ip: str,
    ledger: RunLedger,
    transport: GuestTransport,
) -> dict[str, str]:
    if (
        guest_path != f"/Users/{vm_user}/Downloads/{Path(guest_path).name}"
        or not re.fullmatch(r"[a-z]{4}", vm_user)
        or not _manifests_share_structure(raw_manifest, expected_manifest)
        or not _replacement_counts_valid(replacement_counts)
    ):
        raise UTM21Error("REPLACEMENT_CONTEXT_INVALID")
    try:
        ipaddress.ip_address(vm_ip)
    except ValueError as exc:
        raise UTM21Error("REPLACEMENT_CONTEXT_INVALID") from exc

    hashes = identifier_hashes(identifiers)
    transport.verify_identity()
    state = ledger.read()
    if not (
        state.get("vm_user") == vm_user
        and state.get("vm_ip") == vm_ip
        and state.get("guest_path") == guest_path
    ):
        raise UTM21Error("REPLACEMENT_CONTEXT_INVALID")
    current_manifest = transport.manifest(guest_path)
    verified = (
        state.get("replacement_status") == "verified"
        and state.get("identifier_hashes") == hashes
        and state.get("replacement_counts") == replacement_counts
        and state.get("expected_guest_manifest") == expected_manifest
        and state.get("guest_manifest") == expected_manifest
        and current_manifest == expected_manifest
    )
    if verified:
        return {
            "guest_path": guest_path,
            "manifest_match": "exact",
            "replacement_status": "verified",
        }

    running = state.get("replacement_status") == "running"
    if running and not (
        state.get("identifier_hashes") == hashes
        and state.get("replacement_counts") == replacement_counts
        and state.get("expected_guest_manifest") == expected_manifest
    ):
        raise UTM21Error("REPLACEMENT_CONTEXT_CONFLICT")
    if not running and not (
        state.get("guest_manifest") == raw_manifest
        and current_manifest == raw_manifest
        and not state.get("replacement_status")
    ):
        raise UTM21Error("REPLACEMENT_CONTEXT_CONFLICT")
    if running and not _manifest_is_replacement_state(
        raw_manifest,
        expected_manifest,
        current_manifest,
    ):
        raise UTM21Error("REPLACEMENT_CONTENT_CONFLICT")

    ledger.write(
        {
            **state,
            "replacement_status": "running",
            "identifier_hashes": hashes,
            "replacement_counts": replacement_counts,
            "expected_guest_manifest": expected_manifest,
        }
    )
    applied_counts = transport.replace_identifiers(
        guest_path,
        identifiers,
        raw_manifest,
        expected_manifest,
    )
    if not _replacement_counts_valid(applied_counts) or any(
        applied_counts[placeholder] > replacement_counts[placeholder]
        for placeholder in PLACEHOLDER_TARGETS
    ):
        raise UTM21Error("GUEST_REPLACEMENT_RESULT_INVALID")
    fresh_manifest = transport.manifest(guest_path)
    if fresh_manifest != expected_manifest:
        raise UTM21Error("GUEST_REPLACEMENT_MANIFEST_MISMATCH")
    ledger.write(
        {
            **ledger.read(),
            "replacement_status": "verified",
            "identifier_hashes": hashes,
            "replacement_counts": replacement_counts,
            "expected_guest_manifest": expected_manifest,
            "guest_manifest": fresh_manifest,
        }
    )
    return {
        "guest_path": guest_path,
        "manifest_match": "exact",
        "replacement_status": "verified",
    }


def verify_run_context(
    run: dict[str, Any] | None,
    *,
    run_id: str,
    chat_id: str,
    app_name: str,
    vm_name: str,
    vm_ip: str,
    local_host: str,
) -> None:
    final_directory_name(app_name)
    if not re.fullmatch(r"[a-z]{4}", vm_name):
        raise UTM21Error("RUN_CONTEXT_INVALID")
    try:
        ipaddress.ip_address(vm_ip)
    except ValueError as exc:
        raise UTM21Error("RUN_CONTEXT_INVALID") from exc
    if not isinstance(run, dict):
        raise UTM21Error("RUN_CONTEXT_INVALID")
    submission = run.get("submission_data")
    submission = submission if isinstance(submission, dict) else {}
    run_host = str(submission.get("host_machine") or run.get("host_machine") or "")
    stored_ip = str(submission.get("vm_ip") or run.get("vm_ip") or "")
    lifecycle = run.get("lifecycle")
    lifecycle = lifecycle if isinstance(lifecycle, dict) else {}
    attempts = run.get("skill_attempts")
    attempts = attempts if isinstance(attempts, list) else []
    p8_verified = any(
        isinstance(attempt, dict)
        and attempt.get("skill") == "utm-p8"
        and attempt.get("status") == "succeeded"
        for attempt in attempts
    )
    open_utm21 = [
        attempt
        for attempt in attempts
        if isinstance(attempt, dict)
        and attempt.get("skill") == "utm-21"
        and attempt.get("status") == "started"
        and not attempt.get("finished_at")
    ]
    requested = run.get("requested_skills")
    requested_valid = requested is None or (
        isinstance(requested, list) and "utm-21" in requested
    )
    if not (
        run.get("id") == run_id
        and str(run.get("chat_id") or "") == chat_id
        and str(run.get("project_chat_id") or "") == chat_id
        and str(run.get("app_name") or "") == app_name
        and str(run.get("vm_name") or "") == vm_name
        and run_host == local_host
        and bool(local_host)
        and (not stored_ip or stored_ip == vm_ip)
        and lifecycle.get("started_at")
        and not lifecycle.get("finished_at")
        and not lifecycle.get("outcome")
        and p8_verified
        and len(open_utm21) == 1
        and requested_valid
    ):
        raise UTM21Error("RUN_CONTEXT_INVALID")


def selected_branch_url(repo_url: str, branch: str) -> str:
    owner, repo = parse_github_repo_url(repo_url)
    if branch not in ALLOWED_BRANCHES:
        raise UTM21Error("BRANCH_REF_INVALID")
    return (
        f"https://github.com/{urllib.parse.quote(owner, safe='')}/"
        f"{urllib.parse.quote(repo, safe='')}/tree/{urllib.parse.quote(branch, safe='')}"
    )


def open_host_browser(
    url: str,
    *,
    run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> None:
    parsed = urllib.parse.urlsplit(url)
    if (
        parsed.scheme != "https"
        or parsed.hostname != "github.com"
        or parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise UTM21Error("BROWSER_URL_INVALID")
    result = run_command(
        ["/usr/bin/open", url],
        text=True,
        capture_output=True,
        check=False,
        shell=False,
        timeout=30,
    )
    if result.returncode != 0:
        raise UTM21Error("BROWSER_OPEN_FAILED")


class BotCommandClient:
    def __init__(
        self,
        *,
        project_root: Path = PROJECT_ROOT,
        run_command: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self.project_root = Path(project_root)
        self._run_command = run_command
        self.entry = self.project_root / "services" / "feishu_bot.py"

    def _run(
        self,
        mode: str,
        arguments: list[str],
        *,
        timeout: int = 120,
    ) -> subprocess.CompletedProcess[str]:
        return self._run_command(
            [sys.executable, str(self.entry), mode, *arguments],
            cwd=self.project_root,
            text=True,
            capture_output=True,
            check=False,
            shell=False,
            timeout=timeout,
        )

    def choose_branch(self, run_id: str, chat_id: str, timeout_seconds: int) -> str:
        notified = self._run(
            "notify-code-branch",
            ["--run-id", run_id, "--chat-id", chat_id],
        )
        if notified.returncode != 0:
            raise UTM21Error("BRANCH_CARD_FAILED")
        waited = self._run(
            "wait-decision",
            [
                "--run-id",
                run_id,
                "--decision-kind",
                "code_branch",
                "--timeout-seconds",
                str(timeout_seconds),
            ],
            timeout=max(30, timeout_seconds + 30),
        )
        branch = str(waited.stdout or "").strip()
        if waited.returncode != 0 or branch not in ALLOWED_BRANCHES:
            raise UTM21Error("BRANCH_DECISION_FAILED")
        return branch

    def report_missing_code_url(self, run_id: str, chat_id: str) -> None:
        failed = self._run(
            "skill-failure",
            [
                "--run-id",
                run_id,
                "--chat-id",
                chat_id,
                "--skill",
                "utm-21",
                "--stage",
                "code-url",
            ],
        )
        if failed.returncode != 0:
            raise UTM21Error("FAULT_NOTIFICATION_FAILED")
        notified = self._run(
            "notify-fault",
            [
                "--run-id",
                run_id,
                "--chat-id",
                chat_id,
                "--stage",
                "code-url",
                "--fault",
                "代码 URL 缺失",
                "--suggested-action",
                "补充当前应用的代码 URL 后重试 utm-21",
                "--failure-action",
                "停止当前流程",
                "--retry-count",
                "3",
                "--completed-steps",
                "run-context",
                "--evidence",
                "CODE_URL_READ=missing_after_3",
                "--recovery-skill",
                "utm-21",
                "--recovery-attempts",
                "3",
                "--recovery-actions",
                "three exact Feishu OpenAPI field reads",
                "--recovery-result",
                "unrepairable",
                "--unrepairable",
            ],
        )
        if notified.returncode != 0:
            raise UTM21Error("FAULT_NOTIFICATION_FAILED")


def execute_workflow(
    *,
    run: dict[str, Any] | None,
    run_id: str,
    chat_id: str,
    app_name: str,
    vm_name: str,
    vm_ip: str,
    local_host: str,
    shared_root: Path,
    runtime_root: Path,
    records_loader: Callable[[], list[dict[str, Any]]],
    browser_opener: Callable[[str], None],
    branch_selector: Any,
    zip_client: Any,
    guest_transport: GuestTransport,
    notion_api: Any,
    sleeper: Callable[[float], None] = time.sleep,
    decision_timeout_seconds: int = 3600,
) -> dict[str, str]:
    verify_run_context(
        run,
        run_id=run_id,
        chat_id=chat_id,
        app_name=app_name,
        vm_name=vm_name,
        vm_ip=vm_ip,
        local_host=local_host,
    )
    code_url = ""
    missing: MissingCodeURL | None = None
    for delay in (0, 5, 10):
        sleeper(delay)
        try:
            code_url = select_code_url(records_loader(), app_name)
            missing = None
            break
        except MissingCodeURL as exc:
            missing = exc
    if missing is not None:
        branch_selector.report_missing_code_url(run_id, chat_id)
        raise missing
    browser_opener(code_url)
    branch = branch_selector.choose_branch(
        run_id, chat_id, decision_timeout_seconds
    )
    if branch not in ALLOWED_BRANCHES:
        raise UTM21Error("BRANCH_DECISION_INVALID")
    browser_opener(selected_branch_url(code_url, branch))
    commit_sha, archive = zip_client.retrieve_branch_zip(code_url, branch)
    ledger = RunLedger.for_run(runtime_root, run_id)
    host_path, host_manifest = install_host_code(
        archive=archive,
        shared_root=shared_root,
        app_name=app_name,
        run_id=run_id,
        branch=branch,
        commit_sha=commit_sha,
        ledger=ledger,
    )
    identifiers = load_notion_identifiers(
        notion_api,
        parent_title=local_host,
        page_title=f"{app_name}-{vm_name}",
        app_name=app_name,
        vm_user=vm_name,
    )
    expected_manifest, replacement_counts = replacement_manifest(
        host_path,
        identifiers,
    )
    delivered = deliver_guest_code(
        source=host_path,
        app_name=app_name,
        vm_user=vm_name,
        vm_ip=vm_ip,
        run_id=run_id,
        commit_sha=commit_sha,
        ledger=ledger,
        transport=guest_transport,
        accepted_final_manifest=expected_manifest,
    )
    replaced = apply_guest_replacements(
        guest_path=delivered["guest_path"],
        raw_manifest=host_manifest,
        expected_manifest=expected_manifest,
        replacement_counts=replacement_counts,
        identifiers=identifiers,
        vm_user=vm_name,
        vm_ip=vm_ip,
        ledger=ledger,
        transport=guest_transport,
    )
    return {
        "branch": branch,
        "host_directory": host_path.name,
        **replaced,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare one Feishu-selected GitHub branch for UTM-21."
    )
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--chat-id", required=True)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--vm-name", required=True)
    parser.add_argument("--vm-ip", required=True)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--timeout-seconds", type=int, default=3600)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    print("开始执行：utm-21")
    try:
        if args.timeout_seconds <= 0:
            raise UTM21Error("TIMEOUT_INVALID")
        config = feishu_bot.load_config()
        local_host = str(config.submission_host_machine or "").strip()
        run = feishu_bot.find_run(args.run_id)
        app_id, app_secret = load_credentials(PROJECT_ROOT / ".env")
        location = parse_base_url(args.base_url)
        client = FeishuClient(app_id, app_secret)
        execute_workflow(
            run=run,
            run_id=args.run_id,
            chat_id=args.chat_id,
            app_name=args.app_name,
            vm_name=args.vm_name,
            vm_ip=args.vm_ip,
            local_host=local_host,
            shared_root=SHARED_DIR,
            runtime_root=PROJECT_ROOT / "runtime" / "utm-21",
            records_loader=lambda: client.list_records(location),
            browser_opener=open_host_browser,
            branch_selector=BotCommandClient(),
            zip_client=GitHubBranchZipClient(),
            guest_transport=SSHGuestTransport(args.vm_name, args.vm_ip),
            notion_api=api_from_env(),
            decision_timeout_seconds=args.timeout_seconds,
        )
    except MissingCodeURL:
        print("执行报错：utm-21；CODE_URL_MISSING")
        return 2
    except (UTM21Error, ValueError, RuntimeError, subprocess.TimeoutExpired):
        print("执行报错：utm-21；UTM_21_FAILED")
        return 2
    print("执行成功：utm-21；UTM_21=verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
