# 上下文、偏好与轻量 RAG（M06）

M13接入使用`document:<不可变证据ID>:<页/段号>`作为source，只索引显式选择附件的有界正文；引用回查仍匹配Mission，OCR分数/缺失等保留在文档证据。M12网页继续使用browser前缀。两类查询均为本地关键词检索，不做生成式总结；未新增全盘扫描或自动上传。

## 用途与结构

`service.py` 提供任务范围内的文本分块、jieba 中文分词、SQLite FTS5 检索、用户显式偏好、滚动摘要和索引清理。调用方必须主动提交文本和来源，模块不会扫描目录或读取用户文件。

## 输入输出与公共接口

- `chunk_text(text, max_chars, overlap)`：返回有界文本块。
- `ContextService.index_text(mission_id, source, text)`：按来源原子替换索引，记录 SHA-256 内容摘要。
- `search(mission_id, query, limit)`：只检索指定 Mission，返回原文块、来源、块序号和 FTS 分数。
- `set_preference/preferences`：保存和读取任务范围显式偏好。
- `update_summary/summary`：保存带 revision 的滚动摘要。
- `clear(mission_id, source?)`：清理任务全部或指定来源索引，不删除原文件。

Application 暴露 `context.index/search/clear/context.preferences.* / context.summary.*` 私有协议方法。返回的 evidence 可供 Main Agent 引用，不把分词后的 FTS 内容展示给用户。

## 依赖、运行与测试

Python 3.12、jieba 0.42、SQLite FTS5、aiosqlite。版本由 `backend/uv.lock` 固定。

```powershell
.\backend\.venv\Scripts\python.exe -m pytest backend/tests/test_context.py backend/tests/test_application_context.py
```

测试只使用临时 SQLite 和合成文本，不调用模型、网络或真实用户文件。

## 权限边界与已知限制

Mission ID 是隔离边界；查询拒绝 FTS 控制字符和超长输入，来源仅作为引用标签保存。索引是任务范围临时知识，不是全盘索引；清理只清理数据库索引。jieba 默认词典启动会产生本地缓存日志，缓存不进入仓库。摘要由调用方提供，M06 不自动调用模型生成摘要。


## V4-011 本机只读检索重试

Application将私有RetryService绑定Store，`ContextService.search`完成输入校验和分词后仅将`Store.search_context`纯FTS SELECT包入适配器。只对SQLite错误码BUSY/LOCKED最多三次，额外等待0.2/0.5秒与执行共享总3秒deadline。索引写入、清理、向量推理/失效写入、偏好/摘要更新不重试；外部数据库锁若连尝试账本也不能安全保存则拒绝执行，不能绕过SQLite事实链。没有结果不伪造原文；原文版本和有效关联由上层证据接口复核。独立模块没有RetryService时保留原纯检索接口。命令/真实SQLite与明确故障注入边界见PROGRESS。
