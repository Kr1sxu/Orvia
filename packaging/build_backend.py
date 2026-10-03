"""构建发布资源；固定仓库内输出，无自动下载、模型调用或用户数据读取。"""
import importlib.metadata
import hashlib
import json
from itertools import chain
import os
from pathlib import Path
import shutil
import stat
import subprocess
import sys
import tomllib

import playwright
from packaging.requirements import Requirement
from orvia_backend.automation.windows_isolation import prepare_runtime

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / 'artifacts/test-results/M20/build'


def resource_files(root: Path) -> dict[str, str]:
    """只记录固定资源完整字节，拒绝链接、硬链接及异常体积，不读取用户资料。"""
    files, total, entries = {}, 0, 0
    for path in chain((root,), root.rglob('*')):
        entries += 1
        info = path.lstat()
        if path.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400 or entries > 12000:
            raise SystemExit('资源目录含链接或超出目录项预算')
        if stat.S_ISDIR(info.st_mode):
            continue
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise SystemExit('资源不是独立普通文件')
        total += info.st_size
        if total > 1536 * 1024 * 1024 or len(files) >= 10000:
            raise SystemExit('资源超过文件或字节预算')
        with path.open('rb') as stream:
            files[path.relative_to(root).as_posix()] = hashlib.file_digest(stream, 'sha256').hexdigest()
    return files


def copy_locked_resource(source: Path, destination: Path) -> dict[str, str]:
    """SDK版本目录一旦已复制只核验，不保留陈旧额外文件或覆盖异常现场。"""
    expected = resource_files(source)
    if destination.exists():
        if resource_files(destination) != expected:
            raise SystemExit('既有构建资源与锁定SDK不一致，请核对本轮构建现场')
    else:
        shutil.copytree(source, destination)
    if resource_files(source) != expected or resource_files(destination) != expected:
        raise SystemExit('资源复制前后字节不一致')
    return expected


