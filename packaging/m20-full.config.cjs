const path=require('node:path');
const base=require('../electron-builder.config.cjs');
const root=path.resolve(__dirname,'..');
const build=path.join(root,'artifacts/test-results/M20/build');

// 完整候选包使用独立测试安装身份；生产身份由根配置保持，绝不覆盖旧普通Orvia。
// 冻结服务、脚本解释器和两种Chromium是分别核验的资源，不互相冒充或查PATH回退。
module.exports={...base,appId:'cn.orvia.m20.fulltest',productName:'Orvia M20 Full Test',
  extraMetadata:{...base.extraMetadata,version:'0.3.0-rc.1',orviaAppId:'cn.orvia.m20.fulltest'},
  directories:{...base.directories,output:'artifacts/test-results/M20/release'},
  extraResources:[
    {from:path.join(root,'apps/desktop/resources/icons'),to:'icons',filter:['orvia.ico']},
    {from:path.join(root,'apps/desktop/src/renderer/assets/fonts'),to:'font-licenses',filter:['*-OFL.txt']},
    {from:path.join(build,'python/orvia-backend'),to:'backend',filter:['**/*']},
    {from:path.join(build,'script-runtime'),to:'script-runtime',filter:['**/*']},
    {from:path.join(build,'chromium'),to:'chromium',filter:['**/*']},
    {from:path.join(build,'third-party-licenses'),to:'third-party-licenses',filter:['**/*']},
    {from:path.join(build,'runtime-manifest.json'),to:'runtime-manifest.json'},
    {from:path.join(build,'LICENSE.txt'),to:'LICENSE.txt'},
  ],
  artifactName:'Orvia-M20-full-test-${version}-win-${arch}-setup.${ext}',
  nsis:{...base.nsis,license:path.join(build,'LICENSE.txt'),shortcutName:'Orvia M20 Full Test'},
};
