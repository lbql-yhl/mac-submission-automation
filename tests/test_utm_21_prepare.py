#!/usr/bin/env python3
from __future__ import annotations

import io
import hashlib
import json
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from scripts import utm_21_prepare


REPO_URL = "https://github.com/acme/example-repo"
APP_IDENTIFIER = "1234567890"
BUNDLE_ID = "com.example.production"
PROJECT_CHAT = "project-chat"


def record(app_name: str, code_url: object) -> dict:
    return {
        "record_id": f"record-{app_name}",
        "fields": {
            "应用名": app_name,
            "代码 URL": code_url,
        },
    }


def repository_zip(*members: tuple[str, bytes], root: str = "repo-sha") -> bytes:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        for name, data in members:
            archive.writestr(f"{root}/{name}", data)
    return stream.getvalue()


def test_select_code_url_requires_one_exact_application_and_link() -> None:
    assert utm_21_prepare.select_code_url(
        [record("Other", "https://github.com/acme/other"), record("Demo", {"link": REPO_URL})],
        "Demo",
    ) == REPO_URL

    for records in (
        [],
        [record("Other", REPO_URL)],
        [record("Demo", REPO_URL), record("Demo", REPO_URL)],
        [record("Demo", None)],
        [record("Demo", "")],
        [record("Demo", [{"link": REPO_URL}, {"link": REPO_URL}])],
    ):
        with pytest.raises((ValueError, utm_21_prepare.UTM21Error)):
            utm_21_prepare.select_code_url(records, "Demo")


@pytest.mark.parametrize(
    "unsafe",
    (
        "http://github.com/acme/repo",
        "https://user:secret@github.com/acme/repo",
        "https://gitlab.com/acme/repo",
        "https://github.com/acme/repo/tree/main",
        "https://github.com/acme/repo?branch=main",
    ),
)
def test_select_code_url_rejects_noncanonical_or_credentialed_urls(unsafe: str) -> None:
    with pytest.raises(ValueError, match="code URL"):
        utm_21_prepare.select_code_url([record("Demo", unsafe)], "Demo")


@pytest.mark.parametrize("branch", ("main", "dev", "release"))
def test_parse_branch_ref_accepts_one_exact_commit(branch: str) -> None:
    commit = "a" * 40
    assert utm_21_prepare.parse_branch_ref(
        f"{commit}\trefs/heads/{branch}\n", branch
    ) == commit


@pytest.mark.parametrize(
    ("output", "branch"),
    (
        ("", "main"),
        (f"{'a' * 40}\trefs/heads/main\n{'b' * 40}\trefs/heads/main\n", "main"),
        (f"{'a' * 39}\trefs/heads/main\n", "main"),
        (f"{'a' * 40}\trefs/heads/dev\n", "main"),
        (f"{'a' * 40}\trefs/heads/feature\n", "feature"),
    ),
)
def test_parse_branch_ref_rejects_missing_ambiguous_or_unsupported_refs(
    output: str,
    branch: str,
) -> None:
    with pytest.raises(utm_21_prepare.UTM21Error, match="BRANCH_REF_INVALID"):
        utm_21_prepare.parse_branch_ref(output, branch)


