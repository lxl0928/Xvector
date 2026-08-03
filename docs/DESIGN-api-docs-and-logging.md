# Xvector API 文档合并与请求追踪 / 访问日志 设计说明书

> 版本：v1.0（待确认后实现）  
> 范围：Gateway 统一 OpenAPI/Swagger、跨 Gateway→Writer/Reader 的 `trace_id` / `requestId`、三角色 Start/End 访问日志  
> 前置：仓库已有 `docs/DESIGN.md`（整体架构）；本文件仅覆盖 TODO「xvector api文档 及 日志优化」  
> **本阶段不写业务实现代码**；用户回复 **keep** 后，才按本说明书 coding。

---

## 1. 背景与目标

### 1.1 背景

当前部署为 Docker Compose 三服务：

| 角色 | 端口 | 职责 |
|------|------|------|
| Gateway | **19530**（对外） | Bearer 鉴权、按 `router_table` 转发 Writer/Reader |
| Writer | 18081（内网） | 写 / DDL / Import / User / Role 等 |
| Reader | 18082（内网） | 读 / Search / Query / Describe 等 |

用户访问 `http://{host}:19530/docs` 时期望看到**完整**对外 API（探活、认证、Writer+Reader 业务接口），并能用统一 `requestId`/`X-Request-Id` 串联三容器日志。

### 1.2 目标

1. 全链路 `trace_id`：Gateway 解析或生成 → 向下传递 → Writer/Reader/Gateway 日志与响应头一致。
2. Gateway 对外 JSON 响应注入 `requestId`；Writer/Reader **不改 body**，只打 Start/End 日志并写响应头。
3. 访问日志：UTC ISO8601 时间前缀 + Start 行 + End 行（含同一 `trace_id`）。
4. Gateway `:19530/docs` 合并 Writer/Reader OpenAPI；扁平 tag 模拟二级分类；启用 Swagger Authorize；暴露内部管理刷新接口。
5. Writer/Reader 默认关闭 `/docs`、`/redoc`，保留 `/openapi.json` 供 Gateway 内网拉取。

### 1.3 非目标（见 §7）

不改变业务语义、不强制 Privilege 拦截、不引入独立 APM/OpenTelemetry SDK（仅 header 级 trace）。

---

## 2. 已确认决策摘要

| # | 主题 | 已确认决策 |
|---|------|------------|
| 1 | `trace_id` 来源 | 优先复用客户端传入；若无则生成；头优先级：`X-Request-Id` > `X-Trace-Id` > `traceparent`（取 trace-id 段） |
| 2 | 向下传递与响应统一 | 请求/响应头统一使用 `X-Request-Id`；响应 JSON 字段名 `requestId` |
| 3 | `requestId` 注入 | 所有成功/失败 JSON 响应都注入；同时始终写响应头 `X-Request-Id`；非 JSON 仅写响应头 |
| 4 | 职责分层 | **仅 Gateway** 对外响应注入 body.`requestId`；Writer/Reader 只打带 trace 的 Start/End 日志并写响应头，**不改 body** |
| 5 | 日志形态 | UTC ISO8601 时间前缀；Start + End；形如：`2026-08-02T09:40:01.123Z 127.0.0.1:52486 {trace_id} "GET /healthz HTTP/1.1" Start...`；End 保持现有 status 风格并带同一 `trace_id` 与时间 |
| 6 | 文档 | Gateway `:19530/docs` 合并 writer/reader OpenAPI；扁平 tag：`Writer / Collection`、`Reader / Vector`、`Gateway / System`、`Gateway / Admin` 等；资源参考 Alias/Collection/Import/Index/Partition/Role/User/Vector；healthz/auth 归 System；暴露内部管理接口 |
| 7 | Swagger | 启用 Authorize（Bearer/现有 token）；`info.description` 含 Base URL、认证、`X-Request-Id`/`requestId`、curl 示例（含 trace 头）；认证接口在 `Gateway / System` |
| 8 | OpenAPI 合并 | 启动时合并 + 定时刷新；失败保留上次成功结果；失败重试 + 手动 `POST /openapi/refresh`（无额外鉴权，tag `Gateway / Admin`） |
| 9 | 生成 id 格式 | `xv-` + 32 位 hex UUID（无连字符） |
| 10 | 隐藏与 UI | 隐藏 Gateway catch-all/proxy 路由；writer/reader 默认关闭 `/docs`、`/redoc`，保留 `/openapi.json` |

