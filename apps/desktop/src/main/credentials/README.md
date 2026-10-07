# 主进程凭据模块（M02/M07）

## 用途与结构
`index.ts` 提供 `CredentialVault`、角色类型与 `SafeStorageAdapter`，负责开发凭据只读加载和发布凭据系统加密存储。`synchronize.ts` 处理凭据落盘后与后端的同步边界。本目录不提供 renderer API。

## 输入输出与公共接口
构造参数 `{ development, root, userData, safeStorage }` 的路径必须由受信任主进程提供。
`load()` 异步加载；`getStatus()` 返回角色、配置状态及来源；`getSecrets()` 返回内存副本，仅用于后端私有管道；`save(role, key)` 和 `remove(role)` 仅发布模式可用。调用保存前必须成功加载。

## 依赖与配置
使用 Node.js 文件系统和注入的 Electron `safeStorage`。固定读取 `DEEPSEEK_API_KEY`、`ZHIPU_API_KEY`、`MIMO_API_KEY` 与可选 `TAVILY_API_KEY`；tavily 是搜索凭据而非第四模型角色。开发只读根目录 `.env.local`，发布只使用 `userData/credentials.enc.json` 中角色到加密 Base64 的映射。系统安全存储不可用时直接报错，不降级明文。

## 运行方式
由 Electron 主进程在 `app.whenReady()` 后实例化，注入 `safeStorage` 及 `app.getPath('userData')`，再等待 `load()`；无需独立服务。

## 测试方式
在项目根目录运行 `npx vitest run apps/desktop/tests/credentials.test.ts --reporter=json --outputFile=artifacts/test-results/M07/credentials.json`。测试使用模拟 safeStorage 和合成密钥，临时文件位于忽略的 M07 测试结果目录，不调用模型。

## 使用示例
```ts
const vault = new CredentialVault({ development: !app.isPackaged, root, userData: app.getPath('userData'), safeStorage });
await vault.load();
const status = vault.getStatus(); // 可以向界面展示，不包含秘密。
```

## 权限边界
严禁把 `getSecrets()` 的结果、密钥或底层异常正文发送到 renderer、日志或普通协议响应。开发模式不写 `.env.local`、不落系统存储。发布存储以唯一临时文件加原子替换实现；只有磁盘提交成功才更新内存。串行执行加载和修改，防止单进程并发丢失更新。损坏或解密失败会锁定写操作，要求先修复再加载。

## 已知限制
只支持简单 dotenv 语法：BOM、空行、注释、export、单/双引号；不执行转义、变量展开或命令。只保证单实例串行，不支持多个应用进程同时修改同一存储。发布安全性依赖操作系统账户及 Electron safeStorage；M02 E2E 已用合成 Key 验证 Windows 实际加密、重新加载与删除，安装包全流程仍留 M08。密钥长度限制为 4096 字符、非空且禁止 CR/LF。
磁盘提交与后端内存替换不是原子事务；同步失败后立即停止旧后端，并提示“存储已更新，但后端同步失败”，重启后重新加载。对应边界测试在 `credential-sync.test.ts`；三个模型的真实合成能力测试另见 PROGRESS。

V4-001新增独立redis凭据引用：开发变量REDIS_PASSWORD；发布加密保存/撤回沿用同一仓库与同步失败停止旧后端规则。该引用不进入固定模型配置；后端仅AuxiliaryService使用。无凭据时无认证本地服务可用，认证服务明确降级；禁止拿模型密钥代替Redis密码。