def runtime_licenses(extra_distributions=()) -> dict[str, dict]:
    """从锁定安装分发元数据收集运行依赖原许可；不带入源码/开发凭据。"""
    pending, visited, results = ['orvia-backend', *extra_distributions], set(), {}
    locked = {item['name'].lower().replace('_', '-'): item.get('version')
              for item in tomllib.loads((ROOT / 'backend/uv.lock').read_text(encoding='utf-8'))['package']}
    while pending:
        name = pending.pop()
        distribution = importlib.metadata.distribution(name)
        normalized = distribution.metadata['Name'].lower().replace('_', '-')
        if distribution.version != locked.get(normalized):
            raise SystemExit('实际分发版本与uv.lock不符，未收集冻结许可')
        if normalized in visited:
            continue
        visited.add(normalized)
        for declaration in distribution.requires or []:
            requirement = Requirement(declaration)
            if requirement.marker is None or requirement.marker.evaluate({'extra': ''}):
                pending.append(requirement.name)
        licenses = []
        for entry in distribution.files or []:
            relative = Path(str(entry))
            filename = relative.name.casefold()
            # ONNX/PDFium等把许可放在package而非dist-info；仅复制已安装分发清单
            # 明确列出的原许可文本，保留相对层级，避免同名LICENSE互相覆盖。
            if (not filename.startswith(('license', 'licence', 'copying', 'notice', 'copyright', 'authors', 'thirdpartynotices', 'third-party'))
                    or relative.suffix.casefold() not in ('', '.txt', '.md', '.rst', '.html', '.apache', '.bsd', '.mit', '.isc')):
                continue
            if relative.is_absolute() or '..' in relative.parts:
                raise SystemExit('依赖许可相对路径异常')
            source = Path(distribution.locate_file(entry))
            info = source.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or source.is_symlink() or info.st_size > 2 * 1024 * 1024:
                raise SystemExit('依赖许可文件身份或预算异常')
            destination = BUILD / 'third-party-licenses' / normalized / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            data = source.read_bytes()
            destination.write_bytes(data)
            licenses.append({'file': str(destination.relative_to(BUILD).as_posix()), 'sha256': hashlib.sha256(data).hexdigest()})
        results[normalized] = {'version': distribution.version, 'licenses': licenses}
    # 少数锁定wheel没有附原许可：版本对应的官方原件已在开发审计时获取；
    # 构建阶段只读本仓库固定hash，不下载、不猜测新版许可或更新依赖。
    supplements = ROOT / 'packaging/third-party-licenses'
    source_manifest = supplements / 'manifest.json'
    inventory = json.loads(source_manifest.read_text(encoding='utf-8'))
    if inventory.get('schema') != 1:
        raise SystemExit('补充许可清单版本不符')
    for item in inventory['licenses']:
        distribution, filename = item['distribution'], item['file']
        if (distribution not in results or results[distribution]['version'] != item['version']
                or Path(filename).name != filename or Path(filename).suffix != '.txt'
                or not item['source'].startswith('https://github.com/')):
            raise SystemExit('补充许可的版本、来源或相对文件名不符')
        data = (supplements / filename).read_bytes()
        if len(data) != item['bytes'] or hashlib.sha256(data).hexdigest() != item['sha256']:
            raise SystemExit('补充许可原字节与固定清单不符')
        destination = BUILD / 'third-party-licenses' / distribution / filename
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        results[distribution]['licenses'].append({'file': destination.relative_to(BUILD).as_posix(),
                                                  'sha256': item['sha256'], 'source': item['source']})
    (BUILD / 'third-party-licenses/source-manifest.json').write_bytes(source_manifest.read_bytes())
    project_license = subprocess.check_output(['git', 'show', 'HEAD:LICENSE'], cwd=ROOT)
    destination = BUILD / 'third-party-licenses/orvia-backend/LICENSE.txt'
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(project_license)
    results['orvia-backend']['licenses'].append({'file': destination.relative_to(BUILD).as_posix(),
                                                'sha256': hashlib.sha256(project_license).hexdigest(), 'source': 'git HEAD:LICENSE'})
    if any(not item['licenses'] for item in results.values()):
        raise SystemExit('运行依赖原许可尚有缺项，未生成完整候选包')
    return dict(sorted(results.items()))


def frozen_distribution_owners() -> dict[str, list[str]]:
    """按实际PYZ映射已安装分发，覆盖冻结工具带入的间接/内嵌模块。"""
    from PyInstaller.archive.readers import CArchiveReader
    archive = CArchiveReader(str(BUILD / 'python/orvia-backend/orvia-backend.exe'))
    modules = archive.open_embedded_archive('PYZ.pyz').toc
    if any(name == '_pytest' or name.startswith('_pytest.') or name == 'pytest' or name.startswith('pytest.')
           or name.startswith('orvia_backend.tests') or name.startswith('backend.tests') for name in modules):
        raise SystemExit('冻结归档意外包含测试模块')
    lookup, owners = importlib.metadata.packages_distributions(), {}
    for module in sorted({name.split('.')[0] for name in modules}):
        for distribution in lookup.get(module, []):
            normalized = distribution.lower().replace('_', '-')
            owners.setdefault(normalized, []).append(module)
    return dict(sorted(owners.items()))


