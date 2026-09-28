# M02 数据契约

## 用途与结构

`__init__.py` 定义 `ModelProfile`、`MissionCreate`、`Mission` 和 `get_profiles()`；`export_schema.py` 导出 JSON Schema。本模块只定义草稿，不执行 Agent。

## 输入、输出与公共接口

`MissionCreate(client_request_id=UUID, title=str)` 对标题去除首尾空白，再校验非空且最多 200 字符。`Mission` 增加 UUID、带时区创建时间、固定 `draft` 状态和三个角色配置元组。所有模型拒绝额外字段，构造后不可赋值；三个角色必须各出现一次。

`get_profiles()` 返回 Main、Computer、Browser 的固定供应商、模型、Base URL 和环境变量引用，任何偏离固定映射的 profile 都无法通过验证。快照不保存密钥。

## 依赖与配置

Python 3.12、Pydantic 2；无运行时配置、无环境变量读取。固定角色映射依照根目录 AGENTS.md。

## 运行方式与示例

在根目录运行 `backend/.venv/Scripts/python.exe -m orvia_backend.domain.export_schema` 更新 `contracts/m02.schema.json`。

```python
from uuid import uuid4
from orvia_backend.domain import MissionCreate, get_profiles
request = MissionCreate(client_request_id=uuid4(), title="合成草稿")
profiles = get_profiles()
```

## 测试方式

根目录执行 `backend/.venv/Scripts/python.exe -m pytest backend/tests/test_domain.py --basetemp=artifacts/test-results/M02/domain-temp`。合成数据，无 mock 或模型调用。

## 权限边界与已知限制

不读文件、数据库或凭据，不访问网络。JSON Schema 同时表达固定字段组合和三个角色各一次的约束，需要支持 Draft 2020-12 的校验器；Pydantic 在后端执行同样的业务校验。标题首尾空白处理属于输入规范化，由服务端执行。不可变约束覆盖正常模型 API，不构成对持有 Python 执行权限者的安全沙箱。M02 不支持执行状态转换或模型配置编辑。