---

## 3. 现状分析（基于代码）

### 3.1 入口与配置

- `xvector/__main__.py`：按 `XVECTOR_ROLE` 加载 `gateway_app` / `writer_app` / `reader_app`，`uvicorn.run(..., factory=True)`，**未**自定义 `log_config` / access log formatter。
- `xvector/config.py`：已有 `writer_url` / `reader_url` / `internal_token` / `log_level` 等；**尚无** OpenAPI 刷新、docs 开关、trace 相关配置项。
- `docker-compose.yaml`：Gateway 暴露 `19530`；Writer/Reader 仅内网；环境变量与现有 Settings 对齐。

### 3.2 鉴权

- 对外：`Authorization: Bearer ${USERNAME}:${PASSWORD}`（`parse_bearer`：`split(":", 1)`）。
- Gateway：`gateway_app.proxy_all` 内联鉴权；失败直接 `JSONResponse` 401（`code=1800`）。
- 引导管理员：`bootstrap_matches`；否则 `POST {writer}/internal/auth/verify` + `X-Internal-Token`。
- Writer/Reader：**不强制 Bearer**（内网信任）；`auth_middleware` 已实现但 Gateway **未挂载**（当前走路由内鉴权）。
- **无**独立「认证校验」对外文档接口；Swagger Authorize 尚不可用（无 `securitySchemes`）。

### 3.3 代理与 Header

`xvector/gateway/proxy.py` 现状：

1. 转发时剥离 `host` / `content-length` / `authorization`。
2. 附加 `X-User`、`X-Internal-Token`（若配置）。
3. **已有** `X-Request-Id`：`request.headers.get("X-Request-Id") or str(uuid.uuid4())` —— 仅认一个头、生成格式为标准 UUID（含连字符），**不符合**本决策的优先级与 `xv-`+32hex。
4. 上游响应封装为 `Response(content=..., status_code=..., media_type=...)`，**未回传**上游响应头，也未保证对外响应头带 `X-Request-Id`。
5. Gateway 本地错误 JSON（401/404/500）**未**注入 `requestId`。

### 3.4 访问日志

- `xvector/logging.py`：`logging.basicConfig`，格式 `%(asctime)s [%(levelname)s] %(name)s: %(message)s`（本地时区 asctime，非强制 UTC ISO8601）。
- **无**自定义 Start/End 访问日志中间件；容器中可见的 `127.0.0.1:xxxxx "GET ..." 200 OK` 来自 **uvicorn 默认 access log**，且**无** `trace_id`、**无** Start 行。
- `app_factory.create_base_app` 仅有兜底异常中间件，不参与 access log / requestId。

### 3.5 OpenAPI / Docs

- `create_base_app(title)` → `FastAPI(title=title)`：三角色均默认开启 `/docs`、`/redoc`、`/openapi.json`。
- 业务路由在 `api/v2/routes.py`：`build_writer_router` / `build_reader_router`，**无** `tags`、`include_in_schema`、Pydantic 响应模型包装。
- Gateway catch-all：`/v2/vectordb/{full_path:path}` 会出现在 Gateway 自身 OpenAPI 中，干扰文档。
- **无**合并 Writer/Reader schema 的逻辑。

### 3.6 路由与资源（用于 tag 推断）

`router_table.ROUTE_TABLE` 路径后缀（`/v2/vectordb` 之后）与 W/R 目标已完备，例如：

- `/aliases/*`、`/collections/*`、`/partitions/*`、`/indexes/*`
- `/jobs/import/*` 与 `/import/*`
- `/roles/*`、`/users/*`、`/entities/*`
- `/databases/*`（代码已实现；TODO 资源列表未单列，本设计单独映射为 **Database**）

