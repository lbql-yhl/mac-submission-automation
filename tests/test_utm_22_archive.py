from __future__ import annotations

import json
import plistlib
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from scripts.utm_22_archive import (
    ArchiveContext,
    ArchiveError,
    ProvisioningProfile,
    SigningIdentity,
    archive_command,
    archive_recovery_action,
    game_center_entitlements,
    next_build_number,
    parse_build_settings,
    read_project_version,
    select_signing_context,
    select_workspace,
)


def _workspace(root: Path, name: str) -> Path:
    workspace = root / name / "ios" / "Runner.xcworkspace"
    workspace.mkdir(parents=True)
    (workspace.parent.parent / ".git").mkdir()
    return workspace


def test_select_workspace_requires_one_regular_runner_workspace(tmp_path: Path) -> None:
    studio = tmp_path / "StudioProjects"
    workspace = _workspace(studio, "one")
    linked = studio / "linked" / "ios" / "Runner.xcworkspace"
    linked.parent.mkdir(parents=True)
    linked.symlink_to(workspace, target_is_directory=True)

    assert select_workspace(studio) == workspace.resolve()

    _workspace(studio, "two")
    with pytest.raises(ArchiveError, match="WORKSPACE_MATCH_COUNT=2"):
        select_workspace(studio)


def test_read_project_version_requires_pubspec_and_generated_config_agreement(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "project"
    generated = repository / "ios" / "Flutter" / "Generated.xcconfig"
    generated.parent.mkdir(parents=True)
    (repository / "pubspec.yaml").write_text(
        "name: example\nversion: 1.2.3+42\n", encoding="utf-8"
    )
    generated.write_text(
        "FLUTTER_BUILD_NAME=1.2.3\nFLUTTER_BUILD_NUMBER=42\n",
        encoding="utf-8",
    )

    assert read_project_version(repository) == ("1.2.3", "42")

    generated.write_text(
        "FLUTTER_BUILD_NAME=1.2.3\nFLUTTER_BUILD_NUMBER=43\n",
        encoding="utf-8",
    )
    with pytest.raises(ArchiveError, match="PROJECT_VERSION_MISMATCH"):
        read_project_version(repository)


def test_parse_build_settings_requires_one_runner_target() -> None:
    payload = json.dumps(
        [
            {
                "target": "Runner",
                "buildSettings": {
                    "PRODUCT_BUNDLE_IDENTIFIER": "com.example.app",
                    "MARKETING_VERSION": "1.2.3",
                    "CURRENT_PROJECT_VERSION": "42",
                },
            }
        ]
    )

    settings = parse_build_settings(payload)

    assert settings["PRODUCT_BUNDLE_IDENTIFIER"] == "com.example.app"
    with pytest.raises(ArchiveError, match="RUNNER_BUILD_SETTINGS_COUNT=2"):
        parse_build_settings(json.dumps(json.loads(payload) * 2))


def test_select_signing_context_requires_one_profile_and_matching_identity() -> None:
    now = datetime(2026, 8, 28, tzinfo=timezone.utc)
    identity = SigningIdentity("A" * 40, "Apple Distribution: Example (TEAM123456)")
    profile = ProvisioningProfile(
        uuid="PROFILE-UUID",
        name="Example App Store",
        team_id="TEAM123456",
        bundle_id="com.example.app",
        expires_at=now + timedelta(days=30),
        certificate_fingerprints=(identity.fingerprint,),
        game_center=True,
    )

    selected = select_signing_context([identity], [profile], "com.example.app", now)

    assert selected.identity == identity
    assert selected.profile == profile
    with pytest.raises(ArchiveError, match="SIGNING_CONTEXT_MATCH_COUNT=2"):
        select_signing_context([identity], [profile, profile], "com.example.app", now)
    with pytest.raises(ArchiveError, match="SIGNING_CONTEXT_MATCH_COUNT=0"):
        select_signing_context(
            [identity],
            [
                ProvisioningProfile(
                    **{
                        **profile.__dict__,
                        "expires_at": now - timedelta(seconds=1),
                    }
                )
            ],
            "com.example.app",
            now,
        )


def test_archive_command_contains_only_exact_command_line_configuration(
    tmp_path: Path,
) -> None:
    identity = SigningIdentity("B" * 40, "Apple Distribution: Example (TEAM123456)")
    profile = ProvisioningProfile(
        uuid="PROFILE-UUID",
        name="Example App Store",
        team_id="TEAM123456",
        bundle_id="com.example.app",
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        certificate_fingerprints=(identity.fingerprint,),
        game_center=False,
    )
    signing = select_signing_context(
        [identity],
        [profile],
        "com.example.app",
        datetime(2026, 8, 28, tzinfo=timezone.utc),
    )
    context = ArchiveContext(
        app_name="Example",
        workspace=tmp_path / "Runner.xcworkspace",
        archive_path=tmp_path / "Example.xcarchive",
        bundle_id="com.example.app",
        version="1.2.3",
        build="42",
        signing=signing,
    )

    command = archive_command(context)

    assert command[:2] == ["/usr/bin/xcodebuild", "archive"]
    for value in (
        str(context.workspace),
        "Runner",
        "Release",
        "generic/platform=iOS",
        str(context.archive_path),
        "DEVELOPMENT_TEAM=TEAM123456",
        f"CODE_SIGN_IDENTITY={identity.common_name}",
        "PROVISIONING_PROFILE_SPECIFIER=PROFILE-UUID",
    ):
        assert value in command
    for forbidden in (
        "PRODUCT_BUNDLE_IDENTIFIER=com.example.app",
        "MARKETING_VERSION=1.2.3",
        "CURRENT_PROJECT_VERSION=42",
        "SKIP_INSTALL=NO",
    ):
        assert forbidden not in command


def test_game_center_archive_only_overrides_the_recovery_build_and_entitlements(
    tmp_path: Path,
) -> None:
    identity = SigningIdentity("C" * 40, "Apple Distribution: Example (TEAM123456)")
    profile = ProvisioningProfile(
        uuid="PROFILE-UUID",
        name="Example App Store",
        team_id="TEAM123456",
        bundle_id="com.example.app",
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        certificate_fingerprints=(identity.fingerprint,),
        game_center=True,
    )
    context = ArchiveContext(
        app_name="Example",
        workspace=tmp_path / "Runner.xcworkspace",
        archive_path=tmp_path / "Example.xcarchive",
        bundle_id="com.example.app",
        version="1.2.3",
        build="43",
        signing=select_signing_context(
            [identity],
            [profile],
            "com.example.app",
            datetime(2026, 8, 28, tzinfo=timezone.utc),
        ),
        entitlements_path=tmp_path / "game-center.entitlements.plist",
    )

    command = archive_command(context)

    assert "CURRENT_PROJECT_VERSION=43" in command
    assert f"CODE_SIGN_ENTITLEMENTS={context.entitlements_path}" in command
    assert "PRODUCT_BUNDLE_IDENTIFIER=com.example.app" not in command
    assert "MARKETING_VERSION=1.2.3" not in command


def test_game_center_recovery_requires_profile_capability_and_increments_once() -> None:
    profile = ProvisioningProfile(
        uuid="PROFILE-UUID",
        name="Example App Store",
        team_id="TEAM123456",
        bundle_id="com.example.app",
        expires_at=datetime(2027, 1, 1, tzinfo=timezone.utc),
        certificate_fingerprints=("C" * 40,),
        game_center=True,
    )

    assert next_build_number("42") == "43"
    assert plistlib.loads(game_center_entitlements(profile)) == {
        "com.apple.developer.game-center": True
    }
    with pytest.raises(ArchiveError, match="PROFILE_GAME_CENTER_NOT_AUTHORIZED"):
        game_center_entitlements(
            ProvisioningProfile(**{**profile.__dict__, "game_center": False})
        )


@pytest.mark.parametrize(
    ("ledger", "alive", "expected"),
    [
        ({"state": "starting"}, True, "poll"),
        ({"state": "running"}, True, "poll"),
        ({"state": "verified"}, False, "use_verified"),
        ({"state": "starting"}, False, "stop_ambiguous"),
        ({"state": "running"}, False, "stop_ambiguous"),
        ({"state": "failed"}, False, "stop_failed"),
    ],
)
def test_archive_recovery_never_speculates(
    ledger: dict[str, object], alive: bool, expected: str
) -> None:
    assert archive_recovery_action(ledger, process_alive=alive) == expected
