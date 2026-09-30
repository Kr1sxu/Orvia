// 维护资源来源与不可变字节身份；离线读取，不自动下载或改写字库/图标。
const fs=require('node:fs/promises'),path=require('node:path'),crypto=require('node:crypto');
async function main(){
  const root=path.resolve(__dirname,'../../..'),base=path.join(root,'apps/desktop');
  const fonts=[
    {file:'NotoSansSC.ttf',family:'Noto Sans SC',license:'Noto-OFL.txt',source:'仓库M16 publication/assets/NotoSansSC.ttf原字节复用',upstream:'https://github.com/google/fonts/tree/main/ofl/notosanssc'},
    {file:'InterVariable.woff2',family:'Inter',license:'Inter-OFL.txt',source:'2026-09-30从rsms/inter官方仓库获取原字库',upstream:'https://github.com/rsms/inter/blob/master/docs/font-files/InterVariable.woff2'},
    {file:'JetBrainsMono-Regular.ttf',family:'JetBrains Mono',license:'JetBrains-OFL.txt',source:'2026-09-30从JetBrains官方仓库获取原字库',upstream:'https://github.com/JetBrains/JetBrainsMono/blob/master/fonts/ttf/JetBrainsMono-Regular.ttf'},
  ];
  const digest=async file=>{const data=await fs.readFile(file);return{bytes:data.length,sha256:crypto.createHash('sha256').update(data).digest('hex')}};
  for(const font of fonts){Object.assign(font,await digest(path.join(base,'src/renderer/assets/fonts',font.file)));font.revision='sha256:'+font.sha256;font.licenseDigest=await digest(path.join(base,'src/renderer/assets/fonts',font.license))}
  const icons=[];for(const file of (await fs.readdir(path.join(base,'resources/icons'))).sort())icons.push({file,...await digest(path.join(base,'resources/icons',file))});
  const manifest={schema:'orvia.visual-resources.v1',fontPolicy:'原字节、OFL-1.1、离线；hash作为固定字库版本身份，不猜测截图字体或上游发布版本',fonts,icons,iconSource:'本项目原创折帆SVG；无文字；generated PNG/ICO由可信源重新生成'};
  await fs.writeFile(path.join(base,'resources/manifest.json'),JSON.stringify(manifest,null,2)+'\n');
  console.log('M19资源manifest更新：3字体/原许可、'+icons.length+'图标资源');
}
main().catch(error=>{console.error(error.message);process.exitCode=1});
