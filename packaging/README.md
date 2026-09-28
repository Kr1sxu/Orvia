# M08 发布与验收

`build_backend.py` 构建 PyInstaller onedir 后端，`orvia-backend.spec` 保留 console stdio 并收集 Playwright、trafilatura、LangGraph 数据。`electron-builder.config.cjs` 只把桌面 dist、冻结后端、锁定 Chromium、runtime-manifest 和许可证放入包；发布进程从 `process.resourcesPath` 启动 `backend/orvia-backend.exe`，不查找系统 Python。

```powershell
.\backend\.venv\Scripts\python.exe -X utf8 packaging/build_backend.py
npm run package:dir
npm run package:win
```

动态浏览器使用配套 Chromium Headless Shell；浏览器缓存不读取用户目录，用户数据仅写 Electron userData。安装器未配置签名证书。

测试只使用合成目录、合成凭据和 `data:` 页面，不调用真实模型、Tavily 或公网。无开发环境 Windows 独立机未提供，当前验收清空开发 PATH 并实际安装/卸载隔离目录。
