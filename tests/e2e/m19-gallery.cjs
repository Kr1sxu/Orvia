// 实际React组件的静态SSR视觉检查；无产品事件/后端，不能替代真实Electron流程。
const {chromium}=require('@playwright/test');
const fs=require('node:fs/promises'),path=require('node:path'),{pathToFileURL}=require('node:url');
async function main(){
  const folder=path.resolve('artifacts/test-results/M19/gallery');
  const browser=await chromium.launch({executablePath:path.join(process.env.LOCALAPPDATA,'ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe'),chromiumSandbox:true});
  try{
    const page=await browser.newPage({viewport:{width:900,height:900}});const errors=[];page.on('pageerror',error=>errors.push(error.message));
    await page.goto(pathToFileURL(path.join(folder,'components.html')).href);
    await page.evaluate(()=>{document.querySelectorAll('details').forEach(node=>node.open=true);return Promise.all(Array.from(document.fonts).map(font=>font.load()))});
    await page.locator('#available').focus();const focus=await page.locator('#available').evaluate(node=>({outline:getComputedStyle(node).outlineStyle,width:getComputedStyle(node).outlineWidth}));
    if(focus.outline!=='solid'||focus.width!=='2px')throw Error('实际样式缺少可见焦点');
    await page.screenshot({path:path.join(folder,'states-900.png'),fullPage:true});
    const normal=await page.locator('#available').evaluate(node=>getComputedStyle(node).backgroundColor);await page.locator('#available').hover();
    await page.waitForFunction(value=>getComputedStyle(document.querySelector('#available')).backgroundColor!==value,normal);
    await page.emulateMedia({reducedMotion:'reduce'});const motion=await page.locator('.spinner').evaluate(node=>getComputedStyle(node).animationName);if(motion!=='none')throw Error('减少动态未停动画');
    const widths=[];
    for(const width of [900,760,500]){await page.setViewportSize({width,height:900});const overflow=await page.evaluate(()=>document.documentElement.scrollWidth>innerWidth);widths.push({width,overflow});if(overflow)throw Error('实际组件长文本横向溢出：'+width)}
    await page.screenshot({path:path.join(folder,'states-500.png'),fullPage:true});
    await fs.writeFile(path.join(folder,'report.json'),JSON.stringify({scope:'实际组件静态SSR；事件/IPC/effect未执行，非L3',realModels:0,errors,focus,motion,widths},null,2));
    if(errors.length)throw Error('静态组件脚本错误');console.log('M19实际组件静态状态/长文本/焦点/悬停/减少动态通过');
  }finally{await browser.close()}
}
main().catch(error=>{console.error(error.message);process.exitCode=1});
