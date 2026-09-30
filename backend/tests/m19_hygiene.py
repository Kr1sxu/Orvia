"""M19卫生审计：仅输出计数，合法图标PNG按固定名称白名单，绝不打印密钥。"""
import argparse
import hashlib
import json
import os
import re
import stat
import subprocess
from pathlib import Path

from live_model_preflight import credentials

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / 'artifacts/test-results/M19'
ICON_PNG = {f'apps/desktop/resources/icons/orvia-{n}.png' for n in (16, 20, 24, 32, 40, 48, 64, 128, 256)}


def git_names(*args):
    return [name for name in subprocess.check_output(['git', *args, '-z'], cwd=ROOT).decode().split('\0') if name]


def forbidden(name):
    return (name in ('LICENSE', '.zcodeignore') or name.startswith(('artifacts/', '.orvia/'))
            or any(part in ('dist', 'node_modules', '.venv', '__pycache__') for part in Path(name).parts)
            or Path(name).suffix.lower() in ('.sqlite', '.db', '.log', '.exe', '.enc')
            or (Path(name).suffix.lower() == '.png' and name not in ICON_PNG)
            or (Path(name).name.startswith('.env') and Path(name).name != '.env.example'))


def main(working=False):
    values = credentials()
    env_file = ROOT / '.env.local'
    values['TAVILY_API_KEY'] = ''
    if env_file.is_file():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            name, sep, value = line.partition('=')
            if sep and name.strip() == 'TAVILY_API_KEY':
                values[name.strip()] = value.strip().strip('"').strip("'")
    secrets = [value.encode() for value in values.values() if value]
    names = git_names('diff', '--cached', '--name-only')
    if working:
        names = sorted(set(git_names('diff', '--name-only') + git_names('ls-files', '--others', '--exclude-standard')) - {'.zcodeignore'})
    banned = sum(forbidden(name) for name in names)
    matches, private_blocks = 0, 0
    for name in names:
        content = (ROOT / name).read_bytes() if working else subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT)
        matches += sum(secret in content for secret in secrets)
        private_blocks += bool(re.search(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----\r?\n[A-Za-z0-9+/=\r\n]+-----END', content))
    # 审查实际index而非工作树：防止Windows autocrlf改变原许可/SVG字节身份。
    manifest_path = 'apps/desktop/resources/manifest.json'
    def resource_bytes(name):
        return (ROOT / name).read_bytes() if working else subprocess.check_output(['git', 'show', ':' + name], cwd=ROOT)
    manifest = json.loads(resource_bytes(manifest_path))
    resource_mismatches = 0
    for icon in manifest['icons']:
        data = resource_bytes('apps/desktop/resources/icons/' + icon['file'])
        resource_mismatches += len(data) != icon['bytes'] or hashlib.sha256(data).hexdigest() != icon['sha256']
    for font in manifest['fonts']:
        for name, digest in ((font['file'], font), (font['license'], font['licenseDigest'])):
            data = resource_bytes('apps/desktop/src/renderer/assets/fonts/' + name)
            resource_mismatches += len(data) != digest['bytes'] or hashlib.sha256(data).hexdigest() != digest['sha256']
    # 固定本轮普通产物范围，以有重叠的有界块查找，避免一次把大安装器读入内存；不沿reparse。
    count, artifact_matches = 0, 0
    overlap = max([len(secret) for secret in secrets] + [1]) - 1
    for directory, dirs, files in os.walk(RESULT, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(directory) / name).lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT]
        for name in files:
            file = Path(directory) / name
            if file.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                continue
            found = set()
            with file.open('rb') as stream:
                tail = b''
                while chunk := stream.read(4 * 1024 * 1024):
                    content = tail + chunk
                    found.update(index for index, secret in enumerate(secrets) if secret in content)
                    tail = content[-overlap:] if overlap else b''
            artifact_matches += len(found)
            count += 1
    report = {'scope': 'working tree; NOT staged acceptance' if working else 'actual staged index',
              'credential_present': {name: bool(value) for name, value in values.items()},
              'files': len(names), 'forbidden_paths': banned, 'secret_matches': matches,
              'private_key_blocks': private_blocks, 'artifact_files': count, 'artifact_secret_matches': artifact_matches,
              'resource_manifest_mismatches': resource_mismatches,
              'allowed_png': sorted(ICON_PNG)}
    (RESULT / ('hygiene-working.json' if working else 'hygiene-staged.json')).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in report.items() if key != 'allowed_png'}))
    return int(bool(banned or matches or private_blocks or artifact_matches or resource_mismatches or (not working and not names)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--working', action='store_true')
    raise SystemExit(main(parser.parse_args().working))
