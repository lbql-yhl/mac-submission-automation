#!/usr/bin/env python3
"""Create and reconcile one command-line Xcode Archive inside a UTM guest."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import plistlib
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


VERSION_RE = re.compile(r"^[0-9]+(?:\.[0-9]+)*$")
BUILD_RE = re.compile(r"^[1-9][0-9]*$")
BUNDLE_ID_RE = re.compile(r"^[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
OWNER_HASH_RE = re.compile(r"^[a-f0-9]{16}$")
IDENTITY_RE = re.compile(r'^\s*\d+\)\s+([A-Fa-f0-9]{40})\s+"([^"]+)"')


class ArchiveError(RuntimeError):
    """Raised when an Archive target cannot be proven unique and safe."""


@dataclass(frozen=True)
class SigningIdentity:
    fingerprint: str
    common_name: str


@dataclass(frozen=True)
class ProvisioningProfile:
    uuid: str
    name: str
    team_id: str
    bundle_id: str
    expires_at: datetime
    certificate_fingerprints: tuple[str, ...]
    game_center: bool


@dataclass(frozen=True)
class SigningContext:
    team_id: str
    identity: SigningIdentity
    profile: ProvisioningProfile


@dataclass(frozen=True)
class ArchiveContext:
    app_name: str
    workspace: Path
    archive_path: Path
    bundle_id: str
    version: str
    build: str
    signing: SigningContext
    entitlements_path: Path | None = None


def _regular_file(path: Path, error: str) -> Path:
    path = Path(path)
    if path.is_symlink() or not path.is_file():
        raise ArchiveError(error)
    return path


def _contained(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def select_workspace(studio_root: Path) -> Path:
    root = Path(studio_root)
    if root.is_symlink() or not root.is_dir():
        raise ArchiveError("STUDIO_ROOT_UNSAFE")
    resolved_root = root.resolve()
    matches: list[Path] = []
    for candidate in root.glob("*/ios/Runner.xcworkspace"):
        if candidate.is_symlink() or not candidate.is_dir():
            continue
        resolved = candidate.resolve()
        repository = resolved.parent.parent
        git_marker = repository / ".git"
        if not _contained(resolved, resolved_root):
            continue
        if git_marker.is_symlink() or not git_marker.exists():
            continue
        if candidate.stat().st_uid != os.getuid():
            continue
        matches.append(resolved)
    if len(matches) != 1:
        raise ArchiveError(f"WORKSPACE_MATCH_COUNT={len(matches)}")
    return matches[0]


def _one_match(pattern: re.Pattern[str], text: str, error: str) -> re.Match[str]:
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise ArchiveError(error)
    return matches[0]


def read_project_version(repository: Path) -> tuple[str, str]:
    repository = Path(repository)
    pubspec = _regular_file(repository / "pubspec.yaml", "PUBSPEC_UNSAFE")
    generated = _regular_file(
        repository / "ios" / "Flutter" / "Generated.xcconfig",
        "GENERATED_XCCONFIG_UNSAFE",
    )
    pubspec_match = _one_match(
        re.compile(
            r"^version:\s*['\"]?([0-9]+(?:\.[0-9]+)*)\+([1-9][0-9]*)['\"]?\s*(?:#.*)?$",
            re.MULTILINE,
        ),
        pubspec.read_text(encoding="utf-8"),
        "PUBSPEC_VERSION_COUNT_INVALID",
    )
    generated_values: dict[str, str] = {}
    for line in generated.read_text(encoding="utf-8").splitlines():
        if "=" not in line or line.lstrip().startswith("#"):
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key in {"FLUTTER_BUILD_NAME", "FLUTTER_BUILD_NUMBER"}:
            if key in generated_values:
                raise ArchiveError(f"GENERATED_{key}_DUPLICATE")
            generated_values[key] = value.strip()
    version, build = pubspec_match.groups()
    if (
        generated_values.get("FLUTTER_BUILD_NAME") != version
        or generated_values.get("FLUTTER_BUILD_NUMBER") != build
    ):
        raise ArchiveError("PROJECT_VERSION_MISMATCH")
    if not VERSION_RE.fullmatch(version) or not BUILD_RE.fullmatch(build):
        raise ArchiveError("PROJECT_VERSION_INVALID")
    return version, build


def parse_build_settings(payload: str) -> dict[str, str]:
    try:
        decoded = json.loads(payload)
    except json.JSONDecodeError as error:
        raise ArchiveError("BUILD_SETTINGS_JSON_INVALID") from error
    if not isinstance(decoded, list):
        raise ArchiveError("BUILD_SETTINGS_JSON_INVALID")
    matches = [
        item
        for item in decoded
        if isinstance(item, dict)
        and item.get("target") == "Runner"
        and isinstance(item.get("buildSettings"), dict)
    ]
    if len(matches) != 1:
        raise ArchiveError(f"RUNNER_BUILD_SETTINGS_COUNT={len(matches)}")
    return {str(key): str(value) for key, value in matches[0]["buildSettings"].items()}


def parse_identities(output: str) -> list[SigningIdentity]:
    identities: dict[str, SigningIdentity] = {}
    for line in output.splitlines():
        match = IDENTITY_RE.match(line)
        if not match:
            continue
        fingerprint, common_name = match.groups()
        if not common_name.startswith("Apple Distribution:"):
            continue
        normalized = fingerprint.upper()
        identities[normalized] = SigningIdentity(normalized, common_name)
    return [identities[key] for key in sorted(identities)]


def _aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _profile_from_plist(payload: Mapping[str, Any]) -> ProvisioningProfile:
    entitlements = payload.get("Entitlements")
    teams = payload.get("TeamIdentifier")
    certificates = payload.get("DeveloperCertificates")
    if (
        not isinstance(entitlements, dict)
        or not isinstance(teams, list)
        or len(teams) != 1
    ):
        raise ArchiveError("PROFILE_METADATA_INVALID")
    if not isinstance(certificates, list) or not certificates:
        raise ArchiveError("PROFILE_CERTIFICATES_INVALID")
    team_id = str(teams[0])
    application_identifier = str(entitlements.get("application-identifier") or "")
    prefix = f"{team_id}."
    if not application_identifier.startswith(prefix):
        raise ArchiveError("PROFILE_APPLICATION_IDENTIFIER_INVALID")
    bundle_id = application_identifier[len(prefix) :]
    expires_at = payload.get("ExpirationDate")
    if not isinstance(expires_at, datetime):
        raise ArchiveError("PROFILE_EXPIRATION_INVALID")
    if (
        payload.get("ProvisionedDevices")
        or payload.get("ProvisionsAllDevices")
        or entitlements.get("get-task-allow") is not False
        or entitlements.get("beta-reports-active") is not True
        or not BUNDLE_ID_RE.fullmatch(bundle_id)
    ):
        raise ArchiveError("PROFILE_NOT_APP_STORE")
    fingerprints: list[str] = []
    for certificate in certificates:
        if not isinstance(certificate, bytes):
            raise ArchiveError("PROFILE_CERTIFICATES_INVALID")
        fingerprints.append(hashlib.sha1(certificate).hexdigest().upper())
    uuid = str(payload.get("UUID") or "")
    name = str(payload.get("Name") or "")
    if not uuid or not name or not team_id:
        raise ArchiveError("PROFILE_METADATA_INVALID")
    return ProvisioningProfile(
        uuid=uuid,
        name=name,
        team_id=team_id,
        bundle_id=bundle_id,
        expires_at=_aware_utc(expires_at),
        certificate_fingerprints=tuple(sorted(set(fingerprints))),
        game_center=entitlements.get("com.apple.developer.game-center") is True,
    )


def read_profile(path: Path) -> ProvisioningProfile:
    path = _regular_file(path, "PROFILE_FILE_UNSAFE")
    result = subprocess.run(
        ["/usr/bin/security", "cms", "-D", "-i", str(path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ArchiveError("PROFILE_DECODE_FAILED")
    try:
        payload = plistlib.loads(result.stdout)
    except (plistlib.InvalidFileException, ValueError) as error:
        raise ArchiveError("PROFILE_PLIST_INVALID") from error
    if not isinstance(payload, dict):
        raise ArchiveError("PROFILE_PLIST_INVALID")
    return _profile_from_plist(payload)


def installed_profiles(home: Path) -> list[ProvisioningProfile]:
    roots = (
        Path(home) / "Library" / "MobileDevice" / "Provisioning Profiles",
        Path(home)
        / "Library"
        / "Developer"
        / "Xcode"
        / "UserData"
        / "Provisioning Profiles",
    )
    profiles: dict[str, ProvisioningProfile] = {}
    for root in roots:
        if root.is_symlink() or not root.is_dir():
            continue
        for path in sorted(root.glob("*.mobileprovision")):
            if path.is_symlink() or not path.is_file():
                continue
            try:
                profile = read_profile(path)
            except ArchiveError:
                continue
            profiles[profile.uuid] = profile
    return [profiles[key] for key in sorted(profiles)]


def select_signing_context(
    identities: Sequence[SigningIdentity],
    profiles: Sequence[ProvisioningProfile],
    bundle_id: str,
    now: datetime,
) -> SigningContext:
    now = _aware_utc(now)
    matches: list[SigningContext] = []
    for profile in profiles:
        if profile.bundle_id != bundle_id or profile.expires_at <= now:
            continue
        for identity in identities:
            if identity.fingerprint not in profile.certificate_fingerprints:
                continue
            if f"({profile.team_id})" not in identity.common_name:
                continue
            matches.append(SigningContext(profile.team_id, identity, profile))
    if len(matches) != 1:
        raise ArchiveError(f"SIGNING_CONTEXT_MATCH_COUNT={len(matches)}")
    return matches[0]


def archive_command(context: ArchiveContext) -> list[str]:
    command = [
        "/usr/bin/xcodebuild",
        "archive",
        "-workspace",
        str(context.workspace),
        "-scheme",
        "Runner",
        "-configuration",
        "Release",
        "-destination",
        "generic/platform=iOS",
        "-archivePath",
        str(context.archive_path),
        "CODE_SIGN_STYLE=Manual",
        f"DEVELOPMENT_TEAM={context.signing.team_id}",
        f"CODE_SIGN_IDENTITY={context.signing.identity.common_name}",
        f"PROVISIONING_PROFILE_SPECIFIER={context.signing.profile.uuid}",
    ]
    if context.entitlements_path is not None:
        command.append(f"CURRENT_PROJECT_VERSION={context.build}")
        command.append(f"CODE_SIGN_ENTITLEMENTS={context.entitlements_path}")
    return command


def next_build_number(build: str) -> str:
    if not BUILD_RE.fullmatch(str(build)):
        raise ArchiveError("PROJECT_BUILD_INVALID")
    return str(int(build) + 1)


def game_center_entitlements(profile: ProvisioningProfile) -> bytes:
    if not profile.game_center:
        raise ArchiveError("PROFILE_GAME_CENTER_NOT_AUTHORIZED")
    return plistlib.dumps(
        {"com.apple.developer.game-center": True},
        fmt=plistlib.FMT_XML,
        sort_keys=True,
    )


def archive_recovery_action(
    ledger: Mapping[str, object], *, process_alive: bool
) -> str:
    state = str(ledger.get("state") or "")
    if state == "verified":
        return "use_verified"
    if state == "failed":
        return "stop_failed"
    if state in {"starting", "running"}:
        return "poll" if process_alive else "stop_ambiguous"
    return "stop_ambiguous"


def _run(command: Sequence[str], error: str) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        list(command),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise ArchiveError(error)
    return result


def _read_config_bundle_id(path: Path) -> str:
    path = _regular_file(path, "UPLOAD_CONFIG_UNSAFE")
    in_app_info = False
    matches: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#"):
            continue
        if not raw_line.startswith((" ", "\t")):
            in_app_info = raw_line.strip() == "app_info:"
            continue
        if not in_app_info:
            continue
        match = re.match(r"^\s+bundle_id:\s*(.+?)\s*$", raw_line)
        if match:
            value = match.group(1).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "'\"":
                value = value[1:-1]
            matches.append(value)
    if len(matches) != 1 or not BUNDLE_ID_RE.fullmatch(matches[0]):
        raise ArchiveError(f"CONFIG_BUNDLE_ID_COUNT={len(matches)}")
    return matches[0]


def _require_runner_scheme(workspace: Path) -> None:
    result = _run(
        ["/usr/bin/xcodebuild", "-list", "-json", "-workspace", str(workspace)],
        "XCODE_SCHEME_DISCOVERY_FAILED",
    )
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as error:
        raise ArchiveError("XCODE_SCHEME_JSON_INVALID") from error
    schemes = (
        payload.get("workspace", {}).get("schemes", [])
        if isinstance(payload, dict)
        else []
    )
    matches = [scheme for scheme in schemes if scheme == "Runner"]
    if len(matches) != 1:
        raise ArchiveError(f"RUNNER_SCHEME_COUNT={len(matches)}")


def _build_settings(workspace: Path) -> dict[str, str]:
    result = _run(
        [
            "/usr/bin/xcodebuild",
            "-showBuildSettings",
            "-json",
            "-workspace",
            str(workspace),
            "-scheme",
            "Runner",
            "-configuration",
            "Release",
            "-destination",
            "generic/platform=iOS",
        ],
        "XCODE_BUILD_SETTINGS_FAILED",
    )
    return parse_build_settings(result.stdout)


def _identity_inventory() -> list[SigningIdentity]:
    return parse_identities(
        _run(
            ["/usr/bin/security", "find-identity", "-v", "-p", "codesigning"],
            "CODESIGN_IDENTITY_READ_FAILED",
        ).stdout
    )


def _archive_path(home: Path, owner_hash: str, version: str, build: str) -> Path:
    root = home / "Library" / "Developer" / "Xcode" / "Archives" / "utm-22"
    if root.exists() and (root.is_symlink() or not root.is_dir()):
        raise ArchiveError("ARCHIVE_ROOT_UNSAFE")
    root.mkdir(parents=True, exist_ok=True)
    return root / f"{owner_hash}-{version}-{build}.xcarchive"


def _private_attempt_file(path: Path, payload: bytes) -> Path:
    if path.exists() or path.is_symlink():
        path = _regular_file(path, "GAME_CENTER_ENTITLEMENTS_UNSAFE")
        if path.stat().st_mode & 0o777 != 0o600 or path.read_bytes() != payload:
            raise ArchiveError("GAME_CENTER_ENTITLEMENTS_MISMATCH")
        return path
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    return path


def _prepare_context(
    home: Path,
    config: Path,
    owner_hash: str,
    app_name: str,
    *,
    game_center_recovery: bool = False,
    source_attempt: Path | None = None,
) -> ArchiveContext:
    if (
        not app_name
        or app_name in {".", ".."}
        or Path(app_name).name != app_name
        or any(ord(character) < 32 or ord(character) == 127 for character in app_name)
    ):
        raise ArchiveError("APPLICATION_NAME_INVALID")
    workspace = select_workspace(home / "StudioProjects")
    repository = workspace.parent.parent
    version, build = read_project_version(repository)
    bundle_id = _read_config_bundle_id(config)
    _require_runner_scheme(workspace)
    settings = _build_settings(workspace)
    expected = {
        "PRODUCT_BUNDLE_IDENTIFIER": bundle_id,
        "MARKETING_VERSION": version,
        "CURRENT_PROJECT_VERSION": build,
    }
    for key, value in expected.items():
        if settings.get(key) != value:
            raise ArchiveError(f"XCODE_{key}_MISMATCH")
    signing = select_signing_context(
        _identity_inventory(),
        installed_profiles(home),
        bundle_id,
        datetime.now(timezone.utc),
    )
    entitlements_path: Path | None = None
    if game_center_recovery:
        if source_attempt is None:
            raise ArchiveError("GAME_CENTER_SOURCE_REQUIRED")
        source = _read_ledger(source_attempt, owner_hash)
        if (
            source.get("state") != "verified"
            or source.get("bundle_id") != bundle_id
            or source.get("app_name") != app_name
            or source.get("version") != version
            or source.get("build") != build
            or source.get("team_id") != signing.team_id
            or source.get("profile_uuid") != signing.profile.uuid
            or source.get("game_center_recovery") is True
        ):
            raise ArchiveError("GAME_CENTER_SOURCE_MISMATCH")
        build = next_build_number(build)
        entitlements_path = _private_attempt_file(
            home / "Downloads" / f"utm-22-{owner_hash}.game-center.entitlements.plist",
            game_center_entitlements(signing.profile),
        )
    return ArchiveContext(
        app_name=app_name,
        workspace=workspace,
        archive_path=_archive_path(home, owner_hash, version, build),
        bundle_id=bundle_id,
        version=version,
        build=build,
        signing=signing,
        entitlements_path=entitlements_path,
    )


def _atomic_create_json(path: Path, payload: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _atomic_replace_json(path: Path, payload: Mapping[str, object]) -> None:
    if path.is_symlink() or not path.is_file():
        raise ArchiveError("ARCHIVE_LEDGER_UNSAFE")
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, separators=(",", ":"), sort_keys=True)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
        path.chmod(0o600)
    finally:
        temporary.unlink(missing_ok=True)


def _read_ledger(path: Path, owner_hash: str) -> dict[str, Any]:
    path = _regular_file(path, "ARCHIVE_LEDGER_UNSAFE")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ArchiveError("ARCHIVE_LEDGER_INVALID") from error
    if not isinstance(payload, dict) or payload.get("owner_hash") != owner_hash:
        raise ArchiveError("ARCHIVE_LEDGER_OWNERSHIP_MISMATCH")
    return payload


def _update_ledger(path: Path, owner_hash: str, **values: object) -> dict[str, Any]:
    payload = _read_ledger(path, owner_hash)
    payload.update(values)
    _atomic_replace_json(path, payload)
    return payload


def _validate_attempt_path(
    home: Path,
    path: Path,
    owner_hash: str,
    *,
    game_center_recovery: bool = False,
) -> Path:
    if not OWNER_HASH_RE.fullmatch(owner_hash):
        raise ArchiveError("OWNER_HASH_INVALID")
    downloads = (home / "Downloads").resolve()
    candidate = Path(path)
    if candidate.parent.resolve() != downloads:
        raise ArchiveError("ARCHIVE_LEDGER_LOCATION_INVALID")
    qualifier = ".game-center" if game_center_recovery else ""
    if candidate.name != f"utm-22-{owner_hash}{qualifier}.archive-attempt.json":
        raise ArchiveError("ARCHIVE_LEDGER_NAME_INVALID")
    return candidate


def _verify_archive(context: ArchiveContext) -> None:
    archive = context.archive_path
    if archive.is_symlink() or not (archive / "Info.plist").is_file():
        raise ArchiveError("ARCHIVE_RESULT_MISSING")
    applications = [
        path
        for path in (archive / "Products" / "Applications").glob("*.app")
        if path.is_dir() and not path.is_symlink()
    ]
    if len(applications) != 1:
        raise ArchiveError(f"ARCHIVE_APPLICATION_COUNT={len(applications)}")
    app = applications[0]
    with (app / "Info.plist").open("rb") as handle:
        info = plistlib.load(handle)
    expected = {
        "CFBundleIdentifier": context.bundle_id,
        "CFBundleShortVersionString": context.version,
        "CFBundleVersion": context.build,
    }
    for key, value in expected.items():
        if str(info.get(key) or "") != value:
            raise ArchiveError(f"ARCHIVE_{key}_MISMATCH")
    archived_app_name = str(
        info.get("CFBundleDisplayName") or info.get("CFBundleName") or app.stem
    )
    if archived_app_name != context.app_name:
        raise ArchiveError("ARCHIVE_APPLICATION_MISMATCH")
    profile = read_profile(app / "embedded.mobileprovision")
    if (
        profile.uuid != context.signing.profile.uuid
        or profile.team_id != context.signing.team_id
        or profile.bundle_id != context.bundle_id
    ):
        raise ArchiveError("ARCHIVE_PROFILE_MISMATCH")
    _run(
        ["/usr/bin/codesign", "--verify", "--deep", "--strict", str(app)],
        "ARCHIVE_CODESIGN_VERIFY_FAILED",
    )
    details = _run(
        ["/usr/bin/codesign", "-dv", "--verbose=4", str(app)],
        "ARCHIVE_CODESIGN_DETAILS_FAILED",
    )
    output = f"{details.stdout}\n{details.stderr}"
    if (
        f"TeamIdentifier={context.signing.team_id}" not in output
        or f"Authority={context.signing.identity.common_name}" not in output
    ):
        raise ArchiveError("ARCHIVE_SIGNING_IDENTITY_MISMATCH")
    if context.entitlements_path is not None:
        entitlements_result = _run(
            ["/usr/bin/codesign", "-d", "--entitlements", ":-", str(app)],
            "ARCHIVE_ENTITLEMENTS_READ_FAILED",
        )
        entitlements_output = (
            f"{entitlements_result.stdout}\n{entitlements_result.stderr}"
        )
        start = entitlements_output.find("<?xml")
        end = entitlements_output.find("</plist>", start)
        if start < 0 or end < 0:
            raise ArchiveError("ARCHIVE_ENTITLEMENTS_INVALID")
        try:
            signed_entitlements = plistlib.loads(
                entitlements_output[start : end + len("</plist>")].encode("utf-8")
            )
        except (plistlib.InvalidFileException, ValueError) as error:
            raise ArchiveError("ARCHIVE_ENTITLEMENTS_INVALID") from error
        if signed_entitlements.get("com.apple.developer.game-center") is not True:
            raise ArchiveError("ARCHIVE_GAME_CENTER_ENTITLEMENT_MISSING")


def _context_ledger(context: ArchiveContext) -> dict[str, object]:
    return {
        "app_name": context.app_name,
        "workspace": str(context.workspace),
        "archive_path": str(context.archive_path),
        "bundle_id": context.bundle_id,
        "version": context.version,
        "build": context.build,
        "team_id": context.signing.team_id,
        "identity_fingerprint": context.signing.identity.fingerprint,
        "identity_common_name": context.signing.identity.common_name,
        "profile_uuid": context.signing.profile.uuid,
        "profile_name": context.signing.profile.name,
        "profile_game_center": context.signing.profile.game_center,
        "entitlements_path": (
            str(context.entitlements_path)
            if context.entitlements_path is not None
            else None
        ),
    }


def _worker(
    home: Path,
    config: Path,
    owner_hash: str,
    app_name: str,
    attempt_file: Path,
    *,
    game_center_recovery: bool = False,
    source_attempt: Path | None = None,
) -> int:
    try:
        _update_ledger(
            attempt_file,
            owner_hash,
            state="running",
            stage="xcode_configuration",
            pid=os.getpid(),
        )
        context = _prepare_context(
            home,
            config,
            owner_hash,
            app_name,
            game_center_recovery=game_center_recovery,
            source_attempt=source_attempt,
        )
        if context.archive_path.exists():
            raise ArchiveError("ARCHIVE_PATH_ALREADY_EXISTS")
        _update_ledger(
            attempt_file,
            owner_hash,
            state="running",
            stage="archive",
            game_center_recovery=game_center_recovery,
            **_context_ledger(context),
        )
        print("UTM_22_XCODE_CONFIG=verified", flush=True)
        result = subprocess.run(archive_command(context), check=False)
        if result.returncode != 0:
            raise ArchiveError(f"XCODEBUILD_ARCHIVE_EXIT={result.returncode}")
        _verify_archive(context)
        _update_ledger(
            attempt_file,
            owner_hash,
            state="verified",
            stage="complete",
            pid=None,
            game_center_recovery=game_center_recovery,
            **_context_ledger(context),
        )
        print("UTM_22_ARCHIVE=verified", flush=True)
        return 0
    except (ArchiveError, OSError, ValueError, plistlib.InvalidFileException) as error:
        try:
            _update_ledger(
                attempt_file,
                owner_hash,
                state="failed",
                stage="failed",
                pid=None,
                error=str(error),
            )
        except (ArchiveError, OSError, ValueError):
            pass
        return 1


def _start(
    home: Path,
    config: Path,
    owner_hash: str,
    app_name: str,
    attempt_file: Path,
    *,
    game_center_recovery: bool = False,
    source_attempt: Path | None = None,
) -> int:
    if attempt_file.exists() or attempt_file.is_symlink():
        ledger = _read_ledger(attempt_file, owner_hash)
        if bool(ledger.get("game_center_recovery")) != game_center_recovery:
            raise ArchiveError("ARCHIVE_RECOVERY_MODE_MISMATCH")
        if ledger.get("app_name") != app_name:
            raise ArchiveError("ARCHIVE_APPLICATION_MISMATCH")
        if str(ledger.get("source_attempt") or "") != str(source_attempt or ""):
            raise ArchiveError("ARCHIVE_SOURCE_ATTEMPT_MISMATCH")
        print(f"UTM_22_ARCHIVE_STATE={ledger.get('state', 'unknown')}")
        return 0
    _regular_file(config, "UPLOAD_CONFIG_UNSAFE")
    _atomic_create_json(
        attempt_file,
        {
            "owner_hash": owner_hash,
            "app_name": app_name,
            "state": "starting",
            "stage": "launch",
            "game_center_recovery": game_center_recovery,
            "source_attempt": str(source_attempt or ""),
        },
    )
    log_path = attempt_file.with_suffix(".log")
    if log_path.exists() or log_path.is_symlink():
        _update_ledger(
            attempt_file,
            owner_hash,
            state="failed",
            stage="failed",
            error="ARCHIVE_LOG_ALREADY_EXISTS",
        )
        raise ArchiveError("ARCHIVE_LOG_ALREADY_EXISTS")
    descriptor = os.open(log_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as output, open(os.devnull, "rb") as input_stream:
        worker_command = [
            sys.executable,
            str(Path(__file__).resolve()),
            "worker",
            "--home",
            str(home),
            "--config",
            str(config),
            "--owner-hash",
            owner_hash,
            "--app-name",
            app_name,
            "--attempt-file",
            str(attempt_file),
        ]
        if game_center_recovery:
            worker_command.extend(
                ["--game-center-recovery", "--source-attempt", str(source_attempt)]
            )
        process = subprocess.Popen(
            worker_command,
            stdin=input_stream,
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
            close_fds=True,
        )
    _update_ledger(attempt_file, owner_hash, pid=process.pid)
    print("UTM_22_ARCHIVE_STATE=starting")
    return 0


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create one command-line Xcode Archive"
    )
    parser.add_argument("command", choices=("start", "worker"))
    parser.add_argument("--home", required=True)
    parser.add_argument("--config", required=True)
    parser.add_argument("--owner-hash", required=True)
    parser.add_argument("--app-name", required=True)
    parser.add_argument("--attempt-file", required=True)
    parser.add_argument("--game-center-recovery", action="store_true")
    parser.add_argument("--source-attempt")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        home = Path(args.home).resolve()
        if home.is_symlink() or not home.is_dir() or home != Path.home().resolve():
            raise ArchiveError("GUEST_HOME_MISMATCH")
        if args.game_center_recovery != bool(args.source_attempt):
            raise ArchiveError("GAME_CENTER_SOURCE_ARGUMENT_INVALID")
        source_attempt = None
        if args.source_attempt:
            source_attempt = _validate_attempt_path(
                home,
                Path(args.source_attempt),
                args.owner_hash,
                game_center_recovery=False,
            )
        attempt_file = _validate_attempt_path(
            home,
            Path(args.attempt_file),
            args.owner_hash,
            game_center_recovery=args.game_center_recovery,
        )
        config = Path(args.config)
        if args.command == "start":
            return _start(
                home,
                config,
                args.owner_hash,
                args.app_name,
                attempt_file,
                game_center_recovery=args.game_center_recovery,
                source_attempt=source_attempt,
            )
        return _worker(
            home,
            config,
            args.owner_hash,
            args.app_name,
            attempt_file,
            game_center_recovery=args.game_center_recovery,
            source_attempt=source_attempt,
        )
    except (ArchiveError, OSError, ValueError) as error:
        print(f"UTM_22_ARCHIVE_ERROR={error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