Gateway 本地：`/healthz`、`/readyz`、`/v2/vectordb/heartbeat`。

Writer 额外：`/internal/auth/verify`、`/v2/vectordb/heartbeat`。  
Reader 额外：`/internal/open|close|unfence|reload`。

### 3.7 响应体外壳

业务成功：`{"code": 0, "message": "success", "data": ...}`（`common/errors.ok`）。  
错误：多为 `{"code": ..., "message": ...}`；500 另有 `error_message`。  
**均无** `requestId` 字段。

---

## 4. 详细设计

### 4.1 Trace 中间件（三角色共用能力）

建议新增模块（命名建议）：`xvector/common/trace.py` + `xvector/api/middleware/access_log.py`（或合并为 `xvector/api/middleware/trace.py`）。

#### 4.1.1 解析 `trace_id`

按优先级读取请求头（大小写不敏感）：

1. `X-Request-Id`：非空则原样采用（trim 后）。
2. `X-Trace-Id`：非空则采用。
3. `traceparent`（W3C）：格式 `version-traceid-parentid-flags`；取第 2 段（32 hex）；若解析失败则忽略。
4. 皆无或无效：生成 `xv-` + `uuid.uuid4().hex`（32 位 hex，无连字符）。

**建议默认**：客户端传入的值若非空则**信任并原样传递**（不做强制 `xv-` 前缀校验），以便对接外部网关；仅服务端生成时使用 `xv-` 格式。

将结果挂到 `request.state.trace_id`（或 `request.state.request_id`，实现时二选一，全文一致）。

#### 4.1.2 响应头

各角色中间件在返回前：**始终**设置 `response.headers["X-Request-Id"] = trace_id`。

#### 4.1.3 Gateway 向下传递

`GatewayProxy.forward`：

- 使用中间件已解析的 `trace_id`（勿再单独 `uuid4`）。
- 强制设置下游请求头 `X-Request-Id: {trace_id}`（覆盖下游不应依赖客户端杂散头）。
- 可选：若客户端带来 `X-Trace-Id` / `traceparent`，可透传，但**规范头**以 `X-Request-Id` 为准。
- 对外返回时：在现有 `Response(...)` 上写入 `X-Request-Id`；若上游为 JSON，由 Gateway 注入中间件统一补 `requestId`（见 §4.3），不必依赖上游 body。

认证失败、未知路由、上游超时等**未进入 forward** 的路径，同样经过同一中间件，保证头与（JSON）body 一致。

#### 4.1.4 中间件挂载顺序（建议）

Starlette：后添加的 middleware 更靠外。建议：

1. 最外：`TraceAccessMiddleware`（解析 id → Start 日志 → `call_next` → 写响应头 / Gateway 注入 body → End 日志）。
2. 内层：现有异常兜底中间件保留。

这样即使内层返回 500 JSON，仍能注入 `requestId` 并打 End。

---

### 4.2 访问日志格式

#### 4.2.1 形态

**Start（请求进入）：**

```text
2026-08-02T09:40:01.123Z 127.0.0.1:52486 xv-0123456789abcdef0123456789abcdef "GET /healthz HTTP/1.1" Start...
```

**End（请求结束，保持 uvicorn 风格 status 短语）：**

```text
2026-08-02T09:40:01.145Z 127.0.0.1:52486 xv-0123456789abcdef0123456789abcdef "GET /healthz HTTP/1.1" 200 OK
```

字段约定：

| 字段 | 说明 |
|------|------|
| 时间 | UTC，`YYYY-MM-DDTHH:MM:SS.mmmZ`（毫秒 3 位） |
| 客户端 | `{host}:{port}`；无 port 时仅 host；缺失时用 `-` |
| trace | 与 `X-Request-Id` / `requestId` 同一字符串 |
| 请求行 | `"{METHOD} {path}{?query} HTTP/{version}"`（path 建议含原始 path；query 过长时**建议默认**保留完整，后续可加截断配置） |
| Start 后缀 | 固定 `Start...` |
| End 后缀 | `{status_code} {reason_phrase}`，如 `200 OK`、`401 Unauthorized`、`500 Internal Server Error` |

