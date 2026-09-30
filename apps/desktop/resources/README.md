# M19 视觉资源与窗口

用户于2026-09-30确认B雾蓝强调色、B原创折帆非文字图标，其余A：内置开源字体、Windows11 x64普通桌面、原生小圆角与系统控制。M19已实现并完成本机原生桌面、实际定向安装/升级/卸载、快捷方式与任务栏验收，实际命令及限制见PROGRESS。

## 结构、输入输出与公共接口

- `icons/brand.svg`是可维护的原创几何源，三块折面呼应“航”，不用汉字/字母，不复制参考产品。`orvia-{16,20,24,32,40,48,64,128,256}.png`透明资源与`orvia.ico`均从该源生成；SVG供页面，ICO供窗口/EXE/NSIS/快捷方式。
- `manifest.json`记录每个生产图标、字体及原许可的SHA256、字节数和来源；字体固定版本身份为内容hash，不推断上游版本号。
- 根`.gitattributes`对源SVG/三原许可禁用换行转换，保留上游许可行尾空格；卫生审计同时核对实际暂存字节与manifest，避免Windows autocrlf造成重新检出后的资源身份失配。
- `../src/renderer/assets/fonts/`保留Noto Sans SC、Inter Variable与JetBrains Mono Regular及各自OFL-1.1原许可。原字库未删减字形、未改名、未安装到系统。前端原始字库约17.54MiB；M16后端另有Noto，当前重复携带，接受离线一致性所需体积，不称安装器仅增此大小。
- `../src/renderer/Visual.tsx`只提供装饰性`BrandMark`/固定功能`Icon`；名称由相邻文本或aria-label提供。
- `../src/renderer/style.css`统一中英文字体、数字、代码、浅色变量、卡片与状态、滚动、键盘焦点、减少动态和高对比偏好。Inter→Noto→Windows系统sans；代码JetBrains Mono→Consolas→Noto→monospace，禁用编程连字。字体只从本地应用资源加载。
- `../src/main/window-presentation.ts`仅接受主进程可信资源根，返回原生窗口选项并绑定F11/Escape。默认1120×880、最小760×560；原生标题控制、拖动、双击与thickFrame边缘缩放，没有新增窗口控制IPC。
- `taskbarAppId`仅从可信安装package.json识别固定生产`cn.orvia.desktop`或定向测试`cn.orvia.m19.visualtest`；主进程/窗口/安装器使用一致标识，并以`setAppDetails`指定可信ICO与重启路径。这些值只供Windows图标分组，不参与权限判断，也不接受renderer参数。

## 运行、维护与示例

修改源SVG后在仓库根执行`node apps/desktop/scripts/generate-icons.cjs`，再执行`node apps/desktop/scripts/generate-resource-manifest.cjs`与`npm run build`。生成器使用项目既有Playwright和本机SDK Chromium153 Headless Shell/revision1243；若迁移开发机，可通过仅开发环境`ORVIA_ICON_CHROMIUM`指定已验证的可信Chromium，不由renderer选择，不属于固定业务Browser角色。生成器只渲染自有SVG，无后端/凭据/网络/模型。

日常启动`npm start`。欢迎/侧栏/标题显示折帆与“序航 Orvia”；设置、文件/审批/证据/导出、M15–M18复用既有业务组件和事件处理。需求类型、选择目录、添加附件仍各自保留，M20统一入口/路由/流式协议未实施。Vite `assetsInlineLimit:0`将小SVG独立打包，适配既有`img-src 'self'`，无需放宽CSP。

## 验证

L0构建/许可/hash；L1 `npx vitest run apps/desktop/tests/m19-visual.test.ts apps/desktop/tests/m19-gallery.test.tsx`，后者把实际React组件的合成静态SSR写入被忽略结果目录。`node tests/e2e/m19-gallery.cjs`以headless验证状态/长文本/焦点/减少动态，不执行组件事件，不替代L3。

产品检查为`ORVIA_TEST_MODULE=M19`下`npx playwright test tests/e2e/m19.spec.ts`；原生桌面项必须先取得用户可见桌面时段并设置`ORVIA_M19_DESKTOP_ALLOWED=1`，否则跳过且不能声称通过。真实桌面裁切核对前台HWND，renderer截图只证明页面。定向包/实际PE/安装/快捷方式/任务栏流程见packaging README和PROGRESS。所有产物仅在`artifacts/test-results/M19/`。

## 权限与限制

呈现层不读取密钥、不执行SVG/源码/参考图里的指令，不改sandbox/contextIsolation/CSP、严格IPC、后端授权和原生批准，M18隔离继续由原模块维护。系统原生审批框沿用操作系统外观与权限链；专用Browser目标网页及外部应用仍是它们自己的界面。

原生圆角支持Windows11 x64普通桌面会话；本机25H2/build26200是实际环境，Windows10、VM/AVD、其他系统版本未覆盖。普通窗系统弧度约8DIP，较参考图18–20px小；最大化/全屏/贴靠由系统取消圆角。CSS容器圆角不算外轮廓证据。100/125/150/200%的force-device-scale-factor只表示渲染倍率，实际系统DPI96分开记录。

真实任务栏新测试分组已查看为折帆图标；开发/旧Orvia分组曾显示Electron旧图，不能保证已有固定项自动刷新。记录保留，不清系统缓存；生产稳定AppId保留以兼容升级。实际快捷方式带Windows箭头叠层，与PE资源/源图分别核验。生产签名/独立Windows验收仍暂缓，M20后全功能安装版资源与开发版对照待办保留。
