"""Install explicit IAP omission support through the public UTM-18 entry."""

from __future__ import annotations

import inspect
import re
import shlex
import subprocess

from scripts.utm_18_ssh import build_invocation


def patch_skip_iap_source(source: str) -> str:
    calls = re.findall(r'^\s*execSync\([^\n]*iap-enhanced[^\n]*\);$', source, re.MULTILINE)
    if len(calls) != 1:
        raise ValueError('IAP_SKIP_SOURCE_UNSUPPORTED')
    call = calls[0].strip()
    asset_lines = [
        line for line in source.splitlines()
        if line.lstrip().startswith('execSync(`')
        and (('mv ' in line and ('${xlsxName}' in line or '${pngName}' in line))
             or ('mkdir -p' in line and '${baseDir}/cache/12345' in line))
    ]
    if len(asset_lines) != 3:
        raise ValueError('IAP_SKIP_ASSET_SOURCE_UNSUPPORTED')
    assets = '\n'.join('  ' + line.strip() for line in asset_lines)
    guarded_assets = (
        "  if (process.env.UTM_SKIP_IAP !== '1') {\n"
        + '\n'.join('    ' + line.strip() for line in asset_lines) + '\n  }'
    )
    guarded_call = (
        "  if (process.env.UTM_SKIP_IAP === '1') {\n"
        "    console.log('IAP_CREATION=skipped_by_request');\n"
        "  } else {\n    " + call + '\n  }'
    )
    completion = (
        '  () => {\n'
        "    if (process.env.UTM_SKIP_IAP === '1') {\n"
        "      console.log('FILL_DESCRIPTION=completed_without_iap');\n"
        '    }\n    process.exit(0);\n  },'
    )
    if 'UTM_SKIP_IAP' in source:
        if all(source.count(part) == 1 for part in (guarded_assets, guarded_call, completion)):
            return source
        raise ValueError('IAP_SKIP_SOURCE_CONFLICT')
    original_completion = '  () => process.exit(0),'
    if any(source.count(part) != 1 for part in (assets, '  ' + call, original_completion)):
        raise ValueError('IAP_SKIP_SOURCE_UNSUPPORTED')
    return source.replace(assets, guarded_assets, 1).replace(
        '  ' + call, guarded_call, 1
    ).replace(original_completion, completion, 1)


def prepare_guest_skip_iap(vm_name: str, vm_ip: str, vm_user: str) -> None:
    remote = (
        'import os,pathlib,pwd,re,subprocess,sys,tempfile\n'
        + inspect.getsource(patch_skip_iap_source)
        + r'''
expected_user=sys.argv[1]
if pwd.getpwuid(os.getuid()).pw_name != expected_user: raise SystemExit(61)
root=pathlib.Path.home()/"Downloads"/"Fire_One_en1.3"
path=root/"src"/"fill-description.ts"
if root.is_symlink() or path.parent.is_symlink() or path.is_symlink() or not path.is_file(): raise SystemExit(62)
original=path.read_text()
patched=patch_skip_iap_source(original)
check="const ts=require('typescript');let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>{const r=ts.transpileModule(s,{reportDiagnostics:true,compilerOptions:{target:ts.ScriptTarget.ES2020,module:ts.ModuleKind.CommonJS}});process.exit((r.diagnostics||[]).some(d=>d.category===ts.DiagnosticCategory.Error)?1:0);});"
syntax=subprocess.run(['node','-e',check],input=patched,text=True,capture_output=True,cwd=root,timeout=30)
if syntax.returncode: raise SystemExit(63)
if patched != original:
    if path.read_text() != original: raise SystemExit(64)
    fd,name=tempfile.mkstemp(prefix='.utm-script-skip-iap-',dir=path.parent)
    temporary=pathlib.Path(name)
    try:
        with os.fdopen(fd,'w') as stream:
            stream.write(patched); stream.flush(); os.fsync(stream.fileno())
        temporary.chmod(path.stat().st_mode & 0o777)
        if path.read_text() != original: raise SystemExit(64)
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)
if path.read_text() != patched: raise SystemExit(65)
print('IAP_SKIP_SUPPORT=verified')
'''
    )
    command, environment = build_invocation(
        vm_name, vm_ip,
        ['/bin/zsh', '-lc', shlex.join(['python3', '-B', '-c', remote, vm_user])],
    )
    result = subprocess.run(command, env=environment, capture_output=True, text=True, timeout=45)
    if result.returncode != 0 or result.stdout.strip() != 'IAP_SKIP_SUPPORT=verified':
        raise RuntimeError(f'IAP_SKIP_SUPPORT_FAILED_EXIT={result.returncode}')