def test_branch_zip_client_resolves_exact_ref_and_downloads_by_commit() -> None:
    commit = "c" * 40
    archive = repository_zip(("README.md", b"demo"))
    observed: dict[str, object] = {}

    def run_command(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=f"{commit}\trefs/heads/release\n",
            stderr="",
        )

    def download_zip(repo_url: str, commit_sha: str) -> bytes:
        observed["download"] = (repo_url, commit_sha)
        return archive

    client = utm_21_prepare.GitHubBranchZipClient(
        run_command=run_command,
        download_zip=download_zip,
    )
    resolved, downloaded = client.retrieve_branch_zip(REPO_URL, "release")

    assert resolved == commit
    assert downloaded == archive
    assert observed["command"] == [
        "/usr/bin/git",
        "ls-remote",
        "--exit-code",
        "--refs",
        "--",
        REPO_URL,
        "refs/heads/release",
    ]
    assert observed["download"] == (REPO_URL, commit)
    kwargs = observed["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["shell"] is False
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False
    assert kwargs["timeout"] == 60


@pytest.mark.parametrize(
    ("app_name", "expected"),
    (("Demo", "Demo-git"), ("FlagCue", "FlagCue-git")),
)
def test_final_directory_name_preserves_exact_application_case(
    app_name: str,
    expected: str,
) -> None:
    assert utm_21_prepare.final_directory_name(app_name) == expected


@pytest.mark.parametrize("unsafe", ("", ".", "..", "a/b", "a\\b", "\x00bad"))
def test_final_directory_name_rejects_unsafe_application_names(unsafe: str) -> None:
    with pytest.raises(utm_21_prepare.UTM21Error, match="APPLICATION_NAME_INVALID"):
        utm_21_prepare.final_directory_name(unsafe)


def test_extract_repository_zip_strips_archive_root_and_preserves_executable_mode(
    tmp_path: Path,
) -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("repo-sha/README.md", b"demo")
        script = zipfile.ZipInfo("repo-sha/tool.sh")
        script.external_attr = 0o100755 << 16
        archive.writestr(script, b"#!/bin/sh\n")

    target = tmp_path / "Demo-git"
    utm_21_prepare.extract_repository_zip(stream.getvalue(), target)

    assert (target / "README.md").read_bytes() == b"demo"
    assert (target / "tool.sh").stat().st_mode & 0o111
    assert not (target / "repo-sha").exists()


def test_extract_repository_zip_rejects_path_traversal_without_partial_target(
    tmp_path: Path,
) -> None:
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("repo-sha/../escape", b"unsafe")

    target = tmp_path / "Demo-git"
    with pytest.raises(ValueError, match="unsafe path"):
        utm_21_prepare.extract_repository_zip(stream.getvalue(), target)
    assert not target.exists()
    assert not (tmp_path / "escape").exists()


def test_directory_manifest_includes_dotfiles_hashes_and_executable_mode(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Demo-git"
    (root / "src").mkdir(parents=True)
    (root / ".env.example").write_text("TOKEN=\n", encoding="utf-8")
    tool = root / "src" / "tool.sh"
    tool.write_text("#!/bin/sh\n", encoding="utf-8")
    tool.chmod(0o700)

    manifest = utm_21_prepare.directory_manifest(root)

    assert [item["path"] for item in manifest] == [".env.example", "src/tool.sh"]
    assert [item["executable"] for item in manifest] == [False, True]
    assert all(len(str(item["sha256"])) == 64 for item in manifest)
    assert [item["size"] for item in manifest] == [7, 10]


def test_directory_manifest_rejects_symlinks_and_empty_directories(
    tmp_path: Path,
) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(utm_21_prepare.UTM21Error, match="DIRECTORY_MANIFEST_EMPTY"):
        utm_21_prepare.directory_manifest(empty)

    target = tmp_path / "target"
    target.write_text("target", encoding="utf-8")
    unsafe = tmp_path / "unsafe"
    unsafe.mkdir()
    (unsafe / "link").symlink_to(target)
    with pytest.raises(utm_21_prepare.UTM21Error, match="DIRECTORY_ENTRY_UNSAFE"):
        utm_21_prepare.directory_manifest(unsafe)


class FakeNotionAPI:
    def __init__(
        self,
        *,
        app_name: str = "Demo",
        app_ids: tuple[str, ...] = (APP_IDENTIFIER, APP_IDENTIFIER),
        bundle_ids: tuple[str, ...] = (BUNDLE_ID, BUNDLE_ID),
    ) -> None:
        self.app_name = app_name
        self.app_ids = iter(app_ids)
        self.bundle_ids = iter(bundle_ids)
        self.calls: list[tuple[str, ...]] = []

    def verify_parent(self, title: str) -> str:
        self.calls.append(("verify_parent", title))
        return title

    def read_field(self, page_title: str, section: str, label: str) -> str:
        self.calls.append(("read_field", page_title, section, label))
        if (section, label) == ("应用信息", "应用名: "):
            return self.app_name
        if (section, label) == ("账号信息", "APP_ID："):
            return next(self.app_ids)
        if (section, label) == ("应用信息", "正式包名: "):
            return next(self.bundle_ids)
        raise AssertionError((section, label))


def test_load_notion_identifiers_uses_exact_page_and_stable_rereads() -> None:
    notion = FakeNotionAPI()

    identifiers = utm_21_prepare.load_notion_identifiers(
        notion,
        parent_title="host-one",
        page_title="Demo-user",
        app_name="Demo",
        vm_user="user",
    )

    assert identifiers.app_id == APP_IDENTIFIER
    assert identifiers.bundle_id == BUNDLE_ID
    assert notion.calls.count(("verify_parent", "host-one")) == 3
    assert notion.calls.count(
        ("read_field", "Demo-user", "账号信息", "APP_ID：")
    ) == 2
    assert notion.calls.count(
        ("read_field", "Demo-user", "应用信息", "正式包名: ")
    ) == 2
    assert notion.calls.count(
        ("read_field", "Demo-user", "应用信息", "应用名: ")
    ) == 2


@pytest.mark.parametrize(
    "notion, page_title, error",
    (
        (FakeNotionAPI(app_name="Other"), "Demo-user", "NOTION_PAGE_APP_MISMATCH"),
        (FakeNotionAPI(app_ids=(APP_IDENTIFIER, "9876543210")), "Demo-user", "NOTION_IDENTIFIERS_UNSTABLE"),
        (FakeNotionAPI(app_ids=("not-numeric", "not-numeric")), "Demo-user", "NOTION_APP_ID_INVALID"),
        (FakeNotionAPI(app_ids=("5372311233", "5372311233")), "Demo-user", "NOTION_APP_ID_INVALID"),
        (FakeNotionAPI(bundle_ids=("invalid", "invalid")), "Demo-user", "NOTION_BUNDLE_ID_INVALID"),
        (
            FakeNotionAPI(
                bundle_ids=("org.toolbox.fastcleaner", "org.toolbox.fastcleaner")
            ),
            "Demo-user",
            "NOTION_BUNDLE_ID_INVALID",
        ),
        (FakeNotionAPI(), "Other-user", "NOTION_PAGE_IDENTITY_MISMATCH"),
    ),
)
def test_load_notion_identifiers_rejects_mismatch_unstable_or_invalid_values(
    notion: FakeNotionAPI,
    page_title: str,
    error: str,
) -> None:
    with pytest.raises(utm_21_prepare.UTM21Error, match=error):
        utm_21_prepare.load_notion_identifiers(
            notion,
            parent_title="host-one",
            page_title=page_title,
            app_name="Demo",
            vm_user="user",
        )


def test_replacement_manifest_maps_all_placeholders_without_mutating_host(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Demo-git"
    root.mkdir()
    source = (
        b"5372311233\n"
        b"jltest.test.test\n"
        b"uildbet.brovaxtere\n"
        b"xycoins.2027.test\n"
        b"org.toolbox.fastcleaner\n"
    )
    hidden = root / ".config"
    hidden.write_bytes(source)
    hidden.chmod(0o755)
    untouched = root / "README.md"
    untouched.write_bytes(b"no placeholders")
    identifiers = utm_21_prepare.ReplacementIdentifiers(APP_IDENTIFIER, BUNDLE_ID)

    manifest, counts = utm_21_prepare.replacement_manifest(root, identifiers)

    assert hidden.read_bytes() == source
    assert counts == {
        "5372311233": 1,
        "jltest.test.test": 1,
        "uildbet.brovaxtere": 1,
        "xycoins.2027.test": 1,
        "org.toolbox.fastcleaner": 1,
    }
    expected = APP_IDENTIFIER.encode() + b"\n" + (BUNDLE_ID.encode() + b"\n") * 4
    hidden_entry = next(item for item in manifest if item["path"] == ".config")
    assert hidden_entry["sha256"] == hashlib.sha256(expected).hexdigest()
    assert hidden_entry["size"] == len(expected)
    assert hidden_entry["executable"] is True
    assert next(item for item in manifest if item["path"] == "README.md") == (
        utm_21_prepare.directory_manifest(root)[1]
    )


def test_identifier_byte_replacement_is_one_pass_and_allows_zero_occurrences() -> None:
    nested_app_identifier = "153723112331"
    identifiers = utm_21_prepare.ReplacementIdentifiers(nested_app_identifier, BUNDLE_ID)

    replaced, counts = utm_21_prepare.replace_identifier_bytes(
        b"id=5372311233", identifiers
    )
    untouched, zero_counts = utm_21_prepare.replace_identifier_bytes(
        b"nothing to change", identifiers
    )

    assert replaced == f"id={nested_app_identifier}".encode()
    assert counts["5372311233"] == 1
    assert untouched == b"nothing to change"
    assert set(zero_counts.values()) == {0}


def test_remote_replacement_script_is_atomic_idempotent_and_recovers_partial_files(
    tmp_path: Path,
) -> None:
    root = tmp_path / "Demo-git"
    root.mkdir()
    first = root / "first.txt"
    first.write_bytes(b"5372311233")
    hidden = root / ".hidden-tool"
    hidden.write_bytes(
        b"jltest.test.test\n"
        b"uildbet.brovaxtere\n"
        b"xycoins.2027.test\n"
        b"org.toolbox.fastcleaner"
    )
    hidden.chmod(0o755)
    identifiers = utm_21_prepare.ReplacementIdentifiers(APP_IDENTIFIER, BUNDLE_ID)
    raw_manifest = utm_21_prepare.directory_manifest(root)
    expected_manifest, expected_counts = utm_21_prepare.replacement_manifest(
        root, identifiers
    )
    transformed_first, _counts = utm_21_prepare.replace_identifier_bytes(
        first.read_bytes(), identifiers
    )
    first.write_bytes(transformed_first)

    payload = json.dumps(
        {
            "app_id": APP_IDENTIFIER,
            "bundle_id": BUNDLE_ID,
            "raw_manifest": raw_manifest,
            "expected_manifest": expected_manifest,
        }
    )
    command = [sys.executable, "-c", utm_21_prepare.REMOTE_REPLACEMENT_SCRIPT, str(root)]
    completed = subprocess.run(
        command,
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert utm_21_prepare.directory_manifest(root) == expected_manifest
    assert hidden.stat().st_mode & 0o111
    applied = json.loads(completed.stdout)
    assert applied["5372311233"] == 0
    assert applied["jltest.test.test"] == 1
    assert applied["uildbet.brovaxtere"] == 1
    assert applied["xycoins.2027.test"] == 1
    assert applied["org.toolbox.fastcleaner"] == 1
    assert all(applied[key] <= expected_counts[key] for key in applied)

    repeated = subprocess.run(
        command,
        input=payload,
        text=True,
        capture_output=True,
        check=False,
    )
    assert repeated.returncode == 0, repeated.stderr
    assert set(json.loads(repeated.stdout).values()) == {0}
    assert utm_21_prepare.directory_manifest(root) == expected_manifest


def test_run_ledger_hashes_run_identity_and_writes_private_atomic_json(
    tmp_path: Path,
) -> None:
    ledger = utm_21_prepare.RunLedger.for_run(tmp_path / "runtime", "secret-run-id")
    ledger.write(
        {"app_name": "Demo", "branch": "dev", "run_digest": "forged"}
    )

    assert "secret-run-id" not in ledger.path.name
    assert ledger.path.parent == tmp_path / "runtime"
    assert ledger.path.stat().st_mode & 0o777 == 0o600
    assert ledger.read()["run_digest"] == ledger.run_digest
    assert "secret-run-id" not in ledger.path.read_text(encoding="utf-8")


def test_install_host_code_materializes_private_zip_and_removes_it(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = repository_zip(("README.md", b"demo"))
    shared = tmp_path / "shared"
    shared.mkdir()
    ledger = utm_21_prepare.RunLedger.for_run(tmp_path / "runtime", "run-1")
    original_extract = utm_21_prepare.extract_repository_zip
    observed: list[Path] = []

    def inspect_archive(archive_path: bytes | Path, destination: Path) -> None:
        assert isinstance(archive_path, Path)
        assert archive_path.is_file()
        assert archive_path.stat().st_mode & 0o777 == 0o600
        assert ledger.run_digest[:16] in archive_path.name
        observed.append(archive_path)
        original_extract(archive_path, destination)

    monkeypatch.setattr(utm_21_prepare, "extract_repository_zip", inspect_archive)
    utm_21_prepare.install_host_code(
        archive=archive,
        shared_root=shared,
        app_name="Demo",
        run_id="run-1",
        branch="main",
        commit_sha="a" * 40,
        ledger=ledger,
    )

    assert len(observed) == 1
    assert not observed[0].exists()
    assert not list(ledger.path.parent.glob("*.zip"))


def test_install_host_code_uses_application_git_name_and_resumes_identical_run(
    tmp_path: Path,
) -> None:
    archive = repository_zip(
        ("README.md", b"demo"),
        ("src/main.dart", b"void main() {}"),
    )
    shared = tmp_path / "shared"
    shared.mkdir()
    ledger = utm_21_prepare.RunLedger.for_run(tmp_path / "runtime", "run-1")

    target, manifest = utm_21_prepare.install_host_code(
        archive=archive,
        shared_root=shared,
        app_name="Demo",
        run_id="run-1",
        branch="dev",
        commit_sha="d" * 40,
        ledger=ledger,
    )

    assert target == shared / "Demo-git"
    assert (target / "README.md").read_bytes() == b"demo"
    state = ledger.read()
    assert state["host_directory"] == "Demo-git"
    assert state["branch"] == "dev"
    assert state["commit_sha"] == "d" * 40
    assert state["host_manifest"] == manifest

    repeated_target, repeated_manifest = utm_21_prepare.install_host_code(
        archive=archive,
        shared_root=shared,
        app_name="Demo",
        run_id="run-1",
        branch="dev",
        commit_sha="d" * 40,
        ledger=ledger,
    )
    assert repeated_target == target
    assert repeated_manifest == manifest


def test_install_host_code_refuses_existing_unbound_or_changed_target(
    tmp_path: Path,
) -> None:
    archive = repository_zip(("README.md", b"demo"))
    shared = tmp_path / "shared"
    shared.mkdir()
    target = shared / "Demo-git"
    target.mkdir()
    (target / "README.md").write_bytes(b"foreign")
    ledger = utm_21_prepare.RunLedger.for_run(tmp_path / "runtime", "run-1")

    with pytest.raises(utm_21_prepare.UTM21Error, match="HOST_TARGET_CONFLICT"):
        utm_21_prepare.install_host_code(
            archive=archive,
            shared_root=shared,
            app_name="Demo",
            run_id="run-1",
            branch="main",
            commit_sha="a" * 40,
            ledger=ledger,
        )
    assert (target / "README.md").read_bytes() == b"foreign"


def test_install_host_code_recovers_rename_completed_before_manifest_write(
    tmp_path: Path,
) -> None:
    archive = repository_zip(("README.md", b"demo"), (".hidden", b"hidden"))
    shared = tmp_path / "shared"
    shared.mkdir()
    target = shared / "Demo-git"
    utm_21_prepare.extract_repository_zip(archive, target)
    ledger = utm_21_prepare.RunLedger.for_run(tmp_path / "runtime", "run-1")
    ledger.write(
        {
            "app_name": "Demo",
            "branch": "dev",
            "commit_sha": "d" * 40,
            "host_directory": "Demo-git",
            "host_temporary": f".utm-21-{ledger.run_digest[:16]}-Demo-git",
        }
    )

    recovered, manifest = utm_21_prepare.install_host_code(
        archive=archive,
        shared_root=shared,
        app_name="Demo",
        run_id="run-1",
        branch="dev",
        commit_sha="d" * 40,
        ledger=ledger,
    )

    assert recovered == target
    assert ledger.read()["host_manifest"] == manifest
    assert ledger.read()["host_temporary"] == ""


class FakeGuestTransport:
    def __init__(self) -> None:
        self.paths: dict[str, list[dict[str, object]]] = {}
        self.identity_verified = False
        self.removed: list[str] = []
        self.replacement_calls: list[
            tuple[str, utm_21_prepare.ReplacementIdentifiers]
        ] = []
        self.replacement_target_manifest: list[dict[str, object]] | None = None

    def verify_identity(self) -> None:
        self.identity_verified = True

    def path_state(self, path: str) -> str:
        return "directory" if path in self.paths else "missing"

    def copy_tree(self, source: Path, temporary_path: str) -> None:
        assert self.identity_verified
        assert temporary_path not in self.paths
        self.paths[temporary_path] = utm_21_prepare.directory_manifest(source)

    def manifest(self, remote_path: str) -> list[dict[str, object]]:
        return self.paths[remote_path]

    def promote(self, temporary_path: str, final_path: str) -> None:
        assert final_path not in self.paths
        self.paths[final_path] = self.paths.pop(temporary_path)

    def remove_owned_temporary(self, remote_path: str) -> None:
        self.paths.pop(remote_path, None)
        self.removed.append(remote_path)

    def replace_identifiers(
        self,
        remote_path: str,
        identifiers: utm_21_prepare.ReplacementIdentifiers,
        raw_manifest: list[dict[str, object]],
        expected_manifest: list[dict[str, object]],
    ) -> dict[str, int]:
        self.replacement_calls.append((remote_path, identifiers))
        if self.replacement_target_manifest is not None:
            self.paths[remote_path] = self.replacement_target_manifest
        elif self.paths[remote_path] == raw_manifest:
            self.paths[remote_path] = expected_manifest
        return {placeholder: 0 for placeholder in utm_21_prepare.PLACEHOLDER_TARGETS}


def prepared_host_source(tmp_path: Path) -> tuple[Path, utm_21_prepare.RunLedger]:
    source = tmp_path / "shared" / "Demo-git"
    source.mkdir(parents=True)
    (source / ".hidden").write_text("hidden", encoding="utf-8")
    ledger = utm_21_prepare.RunLedger.for_run(tmp_path / "runtime", "run-1")
    ledger.write(
        {
            "app_name": "Demo",
            "branch": "release",
            "commit_sha": "e" * 40,
            "host_directory": "Demo-git",
            "host_manifest": utm_21_prepare.directory_manifest(source),
        }
    )
    return source, ledger


def test_deliver_guest_code_copies_to_downloads_and_verifies_exact_manifest(
    tmp_path: Path,
) -> None:
    source, ledger = prepared_host_source(tmp_path)
    transport = FakeGuestTransport()

    result = utm_21_prepare.deliver_guest_code(
        source=source,
        app_name="Demo",
        vm_user="user",
        vm_ip="192.0.2.10",
        run_id="run-1",
        commit_sha="e" * 40,
        ledger=ledger,
        transport=transport,
    )

    final = "/Users/user/Downloads/Demo-git"
    assert result == {"guest_path": final, "manifest_match": "exact"}
    assert transport.identity_verified
    assert transport.paths[final] == utm_21_prepare.directory_manifest(source)
    state = ledger.read()
    assert state["vm_user"] == "user"
    assert state["vm_ip"] == "192.0.2.10"
    assert state["guest_path"] == final
    assert state["guest_manifest"] == state["host_manifest"]

    repeated = utm_21_prepare.deliver_guest_code(
        source=source,
        app_name="Demo",
        vm_user="user",
        vm_ip="192.0.2.10",
        run_id="run-1",
        commit_sha="e" * 40,
        ledger=ledger,
        transport=transport,
    )
    assert repeated == result


def test_deliver_guest_code_refuses_conflicting_final_target(
    tmp_path: Path,
) -> None:
    source, ledger = prepared_host_source(tmp_path)
    transport = FakeGuestTransport()
    final = "/Users/user/Downloads/Demo-git"
    transport.paths[final] = [
        {"path": "foreign", "size": 1, "sha256": "f" * 64, "executable": False}
    ]

    with pytest.raises(utm_21_prepare.UTM21Error, match="GUEST_TARGET_CONFLICT"):
        utm_21_prepare.deliver_guest_code(
            source=source,
            app_name="Demo",
            vm_user="user",
            vm_ip="192.0.2.10",
            run_id="run-1",
            commit_sha="e" * 40,
            ledger=ledger,
            transport=transport,
        )
    assert transport.paths[final][0]["path"] == "foreign"


def test_deliver_guest_code_recovers_promotion_completed_before_manifest_write(
    tmp_path: Path,
) -> None:
    source, ledger = prepared_host_source(tmp_path)
    transport = FakeGuestTransport()
    final = "/Users/user/Downloads/Demo-git"
    temporary = (
        f"/Users/user/Downloads/.utm-21-{ledger.run_digest[:16]}-Demo-git"
    )
    host_manifest = utm_21_prepare.directory_manifest(source)
    transport.paths[final] = host_manifest
    ledger.write(
        {
            **ledger.read(),
            "vm_user": "user",
            "vm_ip": "192.0.2.10",
            "guest_path": final,
            "guest_temporary": temporary,
        }
    )

    result = utm_21_prepare.deliver_guest_code(
        source=source,
        app_name="Demo",
        vm_user="user",
        vm_ip="192.0.2.10",
        run_id="run-1",
        commit_sha="e" * 40,
        ledger=ledger,
        transport=transport,
    )

    assert result == {"guest_path": final, "manifest_match": "exact"}
    assert ledger.read()["guest_manifest"] == host_manifest
    assert ledger.read()["guest_temporary"] == ""


def test_ssh_guest_transport_uses_password_channel_and_recursive_scp(
    tmp_path: Path,
) -> None:
    source = tmp_path / "Demo-git"
    source.mkdir()
    (source / "README.md").write_text("demo", encoding="utf-8")
    manifest = utm_21_prepare.directory_manifest(source)
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run_command(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        remote = command[-1]
        if command[0] == "/usr/bin/scp":
            output = ""
        elif "UTM21_PATH_STATE" in remote:
            output = "missing\n"
        elif "UTM21_MANIFEST" in remote:
            output = json.dumps(manifest)
        else:
            output = ""
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    transport = utm_21_prepare.SSHGuestTransport(
        "user",
        "192.0.2.10",
        run_command=run_command,
        environment_factory=lambda: {"SSH_ASKPASS": "configured"},
    )
    transport.verify_identity()
    assert transport.path_state("/Users/user/Downloads/Demo-git") == "missing"
    transport.copy_tree(
        source,
        "/Users/user/Downloads/.utm-21-1234567890abcdef-Demo-git",
    )
    assert transport.manifest("/Users/user/Downloads/Demo-git") == manifest
    transport.promote(
        "/Users/user/Downloads/.utm-21-1234567890abcdef-Demo-git",
        "/Users/user/Downloads/Demo-git",
    )

    scp_command, scp_kwargs = next(call for call in calls if call[0][0] == "/usr/bin/scp")
    assert "-r" in scp_command
    assert str(source) in scp_command
    assert scp_kwargs["shell"] is False
    assert scp_kwargs["env"] == {"SSH_ASKPASS": "configured"}
    assert all(kwargs["capture_output"] is True for _, kwargs in calls)
    assert all(kwargs["check"] is False for _, kwargs in calls)
    assert all(kwargs["shell"] is False for _, kwargs in calls)


def test_ssh_guest_replacement_sends_identifiers_only_through_stdin() -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run_command(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=json.dumps(
                {placeholder: 0 for placeholder in utm_21_prepare.PLACEHOLDER_TARGETS}
            ),
            stderr="",
        )

    transport = utm_21_prepare.SSHGuestTransport(
        "user",
        "192.0.2.10",
        run_command=run_command,
        environment_factory=lambda: {"SSH_ASKPASS": "configured"},
    )
    identifiers = utm_21_prepare.ReplacementIdentifiers(APP_IDENTIFIER, BUNDLE_ID)

    result = transport.replace_identifiers(
        "/Users/user/Downloads/Demo-git",
        identifiers,
        [{"path": "file", "size": 1, "sha256": "a" * 64, "executable": False}],
        [{"path": "file", "size": 1, "sha256": "b" * 64, "executable": False}],
    )

    command, kwargs = calls[0]
    command_text = "\n".join(command)
    assert APP_IDENTIFIER not in command_text
    assert BUNDLE_ID not in command_text
    payload = json.loads(str(kwargs["input"]))
    assert payload["app_id"] == APP_IDENTIFIER
    assert payload["bundle_id"] == BUNDLE_ID
    assert set(payload) == {
        "app_id",
        "bundle_id",
        "raw_manifest",
        "expected_manifest",
    }
    assert kwargs["shell"] is False
    assert kwargs["capture_output"] is True
    assert result == {
        placeholder: 0 for placeholder in utm_21_prepare.PLACEHOLDER_TARGETS
    }


def test_guest_replacement_recovers_partial_state_and_persists_no_identifiers(
    tmp_path: Path,
) -> None:
    source, ledger = prepared_host_source(tmp_path)
    raw_manifest = utm_21_prepare.directory_manifest(source)
    identifiers = utm_21_prepare.ReplacementIdentifiers(APP_IDENTIFIER, BUNDLE_ID)
    expected_manifest = [
        {
            **raw_manifest[0],
            "size": raw_manifest[0]["size"] + 1,
            "sha256": "a" * 64,
        }
    ]
    counts = {placeholder: 0 for placeholder in utm_21_prepare.PLACEHOLDER_TARGETS}
    counts["5372311233"] = 1
    final = "/Users/user/Downloads/Demo-git"
    transport = FakeGuestTransport()
    transport.paths[final] = raw_manifest
    transport.replacement_target_manifest = expected_manifest
    hashes = utm_21_prepare.identifier_hashes(identifiers)
    ledger.write(
        {
            **ledger.read(),
            "vm_user": "user",
            "vm_ip": "192.0.2.10",
            "guest_path": final,
            "guest_temporary": "",
            "guest_manifest": raw_manifest,
            "replacement_status": "running",
            "identifier_hashes": hashes,
            "replacement_counts": counts,
            "expected_guest_manifest": expected_manifest,
        }
    )

    result = utm_21_prepare.apply_guest_replacements(
        guest_path=final,
        raw_manifest=raw_manifest,
        expected_manifest=expected_manifest,
        replacement_counts=counts,
        identifiers=identifiers,
        vm_user="user",
        vm_ip="192.0.2.10",
        ledger=ledger,
        transport=transport,
    )

    assert result == {
        "guest_path": final,
        "manifest_match": "exact",
        "replacement_status": "verified",
    }
    assert len(transport.replacement_calls) == 1
    state = ledger.read()
    assert state["replacement_status"] == "verified"
    assert state["guest_manifest"] == expected_manifest
    ledger_text = ledger.path.read_text(encoding="utf-8")
    assert APP_IDENTIFIER not in ledger_text
    assert BUNDLE_ID not in ledger_text
    assert state["identifier_hashes"] == hashes
    assert state["replacement_counts"] == counts

    repeated = utm_21_prepare.apply_guest_replacements(
        guest_path=final,
        raw_manifest=raw_manifest,
        expected_manifest=expected_manifest,
        replacement_counts=counts,
        identifiers=identifiers,
        vm_user="user",
        vm_ip="192.0.2.10",
        ledger=ledger,
        transport=transport,
    )
    assert repeated == result
    assert len(transport.replacement_calls) == 1


def test_deliver_guest_code_accepts_only_owned_partial_replacement_state(
    tmp_path: Path,
) -> None:
    source = tmp_path / "shared" / "Demo-git"
    source.mkdir(parents=True)
    (source / "one.txt").write_text("5372311233", encoding="utf-8")
    (source / "two.txt").write_text("jltest.test.test", encoding="utf-8")
    raw_manifest = utm_21_prepare.directory_manifest(source)
    identifiers = utm_21_prepare.ReplacementIdentifiers(APP_IDENTIFIER, BUNDLE_ID)
    expected_manifest, counts = utm_21_prepare.replacement_manifest(source, identifiers)
    ledger = utm_21_prepare.RunLedger.for_run(tmp_path / "runtime", "run-1")
    final = "/Users/user/Downloads/Demo-git"
    partial_manifest = [raw_manifest[0], expected_manifest[1]]
    ledger.write(
        {
            "app_name": "Demo",
            "branch": "release",
            "commit_sha": "e" * 40,
            "host_directory": "Demo-git",
            "host_manifest": raw_manifest,
            "vm_user": "user",
            "vm_ip": "192.0.2.10",
            "guest_path": final,
            "guest_temporary": "",
            "guest_manifest": raw_manifest,
            "replacement_status": "running",
            "identifier_hashes": utm_21_prepare.identifier_hashes(identifiers),
            "replacement_counts": counts,
            "expected_guest_manifest": expected_manifest,
        }
    )
    transport = FakeGuestTransport()
    transport.paths[final] = partial_manifest

    result = utm_21_prepare.deliver_guest_code(
        source=source,
        app_name="Demo",
        vm_user="user",
        vm_ip="192.0.2.10",
        run_id="run-1",
        commit_sha="e" * 40,
        ledger=ledger,
        transport=transport,
        accepted_final_manifest=expected_manifest,
    )

    assert result["manifest_match"] == "replacement_partial"

    ledger.write({**ledger.read(), "replacement_status": ""})
    with pytest.raises(utm_21_prepare.UTM21Error, match="GUEST_TARGET_CONFLICT"):
        utm_21_prepare.deliver_guest_code(
            source=source,
            app_name="Demo",
            vm_user="user",
            vm_ip="192.0.2.10",
            run_id="run-1",
            commit_sha="e" * 40,
            ledger=ledger,
            transport=transport,
            accepted_final_manifest=expected_manifest,
        )


def exact_run() -> dict:
    return {
        "id": "run-1",
        "app_name": "Demo",
        "chat_id": "project-chat",
        "project_chat_id": "project-chat",
        "vm_name": "user",
        "submission_data": {"host_machine": "host-one"},
        "skill_attempts": [
            {"skill": "utm-p8", "status": "succeeded"},
            {"skill": "utm-21", "status": "started"},
        ],
        "lifecycle": {"started_at": "2026-08-28T00:00:00+00:00"},
    }


def test_verify_run_context_requires_exact_identity_and_verified_utm_p8() -> None:
    run = exact_run()
    utm_21_prepare.verify_run_context(
        run,
        run_id="run-1",
        chat_id=PROJECT_CHAT,
        app_name="Demo",
        vm_name="user",
        vm_ip="192.0.2.10",
        local_host="host-one",
    )

    mutations = (
        {"id": "other-run"},
        {"chat_id": "other-chat"},
        {"app_name": "Other"},
        {"vm_name": "wxyz"},
        {"submission_data": {"host_machine": "other-host"}},
        {"skill_attempts": [{"skill": "utm-p8", "status": "failed"}]},
        {"lifecycle": {"finished_at": "2026-08-28T01:00:00+00:00"}},
    )
    for mutation in mutations:
        with pytest.raises(utm_21_prepare.UTM21Error, match="RUN_CONTEXT_INVALID"):
            utm_21_prepare.verify_run_context(
                {**run, **mutation},
                run_id="run-1",
                chat_id=PROJECT_CHAT,
                app_name="Demo",
                vm_name="user",
                vm_ip="192.0.2.10",
                local_host="host-one",
            )


class FakeBranchSelector:
    def __init__(self, branch: str = "dev") -> None:
        self.branch = branch
        self.calls: list[tuple[str, ...]] = []

    def choose_branch(self, run_id: str, chat_id: str, timeout_seconds: int) -> str:
        self.calls.append(("choose", run_id, chat_id, str(timeout_seconds)))
        return self.branch

    def report_missing_code_url(self, run_id: str, chat_id: str) -> None:
        self.calls.append(("missing", run_id, chat_id))


def test_execute_workflow_opens_selected_branch_and_copies_application_git(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    selector = FakeBranchSelector("dev")
    guest = FakeGuestTransport()
    archive = repository_zip(("README.md", b"demo"), (".hidden", b"hidden"))
    shared = tmp_path / "shared"
    shared.mkdir()

    class ZipClient:
        def retrieve_branch_zip(self, repo_url: str, branch: str) -> tuple[str, bytes]:
            events.append(f"zip:{branch}")
            assert repo_url == REPO_URL
            return "f" * 40, archive

    result = utm_21_prepare.execute_workflow(
        run=exact_run(),
        run_id="run-1",
        chat_id=PROJECT_CHAT,
        app_name="Demo",
        vm_name="user",
        vm_ip="192.0.2.10",
        local_host="host-one",
        shared_root=shared,
        runtime_root=tmp_path / "runtime",
        records_loader=lambda: events.append("records") or [record("Demo", REPO_URL)],
        browser_opener=lambda url: events.append(f"open:{url}"),
        branch_selector=selector,
        zip_client=ZipClient(),
        guest_transport=guest,
        notion_api=FakeNotionAPI(),
        sleeper=lambda seconds: events.append(f"sleep:{seconds}"),
        decision_timeout_seconds=3600,
    )

    assert result["branch"] == "dev"
    assert result["host_directory"] == "Demo-git"
    assert result["guest_path"] == "/Users/user/Downloads/Demo-git"
    assert result["manifest_match"] == "exact"
    assert result["replacement_status"] == "verified"
    assert len(guest.replacement_calls) == 1
    assert selector.calls == [("choose", "run-1", "project-chat", "3600")]
    assert events == [
        "sleep:0",
        "records",
        f"open:{REPO_URL}",
        "open:https://github.com/acme/example-repo/tree/dev",
        "zip:dev",
    ]
    assert (tmp_path / "shared" / "Demo-git" / ".hidden").read_bytes() == b"hidden"


def test_execute_workflow_missing_code_url_reads_three_times_then_faults(
    tmp_path: Path,
) -> None:
    events: list[str] = []
    selector = FakeBranchSelector()

    with pytest.raises(utm_21_prepare.MissingCodeURL, match="CODE_URL_MISSING"):
        utm_21_prepare.execute_workflow(
            run=exact_run(),
            run_id="run-1",
            chat_id=PROJECT_CHAT,
            app_name="Demo",
            vm_name="user",
            vm_ip="192.0.2.10",
            local_host="host-one",
            shared_root=tmp_path / "shared",
            runtime_root=tmp_path / "runtime",
            records_loader=lambda: events.append("records") or [record("Demo", None)],
            browser_opener=lambda url: events.append(f"open:{url}"),
            branch_selector=selector,
            zip_client=object(),
            guest_transport=FakeGuestTransport(),
            notion_api=FakeNotionAPI(),
            sleeper=lambda seconds: events.append(f"sleep:{seconds}"),
            decision_timeout_seconds=3600,
        )

    assert events == [
        "sleep:0",
        "records",
        "sleep:5",
        "records",
        "sleep:10",
        "records",
    ]
    assert selector.calls == [("missing", "run-1", "project-chat")]


def test_open_host_browser_uses_argv_without_shell() -> None:
    observed: dict[str, object] = {}

    def runner(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        observed["command"] = command
        observed["kwargs"] = kwargs
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    utm_21_prepare.open_host_browser(REPO_URL, run_command=runner)

    assert observed["command"] == ["/usr/bin/open", REPO_URL]
    kwargs = observed["kwargs"]
    assert isinstance(kwargs, dict)
    assert kwargs["shell"] is False
    assert kwargs["capture_output"] is True
    assert kwargs["check"] is False


def test_bot_command_client_notifies_waits_and_reports_missing_without_leaking_output(
    tmp_path: Path,
) -> None:
    commands: list[list[str]] = []

    def runner(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        if "wait-decision" in command:
            return subprocess.CompletedProcess(command, 0, stdout="release\n", stderr="")
        return subprocess.CompletedProcess(command, 0, stdout="internal-run-id\n", stderr="")

    client = utm_21_prepare.BotCommandClient(
        project_root=tmp_path,
        run_command=runner,
    )
    assert client.choose_branch("run-1", "project-chat", 3600) == "release"
    client.report_missing_code_url("run-1", "project-chat")

    assert [command[2] for command in commands] == [
        "notify-code-branch",
        "wait-decision",
        "skill-failure",
        "notify-fault",
    ]
    assert "code_branch" in commands[1]
    assert "utm-21" in commands[2]
    assert "--recovery-attempts" in commands[3]
    assert "3" in commands[3]