#### 4.2.2 实现策略（建议默认）

1. **关闭或抑制 uvicorn 默认 access log**，避免与自定义 End 行重复（`uvicorn.run(..., access_log=False)`，或自定义 `log_config` 去掉 `uvicorn.access` handler）。
2. 用中间件打印 Start/End 到 **stdout**（`logging.getLogger("xvector.access")` 或直接 print；**建议默认**用 logger，level=INFO，message 为整行已格式化字符串，formatter 对 access logger 使用 `%(message)s` 以免双重时间戳）。
3. 三角色（Gateway/Writer/Reader）同一套格式，便于 docker logs 对齐检索。

#### 4.2.3 与应用日志关系

- 业务 `logger.info/exception` 保持现有 `[LEVEL] name: message`；**建议默认**将其 asctime 也改为 UTC ISO8601（`logging.py` 自定义 Formatter），与访问日志时间风格统一。
- 禁止在访问日志中打印 `Authorization` / 密码 / body。

---

### 4.3 Gateway `requestId` 注入

#### 4.3.1 规则

仅 **Gateway** 角色：

| 响应类型 | body.`requestId` | 响应头 `X-Request-Id` |
|----------|------------------|------------------------|
| `Content-Type` 含 `application/json` 且 body 为 JSON **object** | 注入/覆盖为当前 `trace_id` | 始终写入 |
| JSON **array** / 非 object | **不改 body**（无法安全挂字段） | 始终写入 |
| 非 JSON（少见） | 不改 body | 始终写入 |
| 空 body | 不造 body | 始终写入 |

成功与失败（401/404/422/500 等）凡 JSON object 均注入。

#### 4.3.2 实现要点

- 在中间件拿到 `Response` 后：若需改 body，读取 `body` → `json.loads` → 若 `isinstance(dict)` 则 `body["requestId"] = trace_id` → 重新序列化，并更新 `Content-Length`（若存在）。
- 使用 ORJSON/标准 JSON 时注意与 `default_response_class` 一致；失败解析则跳过 body 注入，仍写响应头。
- **Writer/Reader**：中间件只写响应头 + Start/End，**禁止**修改 JSON body（上游 body 原样经 Gateway 时由 Gateway 再注入，避免双重职责；Writer 直连调试时客户端看不到 `requestId` 属预期）。

#### 4.3.3 代理路径

`forward` 返回的上游 JSON 同样经 Gateway 中间件注入，保证客户端始终看到 `requestId`，即使 Writer 未改 body。

---

### 4.4 OpenAPI 合并与 Tag 映射

#### 4.4.1 Writer/Reader App 文档开关

| 项 | Writer/Reader **建议默认** | Gateway |
|----|---------------------------|---------|
| `docs_url` | `None`（关闭 UI） | `"/docs"` |
| `redoc_url` | `None` | `None`（**建议默认**只保留 Swagger UI；可配置开启） |
| `openapi_url` | `"/openapi.json"` | 自定义合并 schema（见下） |

配置项见 §4.6。

#### 4.4.2 合并流程（Gateway）

建议模块：`xvector/gateway/openapi_merge.py`。

1. **启动时**：异步拉取  
   - `{XVECTOR_WRITER_URL}/openapi.json`  
   - `{XVECTOR_READER_URL}/openapi.json`  
2. 与 Gateway 本地 paths（healthz/readyz/heartbeat/auth/openapi.refresh 等）合并。
3. 对合并结果做 **tag 重写**、**隐藏** catch-all、挂 `securitySchemes`、写 `info.description`。
4. 缓存到内存（`app.state.merged_openapi`）；`GET /openapi.json` 与 `/docs` 使用该缓存。
5. **定时刷新**：后台 task，间隔见配置（**建议默认 60s**）。
6. **失败策略**：保留上次成功缓存；单次刷新内 **建议默认重试 3 次**，间隔 **建议默认 1s**（可配置）；三次仍失败则打 warning，不覆盖缓存。
7. **手动刷新**：`POST /openapi/refresh`（见 §4.5），无 Bearer / 无 Internal-Token 要求。

