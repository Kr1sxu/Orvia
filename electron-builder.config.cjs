const path = require('node:path');
const root = __dirname;
const build = path.join(root, 'artifacts/test-results/M20/build');

// 白名单仅发布编译后的桌面代码与明确生成的资源，禁止将仓库根作为 files 通配目录。
module.exports = {
  appId: 'cn.orvia.desktop', productName: 'Orvia',
  extraMetadata:{orviaAppId:'cn.orvia.desktop'},
  directories: { app: 'apps/desktop', output: 'artifacts/test-results/M20/production-release' },
  files: ['dist/main/**/*', 'dist/renderer/**/*', 'package.json'],
  extraResources: [
    { from: path.join(root, 'apps/desktop/resources/icons'), to: 'icons', filter: ['orvia.ico'] },
    { from: path.join(root, 'apps/desktop/src/renderer/assets/fonts'), to: 'font-licenses', filter: ['*-OFL.txt'] },
    { from: path.join(build, 'python/orvia-backend'), to: 'backend', filter: ['**/*'] },
    // 冻结服务不执行任意源码；M18脚本使用另行核验的私有CPython标准库资源。
    { from: path.join(build, 'script-runtime'), to: 'script-runtime', filter: ['**/*'] },
    { from: path.join(build, 'chromium'), to: 'chromium', filter: ['**/*'] },
    { from: path.join(build, 'third-party-licenses'), to: 'third-party-licenses', filter: ['**/*'] },
    { from: path.join(build, 'runtime-manifest.json'), to: 'runtime-manifest.json' },
    { from: path.join(build, 'LICENSE.txt'), to: 'LICENSE.txt' },
  ],
  asar: true, npmRebuild: false, publish: null,
  electronDist: path.join(root, 'node_modules/electron/dist'),
  win: { target: [{ target: 'nsis', arch: ['x64'] }], icon: path.join(root, 'apps/desktop/resources/icons/orvia.ico'),
    // 只关闭生产签名，保留EXE图标/元数据资源编辑；NotSigned必须由实际包复核。
    signExecutable: false },
  nsis: { oneClick: false, perMachine: false, allowElevation: false, allowToChangeInstallationDirectory: true,
    createDesktopShortcut: false, createStartMenuShortcut: true, runAfterFinish: false,
    deleteAppDataOnUninstall: false, license: path.join(build, 'LICENSE.txt'),
    installerIcon: path.join(root, 'apps/desktop/resources/icons/orvia.ico'),
    uninstallerIcon: path.join(root, 'apps/desktop/resources/icons/orvia.ico') },
  artifactName: 'Orvia-${version}-win-${arch}-setup.${ext}',
};
