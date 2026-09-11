import subprocess
from pathlib import Path

import pytest

from scripts import utm_18
from scripts import utm_18_attempt as attempts


SKIP_LOG = 'IAP_CREATION=skipped_by_request\nFILL_DESCRIPTION=completed_without_iap\n'
FINISHED = 'ATTEMPT_ID=' + 'a' * 32 + '\nRUN_STATE=finished\nREMOTE_NPM_EXIT=0\nREMOTE_TEE_EXIT=0\n'


def test_skip_completion_requires_both_markers_and_explicit_mode():
    result = attempts.classify_attempt(
        SKIP_LOG, FINISHED, process_running=False, expected_attempt_id='a' * 32,
        skip_iap=True,
    )
    assert result.state == 'verified'
    assert result.product_count == 0
    for log, enabled in ((SKIP_LOG, False), (SKIP_LOG.splitlines()[0], True),
                         (SKIP_LOG.splitlines()[1], True),
                         (SKIP_LOG + '增强版内购创建完成！\n统计信息: 共处理 1 个产品\n', True)):
        assert attempts.classify_attempt(
            log, FINISHED, process_running=False, expected_attempt_id='a' * 32,
            skip_iap=enabled,
        ).state != 'verified'


def test_skip_mode_persists_in_attempt_and_only_sets_that_command(tmp_path):
    attempt = attempts.create_attempt(
        tmp_path, run_id='run-demo', vm_name='abcd', vm_ip='192.0.2.10', skip_iap=True,
    )
    assert attempts.load_single_attempt(tmp_path, 'run-demo').skip_iap is True
    assert 'UTM_SKIP_IAP=1 npm run fill:description' in attempts._remote_run_script(attempt)
    normal = attempts.create_attempt(
        tmp_path, run_id='run-normal', vm_name='abcd', vm_ip='192.0.2.10', skip_iap=False,
    )
    assert normal.skip_iap is False
    assert 'UTM_SKIP_IAP=1' not in attempts._remote_run_script(normal)


def test_public_selector_defaults_to_skip_iap():
    args = utm_18.build_parser().parse_args([
        '--page-title', 'Demo-abcd', '--vm-name', 'abcd', '--vm-user', 'abcd',
        '--vm-ip', '192.0.2.10',
    ])
    assert args.skip_iap is True


def test_public_selector_accepts_skip_iap():
    args = utm_18.build_parser().parse_args([
        '--page-title', 'Demo-abcd', '--vm-name', 'abcd', '--vm-user', 'abcd',
        '--vm-ip', '192.0.2.10', '--skip-iap',
    ])
    assert args.skip_iap is True


def test_public_selector_with_iap_opts_in():
    args = utm_18.build_parser().parse_args([
        '--page-title', 'Demo-abcd', '--vm-name', 'abcd', '--vm-user', 'abcd',
        '--vm-ip', '192.0.2.10', '--with-iap',
    ])
    assert args.skip_iap is False


def test_resume_rejects_changing_iap_mode(monkeypatch, tmp_path):
    from types import SimpleNamespace
    attempt = attempts.create_attempt(
        tmp_path, run_id='run-demo', vm_name='abcd', vm_ip='192.0.2.10', skip_iap=False,
    )
    attempts.mark_attempt(attempt, state='verified')
    monkeypatch.setattr(utm_18, 'api_from_env', lambda: SimpleNamespace(verify_parent=lambda title: title))
    monkeypatch.setattr(utm_18, 'ensure_browser_session', lambda *args, **kwargs: False)
    args = SimpleNamespace(
        run_id='run-demo', parent_title='Host', page_title='Demo-abcd',
        vm_name='abcd', vm_user='abcd', vm_ip='192.0.2.10',
        attempts_root=tmp_path, skip_iap=True,
    )
    with pytest.raises(utm_18.UTM18Error, match='ATTEMPT_IAP_MODE_MISMATCH'):
        utm_18.run(args)


def test_resume_rejects_default_skip_against_legacy_with_iap_attempt(monkeypatch, tmp_path):
    from types import SimpleNamespace
    attempt = attempts.create_attempt(
        tmp_path, run_id='run-demo', vm_name='abcd', vm_ip='192.0.2.10', skip_iap=False,
    )
    attempts.mark_attempt(attempt, state='verified')
    monkeypatch.setattr(utm_18, 'api_from_env', lambda: SimpleNamespace(verify_parent=lambda title: title))
    monkeypatch.setattr(utm_18, 'ensure_browser_session', lambda *args, **kwargs: False)
    args = SimpleNamespace(
        run_id='run-demo', parent_title='Host', page_title='Demo-abcd',
        vm_name='abcd', vm_user='abcd', vm_ip='192.0.2.10',
        attempts_root=tmp_path, skip_iap=True,
    )
    with pytest.raises(utm_18.UTM18Error, match='ATTEMPT_IAP_MODE_MISMATCH'):
        utm_18.run(args)


def test_skip_source_patch_preserves_config_and_omits_iap_assets(tmp_path):
    from scripts.utm_18_skip_iap import patch_skip_iap_source

    source = r'''const effects = [];
const baseDir = '/tmp/example'; const xlsxName = 'example.xlsx'; const pngName = 'example.png';
function execSync(command) { effects.push(command); }
async function main() {
  execSync(`mv \"$HOME/Downloads/${xlsxName}\" \"${baseDir}/\"`, { stdio: 'inherit' });
  execSync(`mkdir -p \"${baseDir}/cache/12345\"`, { stdio: 'inherit' });
  execSync(`mv \"$HOME/Downloads/${pngName}\" \"${baseDir}/cache/12345/\"`, { stdio: 'inherit' });
  execSync('write API configuration');
  execSync(`cd \"${baseDir}\" && ./apple_store_tools iap-enhanced \"./${xlsxName}\" 12345`, { stdio: 'inherit' });
  console.log(JSON.stringify(effects));
}
main().then(
  () => process.exit(0),
  () => process.exit(1),
);
'''
    patched = patch_skip_iap_source(source)
    assert patch_skip_iap_source(patched) == patched
    script = tmp_path / 'flow.js'
    script.write_text(patched)
    import os
    environment = dict(os.environ, UTM_SKIP_IAP='1')
    result = subprocess.run(['node', str(script)], env=environment, capture_output=True, text=True, check=True)
    assert '["write API configuration"]' in result.stdout
    assert 'iap-enhanced' not in result.stdout
    assert 'mv ' not in result.stdout
    assert all(marker in result.stdout for marker in SKIP_LOG.splitlines())
    environment['UTM_SKIP_IAP'] = '0'
    normal = subprocess.run(['node', str(script)], env=environment, capture_output=True, text=True, check=True)
    assert 'iap-enhanced' in normal.stdout
    assert 'completed_without_iap' not in normal.stdout
    with pytest.raises(ValueError):
        patch_skip_iap_source(source.replace('iap-enhanced', 'unknown-action'))