首次启动若 Writer/Reader 尚未 ready：允许空缓存或仅 Gateway 本地 paths；ready 后定时/手动刷新补齐。`/docs` 在仅有本地 paths 时仍可打开。

#### 4.4.3 隐藏路由

Gateway OpenAPI **排除**：

- `proxy_all`：`/v2/vectordb/{full_path:path}`（`include_in_schema=False`）。
- 不把 Writer/Reader 的 `/internal/*` 默认合并进对外文档（**建议默认隐藏**）；若未来需要运维可见，可用配置 `XVECTOR_OPENAPI_INCLUDE_INTERNAL=true` 打开，tag 为 `Writer / Internal` / `Reader / Internal`。

**建议默认**：对外 docs **不**展示 `/internal/*`。

#### 4.4.4 Tag 映射规则

扁平字符串 tag，用 ` / ` 模拟二级：`{Role} / {Resource}`。

**Role 推断**

| 来源 schema | Role 前缀 |
|-------------|-----------|
| Writer `/openapi.json` 中的 path | `Writer` |
| Reader `/openapi.json` 中的 path | `Reader` |
| Gateway 本地注册 path | `Gateway` |

同一 path 不应同时出现在 Writer 与 Reader（当前路由表互斥）；若冲突，**建议默认** Writer 优先并打 warning。

**Resource 推断（path → 资源名）**

对 path 去掉前缀 `/v2/vectordb` 后，按**第一段**映射：

| path 第一段（或前缀） | Resource 显示名 | 备注 |
|----------------------|-----------------|------|
| `aliases` | `Alias` | |
| `collections` | `Collection` | |
| `jobs` + 第二段 `import`，或第一段 `import` | `Import` | 兼容 `/jobs/import/*` 与 `/import/*` |
| `indexes` | `Index` | |
| `partitions` | `Partition` | |
| `roles` | `Role` | |
| `users` | `User` | |
| `entities` | `Vector` | TODO 资源名 Vector；路径仍为 entities |
| `databases` | `Database` | 代码已有；补充进 tag（非 TODO 八大资源，但需文档可见） |
| 其他 `/v2/vectordb/...` | `Other` | 兜底；实现时 log debug |

**Gateway 本地特殊映射（覆盖第一段规则）**

| Path | Tag |
|------|-----|
| `GET /healthz` | `Gateway / System` |
| `GET /readyz` | `Gateway / System` |
| `GET /v2/vectordb/heartbeat` | `Gateway / System` |
| 认证接口（§4.5.1） | `Gateway / System` |
| `POST /openapi/refresh` | `Gateway / Admin` |
| `GET /openapi.json` | 可不展示在 paths（由 FastAPI 文档端点自身处理） |

最终 tag 示例：`Writer / Collection`、`Reader / Vector`、`Gateway / System`、`Gateway / Admin`。

合并后为每个 operation 设置 `tags: ["Writer / Collection"]`（单 tag **建议默认**），并生成顶层 `tags` 数组（按 Role 再按资源名字母序，Gateway System/Admin 置顶 **建议默认**）。

#### 4.4.5 业务路由 tags（源侧）

为降低合并时猜测成本，**建议**在 `build_writer_router` / `build_reader_router` 为各路由组设置临时 tags（如 `Collection`），合并器再改写为 `Writer / Collection`。若实现时选择纯 path 推断，也可不改 routes —— **建议默认：合并器 path 推断为主，routes 侧 tags 可选增强**。

---

### 4.5 Docs description、认证接口、Swagger Authorize

#### 4.5.1 认证接口（`Gateway / System`）

新增 Gateway 本地接口（不转发）：

- **方法/路径（建议默认）**：`POST /v2/vectordb/auth`
- **行为**：解析 `Authorization: Bearer USERNAME:PASSWORD`，走与 `proxy_all` 相同校验（bootstrap 或 writer verify）；成功返回  
  `{"code":0,"message":"success","data":{"username":"..."},"requestId":"..."}`；失败 401 + `requestId`。
