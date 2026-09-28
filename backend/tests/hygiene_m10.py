"""M10 提交前检查：仅报告密钥存在性/匹配计数，不输出任何密钥值或命中文本。"""
import json
import os
from pathlib import Path
import stat
import subprocess

from live_model_preflight import credentials


def main():
    root = Path(__file__).resolve().parents[2]
    values = credentials()
    secrets = [value.encode('utf-8') for value in values.values() if value]
    staged = subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=root).decode().split('\0')
    staged = [name for name in staged if name]
    banned = [name for name in staged if name == 'LICENSE' or name.startswith(('artifacts/','.orvia/'))
              or any(part in ('dist','node_modules','.venv') for part in Path(name).parts)
              or Path(name).suffix in ('.sqlite','.db','.log','.png','.exe') or Path(name).name == '.env.local']
    staged_matches = 0
    for name in staged:
        content = subprocess.check_output(['git','show',':'+name],cwd=root)
        staged_matches += sum(secret in content for secret in secrets)
    artifact_matches = 0
    count = 0
    result_dir = root / 'artifacts/test-results/M10'
    # 不沿测试创建的链接/联接遍历；读取范围固定在本轮合成证据目录。
    for directory, dirs, files in os.walk(result_dir,followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(directory)/name).lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT]
        for name in files:
            target = Path(directory)/name
            if target.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                continue
            content = target.read_bytes()
            artifact_matches += sum(secret in content for secret in secrets)
            count += 1
    report = {'credential_present':{name:bool(value) for name,value in values.items()},
              'staged_files':len(staged),'forbidden_staged_paths':len(banned),'staged_secret_matches':staged_matches,
              'artifact_files':count,'artifact_secret_matches':artifact_matches}
    (result_dir/'hygiene.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))
    return 1 if banned or staged_matches or artifact_matches else 0


if __name__=='__main__':
    raise SystemExit(main())
