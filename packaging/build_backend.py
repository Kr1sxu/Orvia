"""构建发布资源；固定仓库内输出，无自动下载、模型调用或用户数据读取。"""
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import playwright

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'artifacts/test-results/M08/build'


def main():
    if sys.version_info[:2] != (3, 12) or sys.platform != 'win32':
        raise SystemExit('只支持 Windows Python 3.12 构建')
    BUILD.mkdir(parents=True, exist_ok=True)
    if not BUILD.resolve().is_relative_to(ROOT) or BUILD.is_symlink():
        raise SystemExit('构建输出超出项目目录')
    driver = Path(playwright.__file__).parent / 'driver/package/browsers.json'
    browsers = json.loads(driver.read_text(encoding='utf-8'))['browsers']
    cache = Path(os.environ['LOCALAPPDATA']) / 'ms-playwright'
    versions = {}
    # 仅复制锁定 Playwright 对应的 headless-shell 和辅助程序；不复制 .links 或整个用户缓存。
    for name in ('chromium-headless-shell', 'ffmpeg', 'winldd'):
        item = next(x for x in browsers if x['name'] == name)
        folder = name.replace('-', '_') + '-' + item['revision']
        source = cache / folder
        if not source.is_dir() or not (source / 'INSTALLATION_COMPLETE').exists():
            raise SystemExit('缺少匹配浏览器资源，请执行 playwright install chromium --only-shell')
        shutil.copytree(source, BUILD / 'chromium' / folder, dirs_exist_ok=True)
        versions[name] = {k: item[k] for k in ('revision', 'browserVersion') if k in item}
    # 使用 Git 中已存在的许可证，不恢复工作区预存的 LICENSE 删除。
    license_bytes = subprocess.check_output(['git', 'show', 'HEAD:LICENSE'], cwd=ROOT)
    (BUILD / 'LICENSE.txt').write_bytes(license_bytes)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm',
                    '--distpath', str(BUILD / 'python'), '--workpath', str(BUILD / 'pyinstaller-work'),
                    str(ROOT / 'packaging/orvia-backend.spec')], cwd=ROOT, check=True)
    manifest = {'python': sys.version.split()[0], 'playwright': importlib.metadata.version('playwright'),
                'pyinstaller': importlib.metadata.version('pyinstaller'), 'browsers': versions}
    (BUILD / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('后端与浏览器资源已生成；尚未代表安装包验收通过。')


if __name__ == '__main__':
    main()