- **用途**：Swagger 试用 Authorize 后可「Try it out」验证凭据；文档中说明业务 API 同样携带该 Bearer。
- **OpenAPI**：`security` 要求 Bearer；tag `Gateway / System`。

#### 4.5.2 securitySchemes

合并后的 OpenAPI：

```yaml
components:
  securitySchemes:
    BearerAuth:
      type: http
      scheme: bearer
      bearerFormat: "USERNAME:PASSWORD"
      description: "Authorization: Bearer ${USERNAME}:${PASSWORD}"
```

- 对 `/v2/vectordb/**` 业务与 auth：**建议默认** `security: [{BearerAuth: []}]`。
- `/healthz`、`/readyz`、`/openapi/refresh`：**无** security。
- Swagger UI `Authorize` 按钮写入 `Authorization` 头。

#### 4.5.3 `info` 字段

| 字段 | 建议默认 |
|------|----------|
| `title` | `Xvector API` |
| `version` | 与包版本或固定 `0.1.0` 对齐（实现时读 `xvector` 版本若有） |
| `description` | Markdown，必须包含下列小节 |

**description 必备内容：**

1. **Base URL**：`http://{host}:19530`（说明仅 Gateway 对外）。
2. **认证**：`Authorization: Bearer USERNAME:PASSWORD`；引导用户来自 env；指向 `POST /v2/vectordb/auth`。
3. **请求追踪**：客户端可传 `X-Request-Id` / `X-Trace-Id` / `traceparent`；服务端统一响应头 `X-Request-Id` 与 JSON `requestId`；生成格式 `xv-`+32hex。
4. **curl 示例**（含 trace 头），例如：

```bash
curl -sS -X POST 'http://127.0.0.1:19530/v2/vectordb/collections/list' \
  -H 'Authorization: Bearer root:Xvector' \
  -H 'Content-Type: application/json' \
  -H 'X-Request-Id: xv-client-demo-id-please-use-real-hex' \
  -d '{}'
```

（示例中说明：自定义 id 可原样回传；省略头时服务端生成 `xv-`+uuidhex。）

5. **读写分流简述**：写接口 → Writer；读接口 → Reader；文档 tag 已标注。
6. **OpenAPI 刷新**：`POST /openapi/refresh`（Admin）。

#### 4.5.4 隐藏 Gateway catch-all

对 `proxy_all` 设置 `include_in_schema=False`，避免 Swagger 出现无意义的 `{full_path}` 代理项。

---

### 4.6 配置项（建议默认值）

在 `Settings` / `.env.example` / `docker-compose.yaml`（按需）增加：

| 环境变量 | 建议默认 | 说明 |
|----------|----------|------|
| `XVECTOR_OPENAPI_REFRESH_SECONDS` | `60` | Gateway 定时合并间隔；`0` 表示禁用定时（仅启动+手动） |
| `XVECTOR_OPENAPI_REFRESH_RETRIES` | `3` | 单次刷新失败重试次数 |
| `XVECTOR_OPENAPI_REFRESH_RETRY_INTERVAL_SECONDS` | `1` | 重试间隔 |
| `XVECTOR_OPENAPI_FETCH_TIMEOUT_SECONDS` | `5` | 拉取 W/R openapi.json 超时 |
| `XVECTOR_DOCS_ENABLED` | Gateway:`true`；W/R 忽略（代码写死关 UI） | 是否挂载 `/docs`（仅 Gateway 生效） |
| `XVECTOR_REDOC_ENABLED` | `false` | Gateway 是否挂载 `/redoc` |
| `XVECTOR_WRITER_DOCS_UI` | `false` | Writer 是否开启 `/docs`（默认关） |
| `XVECTOR_READER_DOCS_UI` | `false` | Reader 是否开启 `/docs`（默认关） |
| `XVECTOR_OPENAPI_INCLUDE_INTERNAL` | `false` | 合并时是否纳入 `/internal/*` |
| `XVECTOR_ACCESS_LOG_ENABLED` | `true` | 自定义 Start/End 访问日志开关 |

