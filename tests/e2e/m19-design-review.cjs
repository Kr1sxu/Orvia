// 仅验证忽略目录中的候选设计板，不启动产品、后端或模型，也不代表M19最终验收。
const {chromium}=require('@playwright/test');
const fs=require('node:fs/promises');
const path=require('node:path');
const {pathToFileURL}=require('node:url');

async function main(){
  const directory=path.resolve('artifacts/test-results/M19/design');
  const browser=await chromium.launch({executablePath:path.join(process.env.LOCALAPPDATA,'ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe'),chromiumSandbox:true});
  try{
    const page=await browser.newPage({viewport:{width:1550,height:1170},deviceScaleFactor:1});
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pathToFileURL(path.join(directory,'design-review.html')).href);
    await page.evaluate(()=>document.fonts.ready);
    const fonts=await page.evaluate(()=>Array.from(document.fonts).map(font=>({family:font.family,status:font.status})));
    // 显式加载代码字库，避免欢迎页没有代码时将未使用误认为解析成功。
    await page.evaluate(()=>Promise.all(Array.from(document.fonts).map(font=>font.load())));
    const parsedFonts=await page.evaluate(()=>Array.from(document.fonts).map(font=>({family:font.family,status:font.status})));
    await page.screenshot({path:path.join(directory,'welcome-teal.png'),fullPage:true});
    await page.locator('[data-view=flow]').click();await page.screenshot({path:path.join(directory,'workflow-teal.png'),fullPage:true});
    await page.locator('[data-view=spec]').click();await page.screenshot({path:path.join(directory,'typography-teal.png'),fullPage:true});
    await page.locator('#color').selectOption('blue');
    if(await page.evaluate(()=>getComputedStyle(document.documentElement).getPropertyValue('--accent').trim())!=='#335fc7')throw Error('颜色切换未生效');
    await page.locator('#icon').selectOption('sail');
    if(await page.locator('[data-brand]').first().getAttribute('href')!=='#sail')throw Error('图标切换未生效');
    await page.locator('#font').selectOption('system');await page.screenshot({path:path.join(directory,'typography-system-blue.png'),fullPage:true});
    await page.locator('#font').selectOption('bundled');await page.locator('#color').selectOption('teal');await page.locator('#icon').selectOption('route');
    await page.locator('[data-view=welcome]').click();await page.setViewportSize({width:900,height:1180});
    const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
    await page.screenshot({path:path.join(directory,'review-narrow.png'),fullPage:true});
    const loaded=await page.evaluate(()=>Array.from(document.fonts).map(font=>({family:font.family,status:font.status})));
    const report={scope:'候选设计板，不是产品验收',realModels:0,network:'本地file字体；没有业务网络',browser:await browser.version(),errors,fontsBeforeCode:fonts,fontsParsed:parsedFonts,fonts:loaded,overflow};
    await fs.writeFile(path.join(directory,'review-check.json'),JSON.stringify(report,null,2));
    if(errors.length||overflow||parsedFonts.some(font=>font.status!=='loaded'))throw Error('设计板检查失败，请查看固定报告');
    console.log(JSON.stringify({result:'passed',fontCount:loaded.length,errors:errors.length,overflow,screenshots:5,scope:report.scope}));
  }finally{await browser.close();}
}
main().catch(error=>{console.error('M19候选设计板检查失败：'+error.message.slice(0,1600));process.exitCode=1});
