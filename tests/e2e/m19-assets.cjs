// 定向包内实际字节与源码manifest对照；不启动桌面、不读取开发凭据。
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
const {pathToFileURL}=require('node:url'),{chromium}=require('@playwright/test'),asar=require('@electron/asar');
const digest=data=>crypto.createHash('sha256').update(data).digest('hex');
async function main(){
  const base=path.resolve('apps/desktop'),out=path.resolve('artifacts/test-results/M19'),release=path.join(out,'release/win-unpacked/resources');
  const manifest=JSON.parse(await fs.readFile(path.join(base,'resources/manifest.json'),'utf8'));
  const packageFile=path.join(release,'app.asar'),files=asar.listPackage(packageFile).map(file=>file.replace(/\\/g,'/')),checked=[];
  for(const font of manifest.fonts){
    const source=await fs.readFile(path.join(base,'src/renderer/assets/fonts',font.file));if(digest(source)!==font.sha256)throw Error('字体source/hash不符');
    const stem=font.file.slice(0,font.file.lastIndexOf('.')),extension=font.file.slice(font.file.lastIndexOf('.'));
    const matches=files.filter(file=>file.startsWith('/dist/renderer/assets/'+stem+'-')&&file.endsWith(extension));if(matches.length!==1)throw Error('包内字体不唯一');
    const packed=asar.extractFile(packageFile,path.normalize(matches[0].slice(1)));if(digest(packed)!==font.sha256)throw Error('包内实际字体字节不符');
    if(digest(await fs.readFile(path.join(release,'font-licenses',font.license)))!==font.licenseDigest.sha256)throw Error('包内原许可不符');
    checked.push({family:font.family,bytes:source.length,asar:matches[0],sha256:font.sha256});
  }
  for(const item of manifest.icons)if(digest(await fs.readFile(path.join(base,'resources/icons',item.file)))!==item.sha256)throw Error('图标manifest过期');
  const ico=await fs.readFile(path.join(release,'icons/orvia.ico'));if(digest(ico)!==manifest.icons.find(i=>i.file==='orvia.ico').sha256)throw Error('包内窗口ICO不符');
  const brand=files.filter(file=>/^\/dist\/renderer\/assets\/brand-.+\.svg$/.test(file));if(brand.length!==1)throw Error('包内独立品牌SVG缺失');
  if(digest(asar.extractFile(packageFile,path.normalize(brand[0].slice(1))))!==manifest.icons.find(i=>i.file==='brand.svg').sha256)throw Error('包内品牌SVG字节不符');
  const folder=path.join(out,'icon-review');await fs.mkdir(folder,{recursive:true});
  const sizes=[16,20,24,32,40,48,64,128,256];
  const html=`<!doctype html><meta charset="utf-8"><style>body{font:14px sans-serif;background:#f6f7f8}.row{display:flex;align-items:center;gap:22px;margin:20px;padding:22px;flex-wrap:wrap}.dark{background:#22272e;color:white}figure{margin:0;text-align:center}img{display:block;margin:8px auto}</style><h1>M19 原字节图标尺寸/透明边缘检查</h1>${['light','dark'].map(theme=>`<div class="row ${theme}">${sizes.map(size=>`<figure><img width="${size}" height="${size}" src="${pathToFileURL(path.join(base,'resources/icons',`orvia-${size}.png`)).href}">${size}px</figure>`).join('')}</div>`).join('')}`;
  const target=path.join(folder,'icons.html');await fs.writeFile(target,html);
  const browser=await chromium.launch({executablePath:path.join(process.env.LOCALAPPDATA,'ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe'),chromiumSandbox:true});
  try{const page=await browser.newPage({viewport:{width:1200,height:950}});await page.goto(pathToFileURL(target).href);await page.screenshot({path:path.join(folder,'icons-light-dark.png'),fullPage:true});if(!(await page.locator('img').evaluateAll(images=>images.every(img=>img.complete&&img.naturalWidth>0))))throw Error('图标解码失败')}finally{await browser.close()}
  await fs.writeFile(path.join(out,'assets-audit.json'),JSON.stringify({scope:'实际ASAR字体/SVG、包外ICO/许可与可信manifest字节对照；headless原始图标明暗背景；非安装/任务栏验收',realModels:0,fonts:checked,icons:manifest.icons.length},null,2));
  console.log('M19实际包资源和原字节图标明暗背景通过');
}
main().catch(error=>{console.error(error.message);process.exitCode=1});
