const path = require('node:path');
const root = __dirname;
const build = path.join(root, 'artifacts/test-results/M14/build');

// 白名单仅发布编译后的桌面代码与明确生成的资源，禁止将仓库根作为 files 通配目录。
module.exports = {
  appId: 'cn.orvia.desktop', productName: 'Orvia',
  directories: { app: 'apps/desktop', output: 'artifacts/test-results/M14/release' },
  files: ['dist/main/**/*', 'dist/renderer/**/*', 'package.json'],
  extraResources: [
    { from: path.join(build, 'python/orvia-backend'), to: 'backend', filter: ['**/*'] },
    { from: path.join(build, 'chromium'), to: 'chromium', filter: ['**/*'] },
    { from: path.join(build, 'runtime-manifest.json'), to: 'runtime-manifest.json' },
    { from: path.join(build, 'LICENSE.txt'), to: 'LICENSE.txt' },
  ],
  asar: true, npmRebuild: false, publish: null,
  electronDist: path.join(root, 'node_modules/electron/dist'),
  win: { target: [{ target: 'nsis', arch: ['x64'] }], signAndEditExecutable: false },
  nsis: { oneClick: false, perMachine: false, allowElevation: false, allowToChangeInstallationDirectory: true,
    createDesktopShortcut: false, createStartMenuShortcut: true, runAfterFinish: false,
    deleteAppDataOnUninstall: false, license: path.join(build, 'LICENSE.txt') },
  artifactName: 'Orvia-${version}-win-${arch}-setup.${ext}',
};
