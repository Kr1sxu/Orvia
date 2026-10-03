# M02 跨语言数据契约

M02导出Schema和下述草稿定义保留。M20真实会话/事件契约由后端`chat/contracts.py`、`chat/streaming.py`与桌面`main/m20-contracts.ts`同时strict验证；没有扩大此目录的Mission草稿权限。事件带`v=1`、私有传输`id`、`conversation_id`、业务`request_id`、`stream_id`、递增`seq`和固定`kind/payload`，状态/扫描批次/模型增量/终态分别验证，完整事件12KiB、stdio帧64KiB。

`chat.natural/continue/material.remove/revoke`等固定接口不接受路径、命令、工具名、模型、approved字段；目录/文件选择仍仅主进程可提供。`chat.stream.pull/ack`是主进程有界传输回收，不能授予业务权限、重发请求或确认执行。扫描分页绑定当前会话不可变`scan_id`和实际游标，不重新扫描。公共快照的`model_partial`带原流身份/seq和未核验标记，不能成为成功引用或M16来源。字段和预算以源契约为准，见[对话README](../backend/src/orvia_backend/chat/README.md)。

M20测试入口是`apps/desktop/tests/m20-contracts.test.ts`、`m20-transport.test.ts`与`backend/tests/test_m20_transport.py`；实际stdio、重复/乱序/帧预算、权限和重启证据在[PROGRESS](../docs/PROGRESS.md)。模型mock、真实供应商和安装验收分别记录，不由Schema通过推断整模块完成。

## 用途与目录结构

`m02.schema.json` 是从 Python Pydantic 数据模型导出的 JSON Schema 集合，顶层包含 `ModelProfile`、`MissionCreate` 和 `Mission`。本目录不包含服务端执行代码。

## 输入、输出与公共接口

输入为 `backend/src/orvia_backend/domain/` 中的模型定义，输出为 UTF-8 JSON。模型快照有 Main、Computer、Browser 三个角色；JSON 中元组序列化为数组。UUID 和带时区日期使用字符串。

## 依赖与配置

依赖已安装的 Python 后端和 Pydantic 2；没有凭据或环境配置。Schema 版本随源代码提交管理；不等同于 SQLite schema 版本。

## 运行方式与使用示例

在项目根目录运行 `backend/.venv/Scripts/python.exe -m orvia_backend.domain.export_schema`。桌面端可用 `MissionCreate` 条目核对 `client_request_id` 和 `title` 字段，最终以服务端验证结果为准。示例输入：

```json
{"client_request_id":"d78bd7b6-5a4a-4d15-bf88-1735d20be225","title":"合成草稿"}
```

## 测试方式

契约行为由 `backend/tests/test_domain.py` 验证。生成后检查 JSON 可解析，并比较生成内容与模型的 `model_json_schema()` 结果；测试产物应放 `artifacts/test-results/M02/`。

## 权限边界与已知限制

Schema 不包含密钥，也不授予文件或网络权限。跨字段固定模型映射使用 `oneOf` 与 `const` 表达；三个角色各一个使用 `contains`、`minContains` 和 `maxContains` 表达，需要支持 Draft 2020-12 的校验器（例如 Ajv2020）。后端同时通过 Pydantic 强制校验；标题首尾空白规范化在服务端执行。当前没有自动生成 TypeScript 类型，调用端仍应维护运行时响应校验。只定义草稿，不代表任务执行能力已可用。
