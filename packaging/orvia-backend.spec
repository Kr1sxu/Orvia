# PyInstaller onedir + console；只收集代码依赖与明确的数据文件，不遍历项目工作区。
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata, collect_dynamic_libs

root = Path(SPECPATH).parent
hidden = []
datas = []
for package in ('langgraph', 'langgraph.checkpoint.sqlite', 'langchain_core', 'jieba', 'trafilatura', 'lxml', 'playwright'):
    hidden += collect_submodules(package, filter=lambda name: '.tests' not in name)
for package in ('jieba', 'trafilatura', 'playwright', 'certifi'):
    datas += collect_data_files(package)
for distribution in ('orvia-backend', 'langgraph', 'langgraph-checkpoint', 'langgraph-checkpoint-sqlite', 'langchain-core', 'playwright', 'trafilatura'):
    datas += copy_metadata(distribution)

# OCR 权重/字典和 PDF 原生库必须随包携带，运行时不下载或查找开发环境。
for package in ('rapidocr_onnxruntime', 'pypdfium2', 'pypdfium2_raw', 'onnxruntime'):
    datas += collect_data_files(package)
binaries = collect_dynamic_libs('pypdfium2_raw') + collect_dynamic_libs('onnxruntime')

a = Analysis([str(root / 'packaging/backend_entry.py')], pathex=[str(root / 'backend/src')],
             binaries=binaries, datas=datas, hiddenimports=hidden,
             excludes=['pytest', 'tkinter', 'unittest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='orvia-backend',
          debug=False, bootloader_ignore_signals=False, strip=False, upx=False, console=True)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='orvia-backend')
