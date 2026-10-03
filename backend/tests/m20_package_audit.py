"""M20完整候选包的实际资源/hash/原许可与敏感审查；不执行包或供应商调用。"""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import runpy
import subprocess

from PyInstaller.archive.readers import CArchiveReader

from orvia_backend.automation.windows_isolation import _verify_runtime
from m19_resource_audit import audit_pe, png_frames

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / 'artifacts/test-results/M20'


def digest(file):
    with file.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def source_files():
    return runpy.run_path(str(ROOT/'packaging/build_backend.py'))['resource_files']


def asar_resources(resources, app_id):
    """只提取固定JSON/字库/SVG字节，不执行ASAR内代码或在renderer开放Node。"""
    program = r'''
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),asar=require('@electron/asar');
const resources=process.argv[1],root=process.argv[2],expectedIdentity=process.argv[3],archive=path.join(resources,'app.asar');
const checksum=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
const metadata=JSON.parse(asar.extractFile(archive,'package.json').toString('utf8'));
if(metadata.version!=='0.3.0-rc.1'||metadata.orviaAppId!==expectedIdentity)throw Error('实际ASAR版本或身份不符');
const manifest=JSON.parse(fs.readFileSync(path.join(root,'apps/desktop/resources/manifest.json'),'utf8'));
const files=asar.listPackage(archive).map(name=>name.replaceAll('\\','/')),fonts=[];
for(const font of manifest.fonts){
 const stem=font.file.slice(0,font.file.lastIndexOf('.')),extension=font.file.slice(font.file.lastIndexOf('.'));
 const matches=files.filter(name=>name.startsWith('/dist/renderer/assets/'+stem+'-')&&name.endsWith(extension));
 if(matches.length!==1||checksum(asar.extractFile(archive,path.normalize(matches[0].slice(1))))!==font.sha256)throw Error('ASAR原字体字节不符');
 if(checksum(fs.readFileSync(path.join(resources,'font-licenses',font.license)))!==font.licenseDigest.sha256)throw Error('字体原许可不符');
 fonts.push({family:font.family,sha256:font.sha256});
}
const brands=files.filter(name=>/^\/dist\/renderer\/assets\/brand-.+\.svg$/.test(name));
if(brands.length!==1||checksum(asar.extractFile(archive,path.normalize(brands[0].slice(1))))!==manifest.icons.find(item=>item.file==='brand.svg').sha256)throw Error('ASAR品牌SVG不符');
if(checksum(fs.readFileSync(path.join(resources,'icons/orvia.ico')))!==manifest.icons.find(item=>item.file==='orvia.ico').sha256)throw Error('包外窗口图标不符');
console.log(JSON.stringify({version:metadata.version,appId:metadata.orviaAppId,fonts,brandVerified:true,iconVerified:true,asarFiles:files.length}));
'''
    output=subprocess.check_output(['node','-e',program,str(resources),str(ROOT),app_id],cwd=ROOT)
    return json.loads(output)