def desktop_licenses() -> dict[str, dict]:
    """收集实际桌面运行依赖及Electron原通知；依赖只读已安装树和锁文件。"""
    desktop = json.loads((ROOT / 'apps/desktop/package.json').read_text(encoding='utf-8'))
    locked = json.loads((ROOT / 'package-lock.json').read_text(encoding='utf-8'))['packages']
    pending, results = list(desktop['dependencies']) + ['electron'], {}
    while pending:
        name = pending.pop()
        if name in results:
            continue
        relative = 'node_modules/' + name
        package_root = ROOT / relative
        metadata = json.loads((package_root / 'package.json').read_text(encoding='utf-8'))
        if metadata['name'] != name or locked[relative]['version'] != metadata['version']:
            raise SystemExit('桌面运行依赖安装版本与锁文件不符')
        expected = desktop['dependencies'].get(name) or desktop['devDependencies'].get(name)
        if expected and expected != metadata['version']:
            raise SystemExit('桌面直接依赖没有使用固定版本')
        originals = [package_root / 'LICENSE']
        if name == 'electron':
            originals = [package_root / 'dist/LICENSE', package_root / 'dist/LICENSES.chromium.html']
            if (package_root / 'dist/version').read_text().strip() != metadata['version']:
                raise SystemExit('Electron实际运行二进制版本与锁文件不符')
        else:
            pending.extend(metadata.get('dependencies', {}))
        licenses = []
        for source in originals:
            info = source.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or source.is_symlink()
                    or getattr(info, 'st_file_attributes', 0) & 0x400 or info.st_size > 32 * 1024 * 1024):
                raise SystemExit('桌面原许可缺失、身份或预算不符')
            data = source.read_bytes()
            destination = BUILD / 'third-party-licenses/npm' / name / source.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            licenses.append({'file': destination.relative_to(BUILD).as_posix(),
                             'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
        results[name] = {'version': metadata['version'], 'licenses': licenses}
    return dict(sorted(results.items()))


def build_tool_licenses() -> dict[str, dict]:
    """只收集实际分发的冻结bootloader/NSIS stub原许可，独立于应用运行依赖。"""
    def regular_source(source: Path, limit: int = 2 * 1024 * 1024) -> bytes:
        for ancestor in (source, *source.parents):
            info = ancestor.lstat()
            if ancestor.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise SystemExit('引导资源许可来源含链接')
        info = source.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_size > limit:
            raise SystemExit('引导资源原许可身份或预算不符')
        return source.read_bytes()

    def original(source: Path, destination: Path) -> dict:
        data = regular_source(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        return {'file': destination.relative_to(BUILD).as_posix(),
                'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)}

    pyinstaller = importlib.metadata.distribution('pyinstaller')
    entries = [entry for entry in pyinstaller.files or []
               if str(entry).endswith('.dist-info/licenses/COPYING.txt')]
    if len(entries) != 1:
        raise SystemExit('锁定PyInstaller未携带唯一bootloader原许可')
    py_license = original(Path(pyinstaller.locate_file(entries[0])),
                          BUILD / 'third-party-licenses/build-tools/pyinstaller/COPYING.txt')
    # 当前锁定builder的默认toolset使用官方legacy包。拒绝会改变编译器来源的
    # 环境覆盖与自定义配置；只核对既有本机缓存，不触发SDK下载或执行构建。
    overrides = ('ELECTRON_BUILDER_NSIS_DIR', 'ELECTRON_BUILDER_CACHE',
                 'ELECTRON_BUILDER_BINARIES_DOWNLOAD_OVERRIDE_URL', 'ELECTRON_BUILDER_BINARIES_MIRROR',
                 'ELECTRON_BUILDER_BINARIES_CUSTOM_DIR', 'NPM_CONFIG_ELECTRON_BUILDER_BINARIES_CUSTOM_DIR',
                 'npm_config_electron_builder_binaries_custom_dir', 'npm_package_config_electron_builder_binaries_custom_dir')
    if any(os.environ.get(name) for name in overrides):
        raise SystemExit('NSIS来源含环境覆盖，未采用已核对toolset')
    program = "const c=require('./packaging/m20-full.config.cjs');if(c.toolsets?.nsis!=null||c.nsis?.customNsisBinary)throw Error('custom NSIS');console.log(JSON.stringify({builder:require('./node_modules/electron-builder/package.json').version}));"
    builder = json.loads(subprocess.check_output(['node', '-e', program], cwd=ROOT))['builder']
    checksum = '9877df902530f96357d13a7a31ae2b9df67f48b11ffc9a1700a7c961574ec5fa'
    sdk = (ROOT / 'node_modules/app-builder-lib/out/toolsets/windows.js').read_text(encoding='utf-8')
    if 'getBinFromUrl)("nsis-3.0.4.1", "nsis-3.0.4.1.7z", "' + checksum + '"' not in sdk:
        raise SystemExit('锁定builder默认NSIS来源改变，需重新审查原许可')
    cache = Path(os.environ['LOCALAPPDATA']) / 'electron-builder/Cache'
    archives = list((cache / 'downloads').glob('*/nsis-3.0.4.1.7z'))
    if len(archives) != 1 or hashlib.sha256(regular_source(archives[0], 32 * 1024 * 1024)).hexdigest() != checksum:
        raise SystemExit('NSIS缓存原包与锁定SDK官方hash不符')
    candidates = list((cache / 'nsis-3.0.4.1').glob('*/COPYING'))
    if len(candidates) != 1:
        raise SystemExit('锁定NSIS缓存缺少唯一原许可')
    nsis_root = candidates[0].parent
    compiler = nsis_root / 'Bin/makensis.exe'
    compiler_bytes = regular_source(compiler, 32 * 1024 * 1024)
    nsis_license = original(candidates[0], BUILD / 'third-party-licenses/build-tools/nsis/COPYING.txt')
    # 仅版本查询，无安装器输入或输出；来源必须是上面固定缓存，不能从PATH回退。
    compiler_version = subprocess.check_output([str(compiler), '/VERSION'], timeout=10).decode().strip()
    if compiler_version != 'v3.04':
        raise SystemExit('固定NSIS编译器实际版本不符')
    return {'pyinstaller': {'version': pyinstaller.version, 'scope': 'frozen backend bootloader', 'licenses': [py_license]},
            'nsis': {'version': '3.0.4.1', 'compiler_version': compiler_version, 'builder_version': builder,
                     'scope': 'installer/uninstaller stubs and compression modules',
                     'source': 'https://github.com/electron-userland/electron-builder-binaries/releases/download/nsis-3.0.4.1/nsis-3.0.4.1.7z',
                     'source_sha256': checksum, 'compiler_sha256': hashlib.sha256(compiler_bytes).hexdigest(),
                     'licenses': [nsis_license]}}


def main():
    if sys.version_info[:2] != (3, 12) or sys.platform != 'win32':
        raise SystemExit('只支持 Windows Python 3.12 构建')
    BUILD.mkdir(parents=True, exist_ok=True)
    if not BUILD.resolve().is_relative_to(ROOT) or any(path.is_symlink() or getattr(path.stat(), 'st_file_attributes', 0) & 0x400 for path in (BUILD, *BUILD.parents)):
        raise SystemExit('构建输出超出项目目录')
    version = json.loads((ROOT / 'package.json').read_text(encoding='utf-8'))['version']
    desktop_version = json.loads((ROOT / 'apps/desktop/package.json').read_text(encoding='utf-8'))['version']
    if version != desktop_version:
        raise SystemExit('根版本与桌面版本不一致，未生成候选包')
    driver = Path(playwright.__file__).parent / 'driver/package/browsers.json'
    browsers = json.loads(driver.read_text(encoding='utf-8'))['browsers']
    cache = Path(os.environ['LOCALAPPDATA']) / 'ms-playwright'
    versions = {}
    # 只复制SDK清单指定的两种Chromium和辅助程序，不复制.links或个人浏览器。
    for name in ('chromium', 'chromium-headless-shell', 'ffmpeg', 'winldd'):
        item = next(x for x in browsers if x['name'] == name)
        folder = name.replace('-', '_') + '-' + item['revision']
        source = cache / folder
        if not source.is_dir() or not (source / 'INSTALLATION_COMPLETE').exists():
            raise SystemExit('缺少匹配浏览器资源；仅开发准备可执行 playwright install chromium，本脚本不下载')
        files = copy_locked_resource(source, BUILD / 'chromium' / folder)
        versions[name] = {**{k: item[k] for k in ('revision', 'browserVersion') if k in item}, 'files': files}
    if 'COPYING.LGPLv2.1' not in versions['ffmpeg']['files']:
        raise SystemExit('锁定FFmpeg辅助资源缺少SDK携带的原许可')
    # PyInstaller服务仅处理固定协议，不是脚本解释器。另行复制当前经校验CPython3.12，
    # 复用M18 manifestless变换、_pth搜索隔离和完整hash，原安装/原签名资源不改。
    script = prepare_runtime(BUILD / 'script-runtime')
    script_manifest = script.parent / 'orvia-runtime.json'
    if not (script.parent / 'LICENSE.txt').is_file():
        raise SystemExit('私有CPython运行时缺少原许可证')
    dependencies = runtime_licenses()
    desktop_dependencies = desktop_licenses()
    build_tools = build_tool_licenses()
    credits = json.loads((BUILD / 'chromium-credits.json').read_text(encoding='utf-8'))
    credits_file = BUILD / credits['file']
    if (credits['browser_version'] != versions['chromium']['browserVersion']
            or credits['revision'] != versions['chromium']['revision']
            or credits['source_files'] != versions['chromium']['files']
            or credits['source'] != 'chrome://credits/' or credits['outbound_requests'] != 0
            or credits['file'] != 'third-party-licenses/chromium-' + credits['browser_version'] + '/credits.txt'
            or credits_file.stat().st_size != credits['bytes'] or credits['bytes'] > 32 * 1024 * 1024
            or hashlib.sha256(credits_file.read_bytes()).hexdigest() != credits['sha256']):
        raise SystemExit('完整Chromium内置原credits缺失或不对应锁定资源')
    # 使用 Git 中已存在的许可证，不恢复工作区预存的 LICENSE 删除。
    license_bytes = subprocess.check_output(['git', 'show', 'HEAD:LICENSE'], cwd=ROOT)
    (BUILD / 'LICENSE.txt').write_bytes(license_bytes)
    subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm',
                    '--distpath', str(BUILD / 'python'), '--workpath', str(BUILD / 'pyinstaller-work'),
                    str(ROOT / 'packaging/orvia-backend.spec')], cwd=ROOT, check=True)
    owners = frozen_distribution_owners()
    declared_dependencies = sorted(dependencies)
    extra_distributions = sorted(set(owners) - set(dependencies))
    dependencies = runtime_licenses(extra_distributions)
    manifest = {'python': sys.version.split()[0], 'playwright': importlib.metadata.version('playwright'),
                'pyinstaller': importlib.metadata.version('pyinstaller'), 'browsers': versions, 'app_version': version, 'signed': False,
                'script_runtime': {'version': sys.version.split()[0], 'path': 'script-runtime/python312',
                                   'transform': 'manifestless-console', 'manifest_sha256': hashlib.sha256(script_manifest.read_bytes()).hexdigest(),
                                   'files': resource_files(script.parent)},
                'frozen_backend': {'files': resource_files(BUILD / 'python/orvia-backend')},
                'desktop_worker': {'sha256': hashlib.sha256((ROOT / 'backend/src/orvia_backend/automation/desktop_worker.ps1').read_bytes()).hexdigest()},
                'dependencies': dependencies, 'desktop_dependencies': desktop_dependencies,
                'declared_runtime_distributions': declared_dependencies,
                'frozen_distribution_owners': owners, 'frozen_extra_distributions': extra_distributions,
                'build_tool_licenses': build_tools, 'chromium_credits': credits,
                'documents': {name: importlib.metadata.version(name) for name in
                              ('pypdfium2', 'rapidocr-onnxruntime', 'onnxruntime', 'pillow', 'defusedxml')},
                'publication': {name: importlib.metadata.version(name) for name in ('python-docx', 'python-pptx', 'reportlab')}}
    (BUILD / 'runtime-manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print('后端与浏览器资源已生成；尚未代表安装包验收通过。')


if __name__ == '__main__':
    main()
