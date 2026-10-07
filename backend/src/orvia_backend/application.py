"""M02 应用服务：可信主进程初始化数据目录和凭据，UI 只能创建/读取草稿。"""

import json
import asyncio
import errno
import sqlite3
from pathlib import Path
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .configuration import Credentials, ModelRegistry
from .browser import BrowserService
from .browser.service import ReadRequest, SearchRequest
from .domain import MissionCreate
from .protocol import Session, error_response
from .storage import Store
from .computer.contracts import GrantRequest, MissionRequest, ToolRequest
from .computer.gateway import ComputerGateway
from .computer.actions import Action, ActionPlanRequest, ActionService
from .agents.graph import MissionGraph
from .context import ContextError, ContextService
from .computer.paths import ToolError
from .computer.system import SystemToolError
from .chat import ChatService
from .auxiliary import AuxiliaryService, AuxiliaryConfig
from .skills import SkillsService, SkillError
from .retrieval import RetrievalService, RetrievalError
from .retrieval.runtime import LocalEmbedder
from .retrieval.model import manifest as embedding_manifest
from .retrieval.integration import ScopedRetrieval
from .memory import MemoryService, MemoryError


class Params(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class Initialize(Params):
    data_directory: str
    credentials: Credentials


class ReplaceCredentials(Params):
    credentials: Credentials


class RetrievalConversation(Params):
    id: Annotated[str, Field(pattern=r"^[0-9a-f-]{36}$")]


class RetrievalQuery(RetrievalConversation):
    query: str = Field(min_length=1, max_length=200)


class ModelPath(Params):
    path: str = Field(min_length=1, max_length=1000)


class MemoryContext(RetrievalConversation):
    query: str = Field(default="", max_length=200)


class MemorySearch(Params):
    query: str = Field(min_length=1, max_length=200)


class MemoryGenerate(RetrievalConversation):
    revision: str = Field(pattern=r"^[0-9a-f]{64}$")


class MemoryRecord(RetrievalConversation):
    memory_id: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]


class MemoryCorrect(MemoryRecord):
    value: str = Field(min_length=1, max_length=300)


class MissionId(Params):
    id: Annotated[str, Field(min_length=1, max_length=64)]


class OperationId(Params):
    operation_id: Annotated[str, Field(min_length=1, max_length=64)]


class GraphStart(Params):
    mission_id: str
    goal: str = Field(min_length=1, max_length=500)
    root: str = Field(min_length=1, max_length=1000)
    actions: list[Action] = Field(min_length=1, max_length=100)
    thread_id: Annotated[str, Field(min_length=1, max_length=128)]


class GraphThread(Params):
    thread_id: Annotated[str, Field(min_length=1, max_length=128)]


class ContextIndex(Params):
    mission_id: str = Field(min_length=1, max_length=128)
    source: str = Field(min_length=1, max_length=1000)
    text: str = Field(min_length=1, max_length=256_000)


class ContextSearch(Params):
    mission_id: str = Field(min_length=1, max_length=128)
    query: str = Field(min_length=1, max_length=200)
    limit: int = Field(default=5, ge=1, le=20, strict=True)


class ContextMission(Params):
    mission_id: str = Field(min_length=1, max_length=128)


class ContextClear(ContextMission):
    source: str | None = Field(default=None, max_length=1000)


class ContextPreference(Params):
    mission_id: str = Field(min_length=1, max_length=128)
    key: str = Field(min_length=1, max_length=64)
    value: str = Field(max_length=1000)


class ContextSummary(Params):
    mission_id: str = Field(min_length=1, max_length=128)
    summary: str = Field(max_length=4000)
    revision: int = Field(ge=1, le=1_000_000, strict=True)


class SkillIdentity(Params):
    skill_id: str = Field(pattern=r'^[a-z][a-z0-9-]{1,63}$')


class SkillList(Params):
    offset: int = Field(default=0, ge=0, le=36, strict=True)


class SkillEnable(SkillIdentity):
    enabled: bool = Field(strict=True)


class SkillImport(Params):
    path: str = Field(min_length=1, max_length=1000)


class SkillRegister(Params):
    review_id: str = Field(min_length=1, max_length=64)
    revision: str = Field(pattern=r'^[a-f0-9]{64}$')


class SkillPlan(SkillIdentity):
    inputs: dict
    mission_id: str = Field(min_length=1, max_length=64)
    grant_id: str = Field(min_length=1, max_length=64)


class SkillExecution(Params):
    plan_id: str = Field(min_length=1, max_length=64)


