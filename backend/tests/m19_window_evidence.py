"""只分析本轮自有前台原生截图的四角像素；DWM配置值不单独作为圆角证明。"""
import json
from pathlib import Path
from PIL import Image

RESULT = Path(__file__).resolve().parents[2] / 'artifacts/test-results/M19/product'


def distance(a, b):
    return sum(abs(x - y) for x, y in zip(a, b))


def main():
    report = json.loads((RESULT / 'native-window.json').read_text(encoding='utf-8'))
    output = []
    for state in report['states']:
        with Image.open(RESULT / state['native']['image']) as raw:
            image = raw.convert('RGB')
            width, height = image.size
            if state['name'] in ('ordinary', 'restored', 'minimum'):
                background = image.getpixel((0, 0))
                corners = [(10, 10), (width - 11, 10), (10, height - 11), (width - 11, height - 11)]
                inside = [(30, 30), (width - 31, 30), (30, height - 31), (width - 31, height - 31)]
                samples = []
                for edge, inner in zip(corners, inside):
                    a, b = image.getpixel(edge), image.getpixel(inner)
                    assert distance(a, background) < distance(b, background), '普通窗口四角未呈现自有背景'
                    assert distance(a, b) > 35, '普通窗口四角与内侧颜色不足以证明外轮廓'
                    samples.append({'corner': a, 'inside': b})
                output.append({'state': state['name'], 'native_screenshot': state['native']['image'], 'background': background, 'rounded_corners': samples})
            else:
                assert state['max'] or state['snap'] or state['full']
                # 四角为系统边线/窗口浅色，不能出现自有蓝色背景；截图裁切没有周边padding。
                corners = [image.getpixel(p) for p in [(0, 0), (width-1, 0), (0, height-1), (width-1, height-1)]]
                assert all(max(c) - min(c) < 25 for c in corners), '边缘状态出现圆角背景'
                output.append({'state': state['name'], 'native_screenshot': state['native']['image'], 'square_edge_pixels': corners})
    (RESULT / 'corner-pixels.json').write_text(json.dumps({'scope': '真实桌面截图像素与系统状态关联；非renderer截图', 'states': output}, indent=2), encoding='utf-8')
    print(f'M19真实窗口四角像素核验通过：{len(output)}状态，普通/还原/最小窗各4圆角')


if __name__ == '__main__':
    main()
