"""Explicit coin-image omission across download, staging and guest verification."""

import sys
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_utm_env_download_assets import (
    BASE_URL, FakeClient, FakeGitHubClient, record, xlsx_bytes, zip_bytes,
)
from test_utm_env_runner import FakeTransport, make_assets, make_guest_home
from scripts import utm_env as runner
from scripts import utm_env_download_assets as assets
from scripts import utm_env_guest_finalize as guest


class SkipCoinImageTests(unittest.TestCase):
    def test_skip_downloads_remaining_assets_and_verifies_guest(self):
        source = record()
        del source['fields']['金币商店截图']
        client = FakeClient([source], {'dev-token': zip_bytes(), 'sheet-token': xlsx_bytes()})
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            shared = base / 'shared'
            shared.mkdir()
            (shared / 'Fire_One_en1.3').mkdir()
            (shared / 'Fire_One_en1.3' / '.env').write_text('APP_NAME=FlagCue\n')
            summary = assets.download_assets(
                base_url=BASE_URL, app_name='FlagCue', output_root=shared,
                client=client, github_client=FakeGitHubClient(), skip_coin_image=True,
            )
            manifest = runner.collect_host_manifest(shared, 'FlagCue', skip_coin_image=True)
            self.assertTrue(runner._download_summary_matches_manifest(summary, manifest))
            self.assertEqual(list(manifest), ['FlagCue', 'FlagCue.xlsx', 'FlagCue-git'])
            self.assertEqual(client.downloaded, ['dev-token', 'sheet-token'])
            home, downloads, fire_one = make_guest_home(base)
            payload = {'app_name': 'FlagCue', 'assets': manifest,
                       'fire_one_env': runner.collect_host_env_manifest(shared),
                       'skip_coin_image': True}
            with patch.object(guest, 'GUEST_SHARED_ROOT', shared), patch.object(
                guest, '_verify_identity', return_value=(home, downloads, fire_one)
            ):
                guest.run_assets('copy', 'testvm', payload)
                verified = guest.run_assets('verify', 'testvm', payload)
                self.assertEqual(verified['asset_count'], 3)
                self.assertEqual(verified['guest_download_asset_count'], 2)
                self.assertFalse((downloads / 'FlagCue.png').exists())
                (downloads / 'FlagCue.xlsx').write_bytes(b'corrupted')
                with self.assertRaises(guest.GuestFinalizeError):
                    guest.run_assets('verify', 'testvm', payload)

    def test_default_still_requires_coin_image(self):
        source = record()
        del source['fields']['金币商店截图']
        with self.assertRaisesRegex(ValueError, '金币商店截图'):
            assets.plan_assets(source, 'FlagCue')

    def test_skip_still_requires_coin_sheet(self):
        source = record()
        del source['fields']['金币表格文件']
        with self.assertRaisesRegex(ValueError, '金币表格文件'):
            assets.plan_assets(source, 'FlagCue', skip_coin_image=True)

    def test_archive_excludes_existing_coin_image_when_skipped(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            shared = base / 'shared'
            shared.mkdir()
            make_assets(shared)
            archive = base / 'stage.tar'
            runner.build_stage_archive(shared, 'FlagCue', archive, skip_coin_image=True)
            with tarfile.open(archive) as bundle:
                names = bundle.getnames()
            self.assertNotIn('FlagCue.png', names)
            self.assertIn('FlagCue.xlsx', names)
            self.assertIn('FlagCue-git/README.md', names)
            self.assertTrue((shared / 'FlagCue.png').is_file())

    def test_guest_requires_explicit_boolean_skip_for_incomplete_manifest(self):
        with tempfile.TemporaryDirectory() as temporary:
            shared = Path(temporary)
            make_assets(shared)
            manifest = runner.collect_host_manifest(shared, 'FlagCue')
            del manifest['FlagCue.png']
            payload = {'app_name': 'FlagCue', 'assets': manifest,
                       'fire_one_env': runner.collect_host_env_manifest(shared)}
            for value in (None, False, 'true', 1):
                candidate = dict(payload)
                if value is not None:
                    candidate['skip_coin_image'] = value
                with self.subTest(value=value), self.assertRaises(guest.GuestFinalizeError):
                    guest._validate_payload(candidate)

    def test_host_requires_correct_asset_counts_after_skip(self):
        class SkipTransport(FakeTransport):
            def run_guest(self, mode, payload):
                result = super().run_guest(mode, payload)
                result.update(asset_count=3, guest_download_asset_count=2)
                return result

        with tempfile.TemporaryDirectory() as temporary:
            shared = Path(temporary)
            make_assets(shared)
            (shared / 'FlagCue.png').unlink()
            transport = SkipTransport(guest_code_path='/Users/user/StudioProjects/FlagCue')
            result = runner.finalize_guest(
                app_name='FlagCue', vm_user='user', shared_root=shared,
                transport=transport, skip_coin_image=True,
            )
            self.assertEqual(result['guest_download_asset_count'], 2)
            self.assertTrue(all(p['skip_coin_image'] is True for p in transport.payloads))
            wrong_counts = FakeTransport(guest_code_path='/Users/user/StudioProjects/FlagCue')
            with self.assertRaises(runner.UTMEnvError):
                runner.finalize_guest(
                    app_name='FlagCue', vm_user='user', shared_root=shared,
                    transport=wrong_counts, skip_coin_image=True,
                )

    def test_public_entry_accepts_explicit_skip_flag(self):
        args = runner.build_parser().parse_args([
            '--parent-title', 'Host A', '--app-name', 'FlagCue',
            '--vm-ip', '192.0.2.10', '--vm-user', 'user', '--skip-coin-image',
        ])
        self.assertTrue(args.skip_coin_image)


if __name__ == '__main__':
    unittest.main()
