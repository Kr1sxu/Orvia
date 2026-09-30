const base=require('../electron-builder.config.cjs');
// 定向视觉资源包：隔离安装标识/输出并复用M14冻结资源，绝不当M20后全功能发行验收。
module.exports={...base,appId:'cn.orvia.m19.visualtest',productName:'Orvia M19 Visual Test',
  extraMetadata:{...base.extraMetadata,orviaAppId:'cn.orvia.m19.visualtest'},
  directories:{...base.directories,output:'artifacts/test-results/M19/release'},
  artifactName:'Orvia-M19-visual-test-${version}-win-${arch}-setup.${ext}',
  nsis:{...base.nsis,shortcutName:'Orvia M19 Visual Test',createStartMenuShortcut:true},
};