class SkillExecute(SkillExecution):
    revision: str = Field(pattern=r'^[a-f0-9]{64}$')
    mission_id: str = Field(min_length=1, max_length=64)
    grant_id: str = Field(min_length=1, max_length=64)


class Application:
    """协议与持久化之间的窄接口；不接受 SQL、工具或任意执行请求。"""

    def __init__(self, event_sink=None):
        self.session = Session()
        self.store: Store | None = None
        self.registry = ModelRegistry()
        self.browser = BrowserService()
        # 网关只存在于当前后端连接，连接断开即丢失授权和调用预算。
        self.computer = ComputerGateway()
        self.graph: MissionGraph | None = None
        self.chat: ChatService | None = None
        self.auxiliary: AuxiliaryService | None = None
        self.skills: SkillsService | None = None
        self.embedding: LocalEmbedder | None = None
        self.retrieval: RetrievalService | None = None
        # 仅由私有stdio服务注入；事件出口不能由renderer、模型或业务参数覆写。
        self.event_sink = event_sink

    async def handle(self, line: bytes) -> dict:
        try:
            request = json.loads(line.decode("utf-8"))
        except (ValueError, RecursionError):
            return self.session.handle(line)
        methods = {"initialize", "credentials.replace", "configuration.status", "missions.create", "missions.list", "missions.get",
                   "computer.grant", "computer.revoke", "computer.status", "computer.execute",
                   "computer.plan", "computer.approve", "computer.execute_action", "computer.resume",
                   "computer.verify", "computer.undo_latest", "mission.run", "mission.approve"}
        methods |= {"browser.read", "browser.search"}
        methods |= {"auxiliary.status", "auxiliary.configure", "auxiliary.probe"}
        methods |= {"retrieval.model", "retrieval.status", "retrieval.prepare", "retrieval.activate", "retrieval.download", "retrieval.rebuild", "retrieval.search", "retrieval.clear"}
        methods |= {"memory.list", "memory.context", "memory.preview", "memory.generate", "memory.search", "memory.correct", "memory.forget"}
        methods |= {'skills.list', 'skills.enable', 'skills.preview_import', 'skills.register', 'skills.plan', 'skills.execute', 'skills.execution', 'skills.history', 'skills.cancel'}
        methods |= {"chat.document.attach", "chat.document.source", "chat.document.ask", "chat.document.preview", "chat.document.export"}
        methods |= {"chat.synthesis.preview", "chat.synthesis.generate"}
        methods |= {"chat.natural", "chat.continue", "chat.fallback.confirm", "chat.material.remove", "chat.revoke", "chat.scan.page"}
        methods |= {"chat.publication.preview", "chat.publication.save"}
        methods |= {"chat.development.context", "chat.development.generate", "chat.development.draft", "chat.development.apply"}
        methods |= {"chat.cleanup.scan", "chat.cleanup.plan", "chat.cleanup.execute", "chat.cleanup.restore"}
        from .automation.contracts import CONTRACTS as AUTOMATION_CONTRACTS
        methods |= {"chat.automation." + suffix for suffix in AUTOMATION_CONTRACTS}
        methods |= {"chat.rename", "chat.pin", "chat.delete", "chat.delete_check", "chat.create", "chat.list", "chat.get", "chat.send", "chat.grant", "chat.inspect",
                    "chat.browser.search", "chat.browser.read", "chat.browser.ask", "chat.browser.source",
                    "chat.approve", "chat.resume", "chat.undo", "chat.cancel"}
        methods |= {"context.index", "context.search", "context.clear", "context.preferences.set", "context.preferences.get",
                    "context.summary.update", "context.summary.get"}
        if not isinstance(request, dict) or not isinstance(request.get("method"), str) or request["method"] not in methods:
            return self.session.handle(line)
        request_id = request.get("id")
        if not isinstance(request_id, str) or not request_id.strip():
            return error_response(None, "INVALID_REQUEST", "请求 ID 必须是非空字符串")
        if type(request.get("v")) is not int or request["v"] != 1:
            return error_response(request_id, "UNSUPPORTED_VERSION", "仅支持协议版本 1")
        if set(request) != {"v", "id", "method", "params"} or not isinstance(request["params"], dict):
            return error_response(request_id, "INVALID_REQUEST", "请求格式无效")
        if not self.session.ready:
            return error_response(request_id, "NOT_READY", "请先完成 hello 握手")
        method, params = request["method"], request["params"]
        try:
            if method == "initialize":
                if self.store is not None:
                    return error_response(request_id, "ALREADY_INITIALIZED", "不能在连接内替换数据目录")
                initial = Initialize.model_validate(params)
                directory = Path(initial.data_directory)
                if not directory.is_absolute():
                    return error_response(request_id, "INVALID_PARAMS", "数据目录必须是主进程提供的绝对路径")
                store = Store(directory / "app.sqlite")
                try:
                    await store.open()
                except (OSError, sqlite3.Error, ValueError, RuntimeError):
                    await store.close()
                    return error_response(request_id, "STORAGE_UNAVAILABLE", "无法打开当前版本的应用数据库")
                graph = MissionGraph(store, directory / "checkpoints.sqlite")
                auxiliary = AuxiliaryService(store)
                try:
                    await store.recover_operations()
                    await graph.__aenter__()
                    chat = ChatService(store, self.computer, graph, self.registry, self.browser)
                    if self.event_sink is not None:
                        chat.set_event_sink(self.event_sink)
                    await chat.open()
                    # 辅助连接故障内部降级；SQLite迁移失败仍按存储故障处理并完整释放。
                    await auxiliary.open()
                    skills = SkillsService(store)
                    await skills.open()
                    embedding = LocalEmbedder(directory)
                    retrieval = RetrievalService(store, embedding)
                    await retrieval.open()
                    chat.retrieval = ScopedRetrieval(chat, retrieval)
                    chat.memory = MemoryService(chat)
                    await chat.memory.open()
                    await auxiliary.replace_password(initial.credentials.redis.get_secret_value() if initial.credentials.redis else None)
                except (OSError, sqlite3.Error, ValueError, RuntimeError):
                    # 初始化完整成功前不发布半就绪对象；失败后允许重新连接。
                    await auxiliary.close()
                    await graph.__aexit__(None, None, None)
                    await store.close()
                    raise
                self.store, self.graph, self.chat = store, graph, chat
                self.registry.replace_credentials(initial.credentials)
                self.browser.key = initial.credentials.tavily
                # SQLite 初始化后建立只读事实通知；辅助连接失败不能改变业务就绪状态。
                self.auxiliary = auxiliary
                self.skills = skills
                self.embedding, self.retrieval = embedding, retrieval
                result = {"initialized": True}
            elif self.store is None:
                return error_response(request_id, "NOT_INITIALIZED", "应用数据尚未初始化")
            elif method == "retrieval.model":
                Params.model_validate(params)
                result = embedding_manifest()
            elif method in {"memory.list", "memory.preview"}:
                cid = RetrievalConversation.model_validate(params).id
                result = await getattr(self.chat.memory, method.split(".")[1])(cid)
            elif method == "memory.context":
                request = MemoryContext.model_validate(params)
                result = await self.chat.memory.context(request.id, request.query)
            elif method == "memory.search":
                request = MemorySearch.model_validate(params)
                result = await self.chat.memory.search(request.query)
            elif method == "memory.generate":
                request = MemoryGenerate.model_validate(params)
                result = await self.chat.memory.generate(request.id, request.revision)
            elif method == "memory.correct":
                request = MemoryCorrect.model_validate(params)
                result = await self.chat.memory.correct(request.id, request.memory_id, request.value)
            elif method == "memory.forget":
                request = MemoryRecord.model_validate(params)
                result = await self.chat.memory.forget(request.id, request.memory_id)
            elif method == "retrieval.status":
                Params.model_validate(params)
                result = self.embedding.status()
            elif method == "retrieval.prepare":
                result = await self.embedding.prepare(ModelPath.model_validate(params).path)
            elif method == "retrieval.activate":
                Params.model_validate(params)
                result = await self.embedding.restore()
            elif method == "retrieval.download":
                Params.model_validate(params)
                result = await self.embedding.download()
            elif method in {"retrieval.rebuild", "retrieval.clear"}:
                cid = RetrievalConversation.model_validate(params).id
                if method == "retrieval.rebuild":
                    result = await self.chat.retrieval.rebuild(cid)
                else:
                    await self.chat.repository.get(cid)
                    result = await self.retrieval.clear(cid)
            elif method == "retrieval.search":
                query = RetrievalQuery.model_validate(params)
                result = await self.chat.retrieval.search(query.id, query.query)
            elif method == 'skills.list':
                result = await self.skills.list(SkillList.model_validate(params).offset)
            elif method == 'skills.history':
                Params.model_validate(params)
                result = await self.skills.history()
            elif method == 'skills.enable':
                request = SkillEnable.model_validate(params)
                result = await self.skills.set_enabled(request.skill_id, request.enabled)
            elif method == 'skills.preview_import':
                result = await self.skills.preview_import(SkillImport.model_validate(params).path)
            elif method == 'skills.register':
                request = SkillRegister.model_validate(params)
                result = await self.skills.register(request.review_id, request.revision)
            elif method == 'skills.plan':
                request = SkillPlan.model_validate(params)
                if await self.store.get_mission(request.mission_id) is None:
                    return error_response(request_id, 'NOT_FOUND', '任务不存在')
                self.computer.check_scan('computer', request.mission_id, request.grant_id)
                result = await self.skills.plan(request.skill_id, request.inputs, request.mission_id, request.grant_id)
            elif method in {'skills.execute', 'skills.cancel'}:
                request = SkillExecute.model_validate(params)
                # 固定角色与授权只由可信调度闭包注入；Skill 包不能提供模型/权限字段。
                async def dispatch(tool, arguments):
                    return await asyncio.to_thread(self.computer.execute, 'computer', ToolRequest.model_validate({
                        'mission_id': request.mission_id, 'grant_id': request.grant_id,
                        'call': {'tool': tool, 'arguments': arguments}}))
                if method == 'skills.cancel':
                    result = await self.skills.cancel(request.plan_id, request.revision, request.mission_id, request.grant_id)
                else:
                    result = await self.skills.execute(request.plan_id, request.revision, request.mission_id, request.grant_id, dispatch)
            elif method == 'skills.execution':
                result = await self.skills.get_execution(SkillExecution.model_validate(params).plan_id)
            elif method == "auxiliary.status":
                Params.model_validate(params)
                result = await self.auxiliary.status()
            elif method == "auxiliary.probe":
                Params.model_validate(params)
                result = await self.auxiliary.probe()
            elif method == "auxiliary.configure":
                config = AuxiliaryConfig.model_validate(params)
                result = await self.auxiliary.configure(config.model_dump())
            elif method.startswith("chat."):
                result = await self.chat.handle(method, params)
                if method in {"chat.send", "chat.natural", "chat.continue", "chat.fallback.confirm", "chat.document.attach", "chat.synthesis.generate", "chat.material.remove"}:
                    # 只建立本地候选；外发整理仍走独立准确预览及主进程原生批准。
                    await self.chat.memory.synchronize(params["id"])
            elif method == "credentials.replace":
                updated = ReplaceCredentials.model_validate(params)
                self.registry.replace_credentials(updated.credentials)
                self.browser.key = updated.credentials.tavily
                await self.auxiliary.replace_password(updated.credentials.redis.get_secret_value() if updated.credentials.redis else None)
                result = {"updated": True}
            elif method in {"browser.read", "browser.search"}:
                # 仅可信主进程可提交显式 URL/查询；网页内容不能扩大访问范围或索引自身。
                request = ReadRequest.model_validate(params) if method == "browser.read" else SearchRequest.model_validate(params)
                if await self.store.get_mission(request.mission_id) is None:
                    return error_response(request_id, "NOT_FOUND", "任务不存在")
                result = (await self.browser.read(request.url, mode=request.mode) if method == "browser.read"
                          else await self.browser.web_search(request.query, max_results=request.max_results))
            elif method == "computer.grant":
                result = self.computer.grant(GrantRequest.model_validate(params))
            elif method == "computer.revoke":
                result = self.computer.revoke(str(MissionRequest.model_validate(params).mission_id))
            elif method == "computer.status":
                result = self.computer.status(str(MissionRequest.model_validate(params).mission_id))
            elif method == "computer.execute":
                # stdio 只由 Electron 主进程连接；网关仍再次固定 Computer 角色。
                result = self.computer.execute("computer", ToolRequest.model_validate(params))
            elif method == "computer.plan":
                result = await ActionService(self.store).create_plan(ActionPlanRequest.model_validate(params))
            elif method == "computer.approve":
                result = await ActionService(self.store).approve(OperationId.model_validate(params).operation_id)
            elif method == "computer.execute_action":
                result = await ActionService(self.store).execute(OperationId.model_validate(params).operation_id)
            elif method == "computer.resume":
                result = await ActionService(self.store).resume(OperationId.model_validate(params).operation_id)
            elif method == "computer.verify":
                result = await ActionService(self.store).verify(OperationId.model_validate(params).operation_id)
            elif method == "computer.undo_latest":
                result = await ActionService(self.store).undo_latest(str(MissionRequest.model_validate(params).mission_id))
            elif method == "mission.run":
                if self.graph is None:
                    raise RuntimeError("编排图尚未初始化")
                request = GraphStart.model_validate(params)
                result = await self.graph.start({"mission_id": request.mission_id, "goal": request.goal,
                                                 "root": request.root, "actions": [item.model_dump() for item in request.actions]}, request.thread_id)
            elif method == "mission.approve":
                if self.graph is None:
                    raise RuntimeError("编排图尚未初始化")
                result = await self.graph.approve_and_resume(GraphThread.model_validate(params).thread_id)
            elif method == "context.index":
                request = ContextIndex.model_validate(params)
                result = await ContextService(self.store).index_text(request.mission_id, request.source, request.text)
            elif method == "context.search":
                request = ContextSearch.model_validate(params)
                result = await ContextService(self.store).search(request.mission_id, request.query, request.limit)
            elif method == "context.clear":
                request = ContextClear.model_validate(params)
                result = await ContextService(self.store).clear(request.mission_id, request.source)
            elif method == "context.preferences.set":
                request = ContextPreference.model_validate(params)
                result = await ContextService(self.store).set_preference(request.mission_id, request.key, request.value)
            elif method == "context.preferences.get":
                request = ContextMission.model_validate(params)
                result = await ContextService(self.store).preferences(request.mission_id)
            elif method == "context.summary.update":
                request = ContextSummary.model_validate(params)
                result = await ContextService(self.store).update_summary(request.mission_id, request.summary, request.revision)
            elif method == "context.summary.get":
                request = ContextMission.model_validate(params)
                result = await ContextService(self.store).summary(request.mission_id)
            elif method == "configuration.status":
                Params.model_validate(params)
                result = self.registry.status()
            elif method == "missions.create":
                mission = await self.store.create_mission(MissionCreate.model_validate(params))
                result = mission.model_dump(mode="json")
            elif method == "missions.list":
                Params.model_validate(params)
                result = {"missions": [mission.model_dump(mode="json") for mission in await self.store.list_missions()]}
            else:
                mission = await self.store.get_mission(MissionId.model_validate(params).id)
                if mission is None:
                    return error_response(request_id, "NOT_FOUND", "草稿不存在")
                result = mission.model_dump(mode="json")
        except ValidationError:
            # ValidationError 可带原始输入，绝不序列化异常详情或写日志。
            return error_response(request_id, "INVALID_PARAMS", "参数或持久化契约无效")
        except (ToolError, SystemToolError, SkillError, RetrievalError, MemoryError) as error:
            return error_response(request_id, error.code, error.message)
        except ContextError as error:
            return error_response(request_id, error.code, error.message)
        except ValueError:
            return error_response(request_id, "CONFLICT", "请求与已有草稿冲突或配置快照无效")
        except sqlite3.Error as error:
            code = getattr(error, "sqlite_errorcode", None)
            if code is not None:
                code &= 0xff
            if code in {sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED}:
                return error_response(request_id, "STORAGE_BUSY", "应用数据库正在使用，请稍后重试")
            if code == sqlite3.SQLITE_FULL:
                return error_response(request_id, "STORAGE_FULL", "应用数据磁盘空间不足，请释放空间后重试")
            return error_response(request_id, "STORAGE_UNAVAILABLE", "应用数据库暂不可用")
        except OSError as error:
            if error.errno == errno.ENOSPC:
                return error_response(request_id, "STORAGE_FULL", "磁盘空间不足，请释放空间后重试")
            if error.errno in {errno.EACCES, errno.EPERM}:
                return error_response(request_id, "PERMISSION_DENIED", "当前操作的访问权限不足")
            return error_response(request_id, "STORAGE_UNAVAILABLE", "应用存储暂不可用")
        return {"v": 1, "id": request_id, "ok": True, "result": result}

    async def close(self) -> None:
        if self.embedding is not None:
            await self.embedding.close()
            self.embedding = None
        if self.auxiliary is not None:
            # 后台观察器先停止，不能在共享库关闭后继续查询或写缓存。
            await self.auxiliary.close()
            self.auxiliary = None
        if self.chat is not None:
            # 先终止自有隔离/自动化工作进程并记账，再关闭共享数据库。
            await self.chat.automation.close()
        if self.graph is not None:
            await self.graph.__aexit__(None, None, None)
            self.graph = None
        if self.store is not None:
            await self.store.close()
