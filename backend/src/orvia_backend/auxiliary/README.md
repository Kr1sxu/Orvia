# V4-001 Redis 辅助服务

本模块为会话请求状态提供可重建通知和短期元数据缓存。SQLite `chat_requests` 仍是事实来源，Redis 不保存审批、正文或唯一任务结果，也没有执行、批准、恢复或模型调用入口。

## 结构及公共接口

- `service.py`：严格配置、SQLite 派生元数据及触发器、连接生命周期、有界发布/消费、只读最近状态投影。
- `__init__.py`：导出 `AuxiliaryService`、`AuxiliaryConfig`。
- `AuxiliaryService(store)`：复用应用 SQLite 串行事务锁；`open()` 必须在 `ChatRepository.open()` 后调用。
- 所有服务方法均为 async：`configure(config, password=None)`、`replace_password(password)`、`probe()`、`status()`、`close()`；`tick_once()` 是维护/测试入口，不作为 IPC 执行工具。

配置必须恰好包含 `enabled: bool`、`host: "127.0.0.1" | "::1"`、`port: int(1..65535)`、`db: int(0..15)`。拒绝 DNS、远程地址、Redis URL、额外连接选项及 bool 冒充整数。默认关闭、127.0.0.1:6379/db0；不启动、安装或修改用户 Redis 服务。严格类型模型 `AuxiliaryConfig` 可用于协议校验。

状态返回配置、`state`（disabled/connected/degraded）、脱敏 `reason`、`password_configured`、`metadata_count`，以及 `cache_hits`、`cache_misses`、`notifications_published`、`notifications_processed`、`notifications_discarded`、`local_notifications_processed`。`recent_tasks` 最多 20 个 `{task_id, version, status}`；这些是已读回 SQL 的请求状态，不是动作/任务已完成的证据。状态查询再次核对 SQL，剔除已删除或已更新的旧投影。

## 数据、权限与恢复

SQLite 追加 `auxiliary_config`（非敏感配置、随机命名空间）和 `auxiliary_tasks`（随机 UUIDv4、仅本地的会话/请求关联、状态、修订和消费游标）。请求插入/状态更新/删除和会话删除标记通过触发器原子更新派生信息。每轮补建最多100个缺失关联；删除后的旧 Redis 随机 ID 无法复活会话或重建正文。

Redis 缓存只含随机 `task_id`、整数 `version` 与固定请求状态，TTL 30 秒。通知只含 `task_id` 和 `version`；队列最多256条、TTL60秒。没有正文、标题、路径、原始会话标识、审批令牌、凭据或模型配置。固定 Lua 脚本仅将不超过128字节的通知及256字节缓存值返回客户端；坏数据只作为未命中或丢弃处理。Lua 被服务 ACL 禁用时明确降级。

缓存命中仍须核对最新 SQLite 状态和修订。通知消费者只刷新只读投影，无法调用业务执行入口。关闭、失联、队列过期/被取走及重启时，同一投影通过本地 SQL 通知重建，单独计为 `local_notifications_processed`，不冒称 Redis 命中。

密码仅内存。`configure(..., password=None)` 保留现有内存密码；撤回必须 `replace_password(None)`，立即关闭旧连接。凭据保存与发布模式 safeStorage 由 Electron 主进程处理，本模块不写明文密码。重启只加载配置并显示 degraded；主进程注入凭据后才探测启用的端点。服务错误只映射固定原因，不输出原始错误文本。

## 依赖、资源和运行

Python 3.12、项目锁定 `redis==7.0.0`（MIT），复用 `aiosqlite`。使用 Redis 单机服务的 PING、SET/EX、RPUSH/LTRIM/EXPIRE 与固定 EVAL；不要求 Redis Cluster。真实服务版本及本轮验收环境见 `docs/PROGRESS.md`。

轮询间隔2秒；每轮最多发布100个修订、Redis/本地消费者合计最多处理100条；最近状态保留20条。单连接、单操作连接/读写超时0.25秒，禁用客户端重试；轮询工作总预算1.5秒，另留最多0.25秒关闭连接。断连后熔断，不后台无限重连；用户显式探测/配置或替换凭据才重新连接。不存在业务自动重试。

示例（应用初始化后，端点由用户自行部署）：

```python
await auxiliary.configure({"enabled": True, "host": "127.0.0.1", "port": 6379, "db": 0})
await auxiliary.probe()
print(await auxiliary.status())  # 返回固定脱敏字段，不能据此授予执行权限
await auxiliary.configure({"enabled": False, "host": "127.0.0.1", "port": 6379, "db": 0})
```

## 验证与限制

`backend/.venv/Scripts/python.exe -m pytest backend/tests/test_v4_auxiliary.py -q` 使用真实临时 SQLite 和 Redis fake 测试边界、触发器修订/删除、重建、过期/伪造通知、降级、凭据隔离、配置失败原子性、预算及只读投影；不调用真实模型。真实 Redis、跨语言和界面验收由主 Agent 单独记录，不能用本模块 fake 测试代替真实服务验收。

缓存当前仅用于请求状态元数据，不缓存资料正文或模型答案；投影最多20项，不是完整任务历史。后台通知不执行任何任务，不是分布式任务执行队列。大量历史缺失元数据按有界批次渐进重建，首次状态可能暂未全部呈现。连接目标是用户自行部署的本地服务；用户须自行限制 Redis 总内存、访问账户和磁盘持久化，不随 Orvia 安装器打包服务。

## 桌面试用与本轮依赖来源

先部署用户自己的本地Redis（Orvia不会代为部署），`npm start` → 设置 → Redis辅助服务；输入服务实际地址、端口和库号，点击“保存并启用连接”。详情可查看最近核对状态。关闭后仍可授权合成目录进行扫描；停掉服务后显示降级，恢复服务后点击“检测并恢复连接”。开发认证使用根.env.local中的REDIS_PASSWORD后重启；发布认证使用设置凭据类型“Redis独立密码”。凭据不作为配置参数从renderer传入。

新增客户端来源 [PyPI redis 7.0.0](https://pypi.org/project/redis/7.0.0/)，MIT及Python3.12兼容性在安装前检查；[官方异步客户端说明](https://redis.io/docs/latest/develop/clients/redis-py/)；wheel SHA256 `1e66c8355b3443af78367c4937484cd875fdf9f5f14e1fed14aa95869e64f6d1` 写入uv.lock。已有Python3.12.6/uv0.12.5/Docker Desktop复用，不安装本地模型、其他模块依赖或全局服务。

本轮仅验收专用Docker官方redis:7.2.4-alpine（[官方镜像说明](https://hub.docker.com/_/redis)、[Redis许可说明](https://redis.io/legal/licenses/)；该版本BSD-3-Clause），固定digest及资源见PROGRESS。这个隔离兼容性夹具不代表推荐把旧版本用于生产，不保证其它Redis版本或ACL组合；服务安全升级与部署由用户管理。未做性能收益基准、安装包或独立Windows验收。