现有项继续沿用：`XVECTOR_WRITER_URL`、`XVECTOR_READER_URL`、`XVECTOR_INTERNAL_TOKEN`、`XVECTOR_LOG_LEVEL`、`XVECTOR_USERNAME`、`XVECTOR_PASSWORD`。

---

### 4.7 刷新 / 重试 API

#### `POST /openapi/refresh`

| 项 | 约定 |
|----|------|
| 鉴权 | **无**额外鉴权（已确认） |
| Tag | `Gateway / Admin` |
| 行为 | 立即执行一次合并（含重试策略）；成功更新缓存；失败保留旧缓存 |
| 响应 JSON（建议默认） | `{"code":0,"message":"success","data":{"ok":true,"paths":N,"refreshedAt":"<UTC ISO8601>"},"requestId":"..."}`；若失败：`ok:false` + `error` 字段，HTTP **建议默认 200 + code!=0** 或 503 —— **建议默认 HTTP 503** 且 body 含 `requestId`，以便探活脚本区分 |

定时任务与手动刷新共用同一 `refresh_openapi()` 函数，加 `asyncio.Lock` 防止并发刷新踩踏。

---

### 4.8 调用链示意

```text
Client
  |  (可选) X-Request-Id / X-Trace-Id / traceparent
  |  Authorization: Bearer user:pass
  v
Gateway TraceMiddleware
  |  resolve/generate trace_id
  |  log Start
  |  auth (business paths)
  |  proxy: X-Request-Id + X-User + X-Internal-Token
  v
Writer/Reader TraceMiddleware
  |  读取 X-Request-Id（无则按同规则生成，直连调试场景）
  |  log Start → handler → 响应头 X-Request-Id → log End
  v
Gateway
  |  注入 JSON requestId + 响应头 X-Request-Id
  |  log End
  v
Client  (header X-Request-Id + body.requestId)
```

---

## 5. 涉及文件与改动点（清单）

> 实现阶段按此清单改动；**当前仅文档落盘，不改运行代码。**

| 文件 | 改动类型 | 说明 |
|------|----------|------|
| `docs/DESIGN-api-docs-and-logging.md` | 新增 | 本说明书 |
| `xvector/common/trace.py`（新） | 新增 | 解析/生成 `trace_id`；常量头名 |
| `xvector/api/middleware/trace_access.py`（新） | 新增 | Start/End 日志；响应头；Gateway body 注入 |
| `xvector/gateway/openapi_merge.py`（新） | 新增 | 拉取、合并、tag 映射、缓存、刷新 |
| `xvector/api/app_factory.py` | 修改 | `create_base_app` 支持 docs/redoc/openapi 开关；挂载 trace 中间件；按 role 区分是否注入 body |
| `xvector/api/gateway_app.py` | 修改 | auth 接口；`openapi/refresh`；自定义 openapi；catch-all `include_in_schema=False`；启动合并+定时任务 |
| `xvector/api/writer_app.py` | 修改 | 关闭 docs/redoc UI（可配置） |
| `xvector/api/reader_app.py` | 修改 | 同上 |
| `xvector/gateway/proxy.py` | 修改 | 使用统一 trace；保证向下 `X-Request-Id`；对外响应带头 |
| `xvector/auth/gateway_auth.py` | 小改/复用 | auth 接口复用 `parse_bearer` / `authenticate_via_writer` |
| `xvector/config.py` | 修改 | §4.6 配置项 |
| `xvector/logging.py` | 修改 | UTC ISO8601；access logger 格式 |
| `xvector/__main__.py` | 修改 | `access_log=False` 或自定义 log_config |
| `xvector/api/v2/routes.py` | 可选 | 为路由补充 tags（增强可读性） |
| `docker-compose.yaml` / `.env.example` | 修改 | 文档化新环境变量（值用建议默认） |
| `docs/DESIGN.md` | 可选 | 增加指向本说明书的交叉链接（非必须） |
| `tests/...` | 后续 | E2E：trace 头优先级、requestId 注入、docs/openapi 合并、refresh；**实现阶段再补** |

---

## 6. 边界与非目标