def resource_audit(package, app_id='cn.orvia.m20.fulltest'):
    assert app_id in ('cn.orvia.m20.fulltest','cn.orvia.desktop')
    resources=package/'resources'
    manifest=json.loads((resources/'runtime-manifest.json').read_text(encoding='utf-8'))
    expected=json.loads((RESULTS/'build/runtime-manifest.json').read_text(encoding='utf-8'))
    assert manifest == expected and manifest['app_version']=='0.3.0-rc.1' and manifest['signed'] is False
    inventory=source_files()
    assert inventory(resources/'backend') == manifest['frozen_backend']['files'], '冻结后端不是本轮构建字节'
    assert inventory(resources/'script-runtime/python312') == manifest['script_runtime']['files'], '专用解释器字节不符'
    _verify_runtime(resources/'script-runtime/python312/python.exe')
    assert digest(resources/'script-runtime/python312/orvia-runtime.json') == manifest['script_runtime']['manifest_sha256']
    for name,item in manifest['browsers'].items():
        assert inventory(resources/'chromium'/(name.replace('-','_')+'-'+item['revision'])) == item['files']
    assert set(manifest['browsers']) == {'chromium','chromium-headless-shell','ffmpeg','winldd'}
    assert {entry.name for entry in (resources/'chromium').iterdir()} == {
        name.replace('-','_')+'-'+item['revision'] for name,item in manifest['browsers'].items()}
    ffmpeg=manifest['browsers']['ffmpeg']
    ffmpeg_license=resources/'chromium'/('ffmpeg-'+ffmpeg['revision'])/'COPYING.LGPLv2.1'
    assert digest(ffmpeg_license)==ffmpeg['files']['COPYING.LGPLv2.1'], 'FFmpeg SDK原许可缺失'
    worker=list((resources/'backend').rglob('desktop_worker.ps1'))
    assert len(worker)==1 and digest(worker[0])==manifest['desktop_worker']['sha256']
    publication=resources/'backend/_internal/orvia_backend/publication/assets'
    for filename in ('NotoSansSC.ttf','OFL.txt'):
        assert digest(publication/filename) == digest(ROOT/'backend/src/orvia_backend/publication/assets'/filename)
    # ONNXRuntime原wheel还携带三个公开算子样例，它们不是RapidOCR权重。
    # 按固定包/文件名逐个核验原hash，不能用整个backend的扩展名数量冒充模型核对。
    model_names={'ch_PP-OCRv4_det_infer.onnx','ch_PP-OCRv4_rec_infer.onnx','ch_ppocr_mobile_v2.0_cls_infer.onnx'}
    model_root=resources/'backend/_internal/rapidocr_onnxruntime/models'
    ocr=list(model_root.glob('*.onnx'))
    assert {file.name for file in ocr}==model_names, '离线OCR三个锁定权重未齐'
    rapid=importlib.metadata.distribution('rapidocr-onnxruntime')
    for file in ocr:assert digest(file)==digest(Path(rapid.locate_file('rapidocr_onnxruntime/models/'+file.name)))
    other_models=[file.relative_to(resources/'backend').as_posix() for file in (resources/'backend').rglob('*.onnx') if file not in ocr]
    license_count=0
    for name,item in manifest['dependencies'].items():
        assert item['version']==importlib.metadata.version(name) and item['licenses'], '分发版本或许可缺项'
        for license in item['licenses']:
            assert digest(resources/license['file'])==license['sha256']
            license_count+=1
    desktop_licenses=0
    for name,item in manifest['desktop_dependencies'].items():
        actual=json.loads((ROOT/'node_modules'/name/'package.json').read_text(encoding='utf-8'))
        assert item['version']==actual['version'] and item['licenses']
        for license in item['licenses']:
            assert digest(resources/license['file'])==license['sha256']
            assert (resources/license['file']).stat().st_size==license['bytes']
            desktop_licenses+=1
    assert set(manifest['desktop_dependencies'])=={'react','react-dom','scheduler','zod','electron'}
    build_licenses=0
    tools=manifest['build_tool_licenses']
    assert set(tools)=={'pyinstaller','nsis'}
    assert tools['pyinstaller']['version']==importlib.metadata.version('pyinstaller')
    assert tools['nsis']['version']=='3.0.4.1' and tools['nsis']['compiler_version']=='v3.04'
    for item in tools.values():
        assert item['licenses']
        for license in item['licenses']:
            assert digest(resources/license['file'])==license['sha256']
            assert (resources/license['file']).stat().st_size==license['bytes']
            build_licenses+=1
    credits=manifest['chromium_credits']
    assert credits['browser_version']==manifest['browsers']['chromium']['browserVersion']
    assert credits['source_files']==manifest['browsers']['chromium']['files']
    assert credits['source']=='chrome://credits/' and credits['outbound_requests']==0
    assert (resources/credits['file']).stat().st_size==credits['bytes'] and digest(resources/credits['file'])==credits['sha256']
    assert digest(resources/'third-party-licenses/source-manifest.json') == digest(ROOT/'packaging/third-party-licenses/manifest.json')
    # 直接读取PyInstaller归档目录，防止把M19复用的旧冻结服务包装成M20完整后端。
    archive=CArchiveReader(str(resources/'backend/orvia-backend.exe'))
    embedded=archive.open_embedded_archive('PYZ.pyz')
    required={'orvia_backend.chat.routing','orvia_backend.chat.scans','orvia_backend.chat.streaming',
              'orvia_backend.publication.service','orvia_backend.automation.windows_isolation',
              'orvia_backend.automation.browser','orvia_backend.configuration.client'}
    assert required <= set(embedded.toc), '冻结归档没有包含本轮M15–M20能力'
    assert not any(name=='_pytest' or name.startswith('_pytest.') or name=='pytest' or name.startswith('pytest.')
                   or name.startswith('orvia_backend.tests') or name.startswith('backend.tests') for name in embedded.toc)
    lookup=importlib.metadata.packages_distributions()
    owners={}
    for module in sorted({name.split('.')[0] for name in embedded.toc}):
        for distribution in lookup.get(module,[]):owners.setdefault(distribution.lower().replace('_','-'),[]).append(module)
    assert dict(sorted(owners.items()))==manifest['frozen_distribution_owners']
    assert set(owners)<=set(manifest['dependencies']), '实际归档分发缺少原许可'
    assert manifest['frozen_extra_distributions']==sorted(set(owners)-set(manifest['declared_runtime_distributions']))
    return {'runtimeVersion':manifest['app_version'],'frozenModulesVerified':sorted(required),
            'backendFiles':len(manifest['frozen_backend']['files']),'browsers':list(manifest['browsers']),
            'scriptRuntimeVersion':manifest['script_runtime']['version'],'scriptTransform':'manifestless-console',
            'uiaWorkerVerified':True,'ocrWeights':len(ocr),'ocrOriginalHashesVerified':True,
            'nonOcrLibraryOnnxSamples':other_models,'publicationFontVerified':True,
            'distributions':len(manifest['dependencies']),'licenseFiles':license_count,
            'declaredRuntimeDistributions':len(manifest['declared_runtime_distributions']),
            'frozenExtraDistributions':manifest['frozen_extra_distributions'],'projectTestsIncluded':False,
            'desktopDependencies':len(manifest['desktop_dependencies']),'desktopLicenseFiles':desktop_licenses,
            'buildToolOriginalLicenseFiles':build_licenses,'nsisVersion':tools['nsis']['version'],
            'completeChromiumCreditsBytes':credits['bytes'],'ffmpegSdkOriginalLicenseVerified':True,
            'visual':asar_resources(resources,app_id)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    target=parser.add_mutually_exclusive_group()
    target.add_argument('--installed',action='store_true',help='核对实际独立M20测试安装目录')
    target.add_argument('--production',action='store_true',help='独立核对普通未签候选包；不启动或安装生产身份')
    parser.add_argument('--check-local-secrets',action='store_true',help='仅内存比对开发凭据，输出计数；不调用供应商')
    args=parser.parse_args()
    release=RESULTS/('production-release' if args.production else 'release')
    package=RESULTS/'install-smoke' if args.installed else release/'win-unpacked'
    app_id='cn.orvia.desktop' if args.production else 'cn.orvia.m20.fulltest'
    product='Orvia' if args.production else 'Orvia M20 Full Test'
    installer='Orvia-0.3.0-rc.1-win-x64-setup.exe' if args.production else 'Orvia-M20-full-test-0.3.0-rc.1-win-x64-setup.exe'
    audit=resource_audit(package,app_id)
    secrets=[]
    if args.check_local_secrets:
        file=ROOT/'.env.local'
        if file.exists():
            for line in file.read_text(encoding='utf-8-sig').splitlines():
                name,separator,value=line.partition('=')
                if separator and name.strip() in ('DEEPSEEK_API_KEY','ZHIPU_API_KEY','MIMO_API_KEY','TAVILY_API_KEY'):
                    value=value.strip().strip('"\'')
                    if value:secrets.append(value.encode())
    def contains_secret(file):
        if not secrets:return False
        carry=b'';overlap=max(map(len,secrets))-1
        with file.open('rb') as stream:
            while chunk:=stream.read(1024*1024):
                chunk=carry+chunk
                if any(secret in chunk for secret in secrets):return True
                carry=chunk[-overlap:] if overlap else b''
        return False
    files=[file for file in package.rglob('*') if file.is_file()]
    forbidden=[file for file in files if file.name.startswith('.env') or file.suffix.lower() in ('.sqlite','.db','.log')
               or file.name in ('credentials.enc.json','.zcodeignore') or '.git' in file.parts]
    matches=sum(contains_secret(file) for file in files)
    artifacts=[file for file in RESULTS.rglob('*') if file.is_file() and package not in file.parents]
    artifact_matches=sum(contains_secret(file) for file in artifacts)
    staged=subprocess.check_output(['git','diff','--cached','--name-only','-z'],cwd=ROOT).decode().split('\0')
    staged=[file for file in staged if file]
    forbidden_staged=[file for file in staged if file.startswith('artifacts/') or file in ('LICENSE','.zcodeignore')
                      or Path(file).name.startswith('.env') and file!='.env.example' or Path(file).suffix.lower() in ('.sqlite','.db','.log')]
    staged_matches=sum(any(secret in subprocess.check_output(['git','show',':'+file],cwd=ROOT) for secret in secrets) for file in staged)
    pe_files=[release/'win-unpacked'/(product+'.exe'),release/installer]
    installed=RESULTS/'install-smoke'
    if not args.production and (installed/'Orvia M20 Full Test.exe').is_file():
        pe_files += [installed/'Orvia M20 Full Test.exe',installed/'Uninstall Orvia M20 Full Test.exe']
    icons=png_frames((ROOT/'apps/desktop/resources/icons/orvia.ico').read_bytes())
    pe=[audit_pe(file,icons) for file in pe_files]
    report={'module':'M20','scope':'实际目录包/安装资源/ASAR/PE/原许可与本地敏感比对；不代替业务、生产签名或独立Windows验收',
            'realModels':0,'installed':args.installed,'productionCandidate':args.production,'appId':app_id,
            'packageDirectory':str(package),'credentialsChecked':args.check_local_secrets,'resourceAudit':audit,'pe':pe,
            'peSha256':{str(file.relative_to(RESULTS)):digest(file) for file in pe_files},
            'packageFiles':len(files),'forbiddenPackageFiles':len(forbidden),'packageSecretMatches':matches,
            'artifactFiles':len(artifacts),'artifactSecretMatches':artifact_matches,'stagedFiles':len(staged),
            'forbiddenStagedFiles':len(forbidden_staged),'stagedSecretMatches':staged_matches}
    report_name='package-audit-production.json' if args.production else 'package-audit-installed.json' if args.installed else 'package-audit.json'
    (RESULTS/report_name).write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    releases=[release] if args.production else [release,RESULTS/'baseline/release']
    for output in releases:
        sums=[f'{digest(file)}  {file.name}' for file in sorted(output.glob('*.exe'))]
        if sums:(output/'SHA256SUMS.txt').write_text('\n'.join(sums)+'\n',encoding='ascii')
    print(json.dumps({'packageFiles':len(files),'licenseFiles':audit['licenseFiles'],'peFiles':len(pe),
                      'forbiddenPackageFiles':len(forbidden),'packageSecretMatches':matches,'artifactSecretMatches':artifact_matches,
                      'forbiddenStagedFiles':len(forbidden_staged),'stagedSecretMatches':staged_matches}))
    assert not any((forbidden,matches,artifact_matches,forbidden_staged,staged_matches)), '包审查失败，见仅含计数的报告'


if __name__=='__main__':
    main()
