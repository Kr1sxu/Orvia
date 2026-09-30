// 开发资源生成器：固定自有SVG → 透明PNG → 多尺寸ICO，不加载产品、后端或凭据。
const {chromium}=require('@playwright/test');
const fs=require('node:fs/promises');
const path=require('node:path');
const sizes=[16,20,24,32,40,48,64,128,256];
async function generate(){
  const folder=path.resolve(__dirname,'../resources/icons');
  const svg=await fs.readFile(path.join(folder,'brand.svg'),'utf8');
  const browser=await chromium.launch({executablePath:process.env.ORVIA_ICON_CHROMIUM||path.join(process.env.LOCALAPPDATA,'ms-playwright/chromium_headless_shell-1243/chrome-headless-shell-win64/chrome-headless-shell.exe'),chromiumSandbox:true});
  try{
    const page=await browser.newPage({viewport:{width:256,height:256},deviceScaleFactor:1});
    await page.setContent(`<style>html,body{margin:0;width:100%;height:100%;background:transparent}svg{display:block;width:100%;height:100%}</style>${svg}`);
    const pngs=[];
    for(const size of sizes){await page.setViewportSize({width:size,height:size});const png=await page.screenshot({omitBackground:true});await fs.writeFile(path.join(folder,`orvia-${size}.png`),png);pngs.push(png)}
    const directory=Buffer.alloc(6+16*sizes.length);directory.writeUInt16LE(1,2);directory.writeUInt16LE(sizes.length,4);
    let offset=directory.length;
    sizes.forEach((size,i)=>{const entry=6+i*16;directory[entry]=size===256?0:size;directory[entry+1]=directory[entry];directory.writeUInt16LE(1,entry+4);directory.writeUInt16LE(32,entry+6);directory.writeUInt32LE(pngs[i].length,entry+8);directory.writeUInt32LE(offset,entry+12);offset+=pngs[i].length});
    await fs.writeFile(path.join(folder,'orvia.ico'),Buffer.concat([directory,...pngs]));
    console.log(JSON.stringify({icons:sizes,source:'brand.svg',renderer:await browser.version()}));
  }finally{await browser.close()}
}
generate().catch(error=>{console.error('图标生成失败：'+error.message);process.exitCode=1});