1. **不**引入 OpenTelemetry/Jaeger 等完整 tracing SDK；仅 HTTP 头 + 日志 + `requestId`。
2. **不**改变 Milvus 风格业务 `code/message/data` 语义；仅追加 `requestId`。
3. **不**在 Writer/Reader 对外（若误暴露）保证 body.`requestId`；契约以 Gateway:19530 为准。
4. **不**在访问日志打印请求/响应 body 或 Authorization。
5. **不**将 Privilege 强制鉴权纳入本次范围。
6. **不**修改 pyxvector 客户端（可选后续：自动传/回显 `X-Request-Id`）。
7. **不**保证客户端自定义 `X-Request-Id` 全局唯一；服务端原样信任。
8. OpenAPI 合并为**尽力而为**：上游 schema 简陋（缺 model）时，docs 仍以路径+tag 可用为验收底线；不强制补全所有 Pydantic 模型（可作为后续优化）。
9. **不**在本阶段编写业务实现代码（本文件确认前）。

---

## 7. 验收标准

1. **Trace 优先级**：分别只带 `X-Request-Id` / `X-Trace-Id` / `traceparent` / 全无，Gateway 与下游日志、`X-Request-Id` 响应头一致；生成值匹配 `^xv-[0-9a-f]{32}$`。
2. **传递**：Gateway → Writer/Reader 请求头含同一 `X-Request-Id`；三容器 Start/End 日志可按该 id grep 对齐。
3. **日志**：每条请求两条访问日志（Start/End）；UTC `...Z` 前缀；End 含 status 短语。
4. **requestId**：经 Gateway 的 JSON object 响应（含 401/500）均含 `requestId`；响应头始终有 `X-Request-Id`；直连 Writer JSON **无**强制 `requestId`，但有响应头。
5. **Docs**：打开 `http://127.0.0.1:19530/docs` 可见合并后的 Writer/Reader 路径；tag 形如 `Writer / Collection`、`Reader / Vector`、`Gateway / System`、`Gateway / Admin`；**无** catch-all `{full_path}`。
6. **Authorize**：Swagger 可 Authorize；带 Bearer 可 Try 业务接口；`POST /v2/vectordb/auth` 在 System 分组。
7. **description**：含 Base URL、认证、`X-Request-Id`/`requestId`、curl 示例。
8. **刷新**：杀掉 Writer 时定时刷新失败不清空旧文档；恢复后自动或 `POST /openapi/refresh` 可更新；refresh **无需**鉴权。
9. **W/R UI**：Writer/Reader 默认访问 `/docs` 为 404；`/openapi.json` 仍 200。
10. **回归**：现有健康检查与 E2E 鉴权/业务主路径不因中间件破坏。

---

## 8. 实现顺序建议（确认 keep 后）

1. `trace` 解析/生成 + 三角色中间件（日志 + 响应头；Gateway body 注入）。
2. 改造 `proxy.forward` 与 `__main__` access log。
3. W/R 关闭 docs UI；Gateway 隐藏 catch-all；新增 auth + openapi refresh。
4. OpenAPI 合并器 + 定时任务 + description/security。
5. 配置项与 `.env.example` / compose。
6. 补充 pytest/E2E 用例。

---

## 9. 待确认后才 coding 的说明

本说明书依据已确认的 10 条决策与仓库现状只读调研写成，**尚未修改** `xvector/` 下任何运行代码。

实现前请确认：

- Tag 映射中 `databases` → `Database`、`entities` → `Vector` 是否接受。
- 认证接口路径 `POST /v2/vectordb/auth` 是否接受。
- §4.6 建议默认值（刷新 60s、重试 3 次、间隔 1s 等）是否接受。
- 对外 docs **默认不展示** `/internal/*` 是否接受。

---

# ✅ 确认区（请回复 keep）

请审阅本说明书。若无异议或仅有已口头确认的微调，请回复：

## **keep**

收到 **keep** 后，将严格按本文开始 coding（trace 中间件、访问日志、Gateway `requestId`、OpenAPI 合并与 Swagger、配置项与验收用例），**在此之前不写业务实现代码**。
