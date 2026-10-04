"""V3-001复用实际index/本轮产物敏感检查；只输出存在性和计数。"""
import argparse
import m19_hygiene as common

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--working', action='store_true')
    common.RESULT = common.ROOT / 'artifacts/test-results/V3-001'
    common.RESULT.mkdir(parents=True, exist_ok=True)
    raise SystemExit(common.main(parser.parse_args().working))
