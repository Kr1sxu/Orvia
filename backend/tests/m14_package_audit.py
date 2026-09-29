"""M14 包内容与本轮敏感信息审查；只输出计数，不输出凭据或匹配内容。"""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / 'artifacts/test-results/M14'
PACKAGE = RESULTS / 'release/win-unpacked'


def main():
    secrets = []
    env_file = ROOT / '.env.local'
    if env_file.exists():
        for line in env_file.read_text(encoding='utf-8-sig').splitlines():
            key, sep, value = line.partition('=')
            if sep and key.strip() in ('DEEPSEEK_API_KEY', 'ZHIPU_API_KEY', 'MIMO_API_KEY', 'TAVILY_API_KEY'):
                value = value.strip().strip('\"\'')
                if value:
                    secrets.append(value.encode())
    def contains_secret(file):
        # 分块检查大型 DLL/ASAR，保留边界防止漏掉跨块匹配。
        carry = b''
        overlap = max(map(len, secrets), default=1) - 1
        with file.open('rb') as stream:
            while block := stream.read(1024 * 1024):
                block = carry + block
                if any(secret in block for secret in secrets):
                    return True
                carry = block[-overlap:] if overlap else b''
        return False
    files = [p for p in PACKAGE.rglob('*') if p.is_file()]
    assert files, '未找到目录包'
    forbidden = [p for p in files if p.name.startswith('.env') or p.suffix.lower() in ('.sqlite', '.db', '.log')
                 or p.name in ('credentials.enc.json', '.zcodeignore') or '.git' in p.parts]
    package_matches = sum(contains_secret(p) for p in files)
    artifacts = [p for p in RESULTS.rglob('*') if p.is_file() and PACKAGE not in p.parents]
    artifact_matches = sum(contains_secret(p) for p in artifacts)
    staged = subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0')
    staged = [p for p in staged if p]
    forbidden_staged = [p for p in staged if p.startswith('artifacts/') or Path(p).name in ('LICENSE','.zcodeignore')
                        or Path(p).name.startswith('.env') and p!='.env.example'
                        or Path(p).suffix.lower() in ('.sqlite','.db','.log')]
    staged_matches = sum(any(secret in subprocess.check_output(['git','show',':'+p],cwd=ROOT) for secret in secrets) for p in staged)
    report = dict(package_files=len(files), forbidden_package_files=len(forbidden), package_secret_matches=package_matches,
                  artifact_files=len(artifacts), artifact_secret_matches=artifact_matches, staged_files=len(staged),
                  forbidden_staged_files=len(forbidden_staged), staged_secret_matches=staged_matches)
    RESULTS.mkdir(parents=True,exist_ok=True)
    (RESULTS/'hygiene.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    sums = []
    for file in sorted((RESULTS/'release').glob('*.exe')):
        with file.open('rb') as stream: digest=hashlib.file_digest(stream,'sha256').hexdigest()
        sums.append(f'{digest}  {file.name}')
    (RESULTS/'release/SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='ascii')
    print(json.dumps(report))
    assert not any((forbidden, package_matches, artifact_matches, forbidden_staged, staged_matches)), '审查失败，见仅含计数的报告'


if __name__ == '__main__':
    main()
