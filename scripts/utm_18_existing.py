"""Host routing for UTM-18 using the existing Edge accessibility session."""

import hashlib
import json
import os
from pathlib import Path
import subprocess

from scripts.notion_api import api_from_env
from scripts.utm_env_generate import parse_notion_sections, validate
from scripts.utm_env import collect_host_env_manifest
from scripts.utm_direct_context import resolve_direct_context
from scripts.utm_18_attempt import create_attempt, load_single_attempt, mark_attempt
from scripts.utm_18_ssh import build_invocation
from services.host_config import optional_setting
from services.project_paths import SHARED_DIR


def _archive_attempt(attempt):
    archive_dir = attempt.ledger_path.parent.parent / 'archive'
    archive_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    archive_dir.chmod(0o700)
    archived = archive_dir / attempt.ledger_path.name
    if archived.exists() or archived.is_symlink():
        raise RuntimeError('FORCE_REPLAY_ARCHIVE_CONFLICT')
    os.replace(attempt.ledger_path, archived)
    archived.chmod(0o600)


def run_existing_browser(args):
    if not args.skip_iap:
        raise RuntimeError('EXISTING_BROWSER_REQUIRES_EXPLICIT_SKIP_IAP')
    if not args.page_title:
        raise RuntimeError('EXISTING_BROWSER_REQUIRES_EXACT_PAGE')
    context = resolve_direct_context(
        parent_title=optional_setting('SUBMISSION_HOST_MACHINE'), page_title=args.page_title,
        vm_name=args.vm_name, vm_user=args.vm_user, vm_ip=args.vm_ip,
    )
    api = api_from_env()
    api.verify_parent(context.parent_title)
    data = validate(parse_notion_sections(
        api.read_section(context.page_title, '账号信息'),
        api.read_section(context.page_title, '应用信息'), context.page_title,
    ))
    data['PROD_SERVER_URL'] = 'https://apple-callback.' + data['TOP_LEVEL_DOMAIN']
    attempt = load_single_attempt(Path(args.attempts_root), context.context_id)
    if attempt is not None and getattr(args, 'force_replay', False):
        _archive_attempt(attempt)
        attempt = None
    if attempt is not None and (not attempt.skip_iap or attempt.mode != 'native_existing' or attempt.vm_ip != args.vm_ip):
        raise RuntimeError('ATTEMPT_NATIVE_CONTEXT_MISMATCH')
    if attempt is None:
        attempt = create_attempt(Path(args.attempts_root), run_id=context.context_id,
                                 vm_name=args.vm_name, vm_ip=args.vm_ip, skip_iap=True)
        attempt = mark_attempt(attempt, state='prepared', mode='native_existing')
    source = Path(__file__).with_name('utm_18_existing_guest.py').read_text()
    payload = {'source': source, 'source_sha256': hashlib.sha256(source.encode()).hexdigest(),
               'app_name': context.app_name, 'vm_user': args.vm_user, 'attempt_id': attempt.attempt_id,
               'env_sha256': collect_host_env_manifest(SHARED_DIR)['sha256'], 'data': data}
    bridge = r'''import hashlib,json,os,pathlib,subprocess,sys
payload=json.load(sys.stdin)
source=payload.pop('source'); digest=payload.pop('source_sha256')
if hashlib.sha256(source.encode()).hexdigest()!=digest: raise SystemExit(61)
path=pathlib.Path.home()/'Downloads'/('.utm-script-native-'+digest[:16]+'.py')
if path.is_symlink(): raise SystemExit(62)
if path.exists():
    if path.read_text()!=source: raise SystemExit(63)
else:
    fd=os.open(path,os.O_CREAT|os.O_EXCL|os.O_WRONLY,0o600)
    with os.fdopen(fd,'w') as stream: stream.write(source)
result=subprocess.run([sys.executable,'-B',str(path)],input=json.dumps(payload),text=True)
raise SystemExit(result.returncode)
'''
    command, environment = build_invocation(args.vm_name, args.vm_ip, ['/usr/bin/python3', '-B', '-c', bridge])
    attempt = mark_attempt(attempt, state='running', mode='native_existing')
    result = subprocess.run(command, input=json.dumps(payload), env=environment,
                            capture_output=True, text=True, timeout=3600)
    lines = result.stdout.splitlines()
    for line in lines:
        if line.startswith(('NATIVE_', 'IAP_CREATION=', 'FILL_DESCRIPTION=')):
            print(line, flush=True)
    if result.returncode != 0:
        for line in lines:
            print(line, flush=True)
        if result.stderr:
            print('NATIVE_STDERR=' + result.stderr[-2000:], flush=True)
        reasons = [line for line in lines if line.startswith('NATIVE_BLOCKED=')]
        raise RuntimeError(reasons[-1] if reasons else 'NATIVE_SSH_FAILED')
    required = {'NATIVE_' + step.upper() + '=verified' for step in
                ('integrations','description','info','privacy','pricing','configuration')}
    required.add('NATIVE_ENROLLMENT=skipped_current_page')
    required.update({'NATIVE_EDGE_SESSION=preserved','IAP_CREATION=skipped_by_request',
                     'FILL_DESCRIPTION=completed_without_iap'})
    if not required.issubset(lines):
        raise RuntimeError('NATIVE_COMPLETION_MARKERS_MISSING')
    mark_attempt(attempt, state='verified', mode='native_existing')
    return 0
