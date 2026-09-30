"""M19 定向 PE 图标审计：读取实际产物，不启动程序，不代替任务栏/安装视觉验收。"""
from __future__ import annotations

import hashlib
import json
import struct
from pathlib import Path

import pefile
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
RESULT = ROOT / 'artifacts/test-results/M19'


def png_frames(ico: bytes) -> dict[int, bytes]:
    frames = {}
    for index in range(struct.unpack_from('<H', ico, 4)[0]):
        at = 6 + 16 * index
        size = ico[at] or 256
        length, offset = struct.unpack_from('<II', ico, at + 8)
        frames[size] = ico[offset:offset + length]
    return frames


def audit_pe(file: Path, expected: dict[int, bytes]) -> dict:
    """用 RT_GROUP_ICON 的资源 ID 关联 RT_ICON 字节，避免只检查资源名存在。"""
    pe = pefile.PE(str(file))
    icons, groups = {}, []
    for kind in pe.DIRECTORY_ENTRY_RESOURCE.entries:
        if kind.id not in (3, 14):
            continue
        for entry in kind.directory.entries:
            for language in entry.directory.entries:
                data = language.data.struct
                raw = pe.get_data(data.OffsetToData, data.Size)
                if kind.id == 3:
                    icons[entry.id] = raw
                else:
                    groups.append((entry.id, raw))
    matched = []
    for group_id, group in groups:
        frames = {}
        for index in range(struct.unpack_from('<H', group, 4)[0]):
            at = 6 + index * 14
            size = group[at] or 256
            resource_id = struct.unpack_from('<H', group, at + 12)[0]
            frames[size] = icons[resource_id]
        if frames == expected:
            matched.append(group_id)
    assert matched, f'实际PE没有与可信ICO全部尺寸精确匹配的图标组: {file.name}'
    pe.close()
    return {'file': str(file.relative_to(ROOT)), 'bytes': file.stat().st_size,
            'sha256': hashlib.sha256(file.read_bytes()).hexdigest(),
            'matching_groups': matched, 'sizes': sorted(expected)}


def main() -> None:
    source = ROOT / 'apps/desktop/resources/icons/orvia.ico'
    expected = png_frames(source.read_bytes())
    assert sorted(expected) == [16, 20, 24, 32, 40, 48, 64, 128, 256]
    release = RESULT / 'release'
    files = [release / 'win-unpacked/Orvia M19 Visual Test.exe',
             release / 'Orvia-M19-visual-test-0.2.0-rc.1-win-x64-setup.exe']
    installed = RESULT / 'install-smoke'
    if (installed / 'Orvia M19 Visual Test.exe').is_file():
        files.extend([installed / 'Orvia M19 Visual Test.exe', installed / 'Uninstall Orvia M19 Visual Test.exe'])
    shell_images = []
    for name in ('executable', 'installer', 'installed', 'uninstaller', 'shortcut'):
        image_path = RESULT / f'shell-icon-{name}.png'
        if not image_path.is_file():
            continue
        with Image.open(image_path) as actual:
            with Image.open(ROOT / f'apps/desktop/resources/icons/orvia-{actual.width}.png') as original:
                assert actual.size == original.size
                if name == 'shortcut':
                    # Shell为lnk叠加左下箭头；未覆盖区仍须逐像素一致，不能把系统箭头当源图更新失败。
                    a, b = actual.convert('RGBA'), original.convert('RGBA')
                    mask_a = {(x, y) for y in range(a.height // 2) for x in range(a.width) if a.getpixel((x, y))[3] >= 128}
                    mask_b = {(x, y) for y in range(b.height // 2) for x in range(b.width) if b.getpixel((x, y))[3] >= 128}
                    assert mask_a == mask_b and len(mask_a) >= 20, '快捷方式未覆盖区的品牌轮廓不符'
                    opaque = [(a.getpixel(p), b.getpixel(p)) for p in mask_a if a.getpixel(p)[3] == b.getpixel(p)[3] == 255]
                    assert len(opaque) >= 20 and all(x == y for x, y in opaque), '快捷方式主体颜色不符'
                    shell_images.append({'kind': name, 'size': actual.width, 'upper_half_mask_identical': True, 'opaque_pixels_identical': len(opaque), 'system_shortcut_arrow_overlay': True, 'edge_alpha': 'Shell解码的半透明边缘不要求原PNG字节相同'})
                else:
                    assert actual.convert('RGBA').tobytes() == original.convert('RGBA').tobytes(), 'Windows关联图标像素不符'
                    shell_images.append({'kind': name, 'size': actual.width, 'source_pixels_identical': True})
    report = {'scope': '实际PE资源/Windows关联图标审计；不代表任务栏、快捷方式或安装器可见视觉验收',
              'realModels': 0, 'files': [audit_pe(file, expected) for file in files], 'shell_icons': shell_images}
    (RESULT / 'pe-icons.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'actual_pe_files': len(files), 'icon_sizes': len(expected), 'passed': True}))


if __name__ == '__main__':
    main()
