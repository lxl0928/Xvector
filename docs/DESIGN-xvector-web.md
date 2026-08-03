# Xvector Dashboard Web（xvector_web）设计说明书

> 版本：v1.0（已 keep，按本说明书实现）  
> 范围：仓库根目录新增 `xvector_web`（Vue3 + Ant Design Vue），对齐 Attu 风格的管理控制台；对接 Gateway 原生接口；Docker 独立服务暴露 `19531`  
> 前置：`docs/DESIGN.md`（整体架构）、Gateway `:19530` 已提供 `/v2/vectordb/**`、`/healthz`、`/readyz`、`POST /v2/vectordb/auth`

---

## 1. 背景与目标

### 1.1 背景

Xvector 以 Docker Compose 部署 Gateway / Writer / Reader。管理侧需要类似 [Milvus Attu](https://github.com/zilliztech/attu) 的 Web 控制台，用于登录、浏览数据库与 Collection、执行向量检索与数据操作。

约束（来自 `TODO-List.md`）：

1. 技术栈：Vue3 + Ant Design UI。
2. 目录：仓库根目录新增 `xvector_web`。
3. 接口：尽可能只调 Writer / Reader / Gateway **原生接口**，不新增 dashboard 业务后端。
4. 部署：独立 Web 服务，端口 **19531**，登录页 `http://{xvector api host}:19531/login`。

### 1.2 目标

1. 提供可登录的管理 Web，登录后进入当前用户的数据库列表。
2. 支持 Database / Collection / Partition / Index / Alias 管理（见 §2 已确认范围）。
3. Collection 详情支持：Schema 查看、向量 Search、实体数据浏览（近似分页）及 Insert / Upsert / Delete。
4. 生产环境通过 Nginx 同源反代 `/api/*` → Gateway `:19530`，浏览器无跨域。
5. 更新 `Dockerfile`（Web 专用）与 `docker-compose.yaml`，使 `xvector_web` 可随栈启动。

### 1.3 非目标（首期不做）

| 项 | 说明 |
|----|------|
| 用户 / 角色管理 UI | 原生 API 存在，首期不做页面 |
| Import 任务 UI | 首期不做 |
| Hybrid Search UI | 首期仅普通 `entities/search` |
| Database 属性更新 | 原生无 update/alter |
| Collection Schema 变更 | 原生无 alter field；首期不提供改字段 |
| 新增 dashboard 业务 API | 除 Nginx 反代外不增加 Python/BFF 接口 |
| 监控指标大盘 | 仅 `/healthz` + `/readyz` 状态条 |

---

## 2. 已确认决策摘要

| # | 主题 | 已确认决策 |
|---|------|------------|
| 1 | Database「更新」 | **不做**更新入口 |
| 2 | Collection「更新」 | **rename** + **load/release**（状态类操作） |
| 3 | 数据列表分页 | 前端用 **主键 filter + limit** 近似翻页；无总页数；仅「上一页 / 下一页」 |
| 4 | API 访问方式 | Nginx 同源反代：浏览器请求 `/api/*` → 转发 Gateway `:19530`；去掉 `/api` 前缀 |
| 5 | 登录凭证存放 | `localStorage`；刷新/重开浏览器保持登录 |
| 6 | MVP 功能范围 | TODO 模块 + **分区 + 索引 + 别名**（对齐 Attu 更大范围） |
| 7 | 前端技术栈 | Vite + Vue3 + **TypeScript** + Ant Design Vue 4 + Vue Router + Pinia |
| 8 | 默认数据库名 | 以 API 为准：`default`（TODO 中 `_default` 视为笔误） |
| 9 | 数据页写操作 | 浏览 + Search + **Insert + Upsert + Delete** |
| 10 | 界面语言 | 中英 **i18n**，**默认中文** |
| 11 | 删除策略 | **禁止删除 `default` 库**；其余库/Collection/实体删除均需**二次确认** |

---

## 3. 现状分析（基于现有后端）

### 3.1 对外入口

| 服务 | 端口 | Web 是否直连 |
|------|------|--------------|
| Gateway | **19530** | **是**（经 Nginx `/api` 反代） |
| Writer | 18081 | 否（内网） |
| Reader | 18082 | 否（内网） |

鉴权：`Authorization: Bearer {USERNAME}:{PASSWORD}`（第一个 `:` 分割）。  
业务路径：`POST /v2/vectordb/...`；响应信封：`{ code, message, data, requestId? }`。  
探活：`GET /healthz`、`GET /readyz`（无需鉴权）。  
登录校验：`POST /v2/vectordb/auth`（需 Bearer）。

### 3.2 首期将使用的原生接口清单

> 下表路径均为 Gateway 绝对路径；前端实际请求为 `/api` + 下表路径。

#### 系统 / 认证

| 用途 | 方法 | 路径 |
|------|------|------|
| 存活 | GET | `/healthz` |
| 就绪 | GET | `/readyz` |
| 登录校验 | POST | `/v2/vectordb/auth` |

#### Database

| 用途 | 方法 | 路径 | Body 要点 |
|------|------|------|-----------|
| 列表 | POST | `/v2/vectordb/databases/list` | `{}` |
| 创建 | POST | `/v2/vectordb/databases/create` | `{ dbName }` |
| 删除 | POST | `/v2/vectordb/databases/drop` | `{ dbName }` |
| 详情 | POST | `/v2/vectordb/databases/describe` | `{ dbName }` |

#### Collection

| 用途 | 方法 | 路径 | Body 要点 |
|------|------|------|-----------|
| 列表 | POST | `/v2/vectordb/collections/list` | `{ dbName }` |
| 创建 | POST | `/v2/vectordb/collections/create` | schema（见 OpenAPI） |
| 删除 | POST | `/v2/vectordb/collections/drop` | `{ collectionName, dbName? }` |
| 详情/Schema | POST | `/v2/vectordb/collections/describe` | `{ collectionName, dbName? }` |
| 重命名 | POST | `/v2/vectordb/collections/rename` | `{ collectionName, newCollectionName, dbName? }` |
| 加载 | POST | `/v2/vectordb/collections/load` | `{ collectionName, dbName? }` |
| 释放 | POST | `/v2/vectordb/collections/release` | `{ collectionName, dbName? }` |
| 加载状态 | POST | `/v2/vectordb/collections/get_load_state` | `{ collectionName, dbName? }` |
| 行数 | POST | `/v2/vectordb/collections/get_stats` | `{ collectionName, dbName? }` |

#### Partition

| 用途 | 方法 | 路径 |
|------|------|------|
| 列表/创建/删除/是否存在/统计/加载/释放 | POST | `/v2/vectordb/partitions/{list,create,drop,has,get_stats,load,release}` |

#### Index

| 用途 | 方法 | 路径 |
|------|------|------|
| 列表/创建/删除/详情 | POST | `/v2/vectordb/indexes/{list,create,drop,describe}` |

#### Alias

| 用途 | 方法 | 路径 |
|------|------|------|
| 列表/创建/删除/修改/详情 | POST | `/v2/vectordb/aliases/{list,create,drop,alter,describe}` |

#### Entities（数据）

| 用途 | 方法 | 路径 |
|------|------|------|
| Query 浏览 | POST | `/v2/vectordb/entities/query` |
| Search | POST | `/v2/vectordb/entities/search` |
| Get by id | POST | `/v2/vectordb/entities/get` |
| Insert | POST | `/v2/vectordb/entities/insert` |
| Upsert | POST | `/v2/vectordb/entities/upsert` |
| Delete | POST | `/v2/vectordb/entities/delete` |

写后立即读：请求头加 `X-XVector-Refresh: true`（或 body `refresh: true`）。

### 3.3 已知能力缺口与前端对策

| 缺口 | 对策 |
|------|------|
| 无 database update | UI 不提供更新 |
| 无 schema alter | UI 不提供改字段；需重建 Collection |
| query 无 offset | 见 §6.5 主键游标翻页 |
| query/search 需 collection 已 load | UI 展示 load 状态；未 load 时引导用户 Load |

---

## 4. 总体架构

```
Browser
  │  http://{host}:19531/login
  ▼
xvector_web (Nginx :19531)
  ├─ /          → 静态资源（Vite build）
  └─ /api/*     → proxy_pass http://gateway:19530/*   （去掉 /api 前缀）
                      │
                      ▼
                 Gateway :19530
                   ├─ Writer :18081
                   └─ Reader :18082
```

原则：

1. **无 BFF**：Web 容器只做静态托管 + 反代。
2. **前端只认相对路径** `/api/...`，不写死 `:19530`。
3. 本地开发：Vite `server.proxy` 将 `/api` 转到本机 Gateway（默认 `http://127.0.0.1:19530`），与生产行为一致。

---

## 5. 工程结构与技术选型

### 5.1 目录（拟）

```
xvector_web/
  package.json
  vite.config.ts
  tsconfig.json
  index.html
  .env.development
  .env.production
  nginx.conf
  Dockerfile
  src/
    main.ts
    App.vue
    locales/          # zh-CN / en-US
    router/
    stores/           # auth、app（语言等）
    api/              # axios 封装 + 各资源 API
    views/
      login/
      databases/
      collections/
      collection-detail/   # tabs: schema / data / search / partitions / indexes / aliases
    components/
    utils/            # 分页游标、错误解析、向量 JSON 解析等
    types/
```

### 5.2 依赖（核心）

| 包 | 用途 |
|----|------|
| vue ^3 | UI 框架 |
| ant-design-vue ^4 | 组件库 |
| vue-router ^4 | 路由 |
| pinia | 状态 |
| axios | HTTP |
| vue-i18n | 中英切换 |
| dayjs | 时间（若 AntDV 需要） |

包管理器：优先 **npm**（与多数 CI 镜像兼容；`package-lock.json` 入仓）。

### 5.3 构建与运行

| 环境 | 方式 |
|------|------|
| 本地开发 | `npm run dev`（Vite，默认端口可 5173；proxy `/api`） |
| 生产镜像 | 多阶段：`node` build → `nginx:alpine` 托管 `dist` + `nginx.conf` |
| Compose | 服务名 `xvector_web`，`ports: ["19531:80"]`，依赖 `gateway` healthy |

---

## 6. 功能设计

### 6.1 路由

| 路径 | 页面 | 鉴权 |
|------|------|------|
| `/login` | 登录 | 无 |
| `/` | 重定向到 `/databases` | 需登录 |
| `/databases` | 数据库列表 + 顶部健康状态 | 需登录 |
| `/databases/:dbName` | 该库下 Collection 列表 | 需登录 |
| `/databases/:dbName/collections/:collectionName` | Collection 详情（多 Tab） | 需登录 |

路由守卫：无 `localStorage` 凭证 → 跳转 `/login`；已登录访问 `/login` → 跳转 `/databases`。

### 6.2 登录

1. 表单：Username、Password。
2. 组装 `Authorization: Bearer ${username}:${password}`，调用 `POST /api/v2/vectordb/auth`，body `{}`。
3. `code === 0`：将 `{ username, password }` 写入 `localStorage`（建议 key：`xvector_web_auth`），跳转 `/databases`。
4. 失败：展示 `message` / HTTP 401。
5. 顶栏提供「退出」：清除 `localStorage` 并回登录页。

> 说明：与 Gateway 一致，凭证即 Bearer 明文用户名密码；localStorage 有 XSS 风险，首期接受该模型（与 Attu 类工具常见做法一致），不额外加密。

### 6.3 数据库列表页

**顶部状态条**

- 并行请求 `GET /api/healthz`、`GET /api/readyz`。
- 展示：Gateway status / ready 状态（ok / not_ready）；失败标红。
- 可手动刷新。

**列表**

- `POST /api/v2/vectordb/databases/list` → 表格展示库名。
- 操作：新建、删除（`default` **隐藏/禁用删除**）、进入详情（跳转 Collection 列表）、查看 describe。
- 新建：Modal 输入 `dbName` → `databases/create` → 刷新列表。
- 删除：二次确认 Modal（输入库名或确认文案）→ `databases/drop`。
- **无「更新」按钮**。

### 6.4 Collection 列表页（某 Database 下）

- `collections/list` + 可选对每个 collection 拉取 `get_load_state` / `get_stats`（注意 N+1；首期可列表仅名称，详情页再拉状态；若性能可接受可批量并行、限制并发）。
- 操作：
  - **新建**：Schema 表单（主键字段、向量字段 dim、metric 相关在 Index Tab 创建；创建 collection 时至少主键 + FloatVector）。
  - **删除**：二次确认 → `collections/drop`。
  - **重命名**：Modal → `collections/rename`。
  - **Load / Release**：确认后调用对应接口；展示当前 load state。
  - **进入详情**。

### 6.5 Collection 详情页（Tabs）

#### Tab A — Schema

- `collections/describe` 展示 fields / indexes 摘要 / autoId 等（只读）。

#### Tab B — Data（实体浏览）

- 前置：若未 Load，提示并提供 Load 按钮。
- 列表：`entities/query`。
- **近似分页算法（主键游标）**：
  1. 从 describe 解析主键字段名与类型（优先 Int64；VarChar 同样支持但比较符语义按字符串）。
  2. 状态保存：`pageSize`（默认 20）、`cursor`（上一页最后一条主键）、`historyStack`（用于上一页）。
  3. 首页：`filter: "{pk} >= 0"`（Int64）或适当全量条件 + `limit: pageSize`；若主键非数值，首页可用 `filter: "{pk} != \"\""` 或后端可接受的宽 filter（实现时以 Reader 实际 filter 语法为准，优先对齐现有 e2e/query 用例）。
  4. 下一页：`filter: "{pk} > {lastPk}"` + `limit`；将当前首页主键压栈。
  5. 上一页：从 `historyStack` 弹出，用上一游标重查（不依赖 offset）。
  6. 无总条数、无页码跳转；可用 `get_stats.rowCount` 仅作「约 N 行」提示（非精确分页总数）。
- 工具栏：Insert / Upsert（JSON 或表单按 schema 动态字段）/ Delete（选中行或 filter）。
- 写操作成功后带 `X-XVector-Refresh: true` 再刷新当前页。
- **所有 Delete 二次确认**。

#### Tab C — Search

- 表单：`annsField`、向量 JSON/`[f1,f2,...]`、`limit`（topK）、可选 `filter`、`outputFields`、`searchParams`（如 `ef`）。
- 调用 `entities/search`；结果表格展示 id / score / distance / 输出字段。

#### Tab D — Partitions

- list / create / drop（二次确认）/ load / release / get_stats。

#### Tab E — Indexes

- list / describe / create（indexType、metricType、params）/ drop（二次确认）。

#### Tab F — Aliases

- list / create / drop（二次确认）/ alter / describe。

### 6.6 全局 UX 约定

1. API `code !== 0`：用 Ant Design `message.error` 展示 `message` 字段。
2. HTTP 401：清空凭证并跳转登录。
3. 危险操作（drop database / collection / partition / index / alias / entities delete）：`Modal.confirm` 二次确认；删除 database 时禁止 `default`。
4. 顶栏：当前用户名、语言切换（zh-CN / en-US）、退出、可选刷新健康状态。
5. 面包屑：Databases → `{db}` → `{collection}`。

### 6.7 i18n

- `vue-i18n`，默认 `zh-CN`，可切换 `en-US`，选择写入 `localStorage`（key：`xvector_web_locale`）。
- 覆盖：菜单、按钮、表单校验、空状态、确认框文案、错误兜底文案。
- API 返回的英文 `message` 可原样展示或做常见 code 映射（首期原样 + 少量映射即可）。

---

## 7. Nginx 与 Docker

### 7.1 `xvector_web/nginx.conf`（要点）

```nginx
server {
  listen 80;
  root /usr/share/nginx/html;
  index index.html;

  location /api/ {
    proxy_pass http://gateway:19530/;   # 注意：去掉 /api 前缀
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header Authorization $http_authorization;
    proxy_set_header X-Request-Id $http_x_request_id;
    proxy_set_header X-XVector-Refresh $http_x_xvector_refresh;
  }

  location / {
    try_files $uri $uri/ /index.html;   # SPA history 模式
  }
}
```

### 7.2 `xvector_web/Dockerfile`（多阶段）

1. Stage `build`：`node:20-alpine`，`npm ci && npm run build`。
2. Stage `runtime`：`nginx:1.27-alpine`，拷贝 `dist` + `nginx.conf`，`EXPOSE 80`。

> 仓库根目录现有 `Dockerfile` 继续服务 Python 三角色；**Web 使用 `xvector_web/Dockerfile`**，不混进 Python 镜像。

### 7.3 `docker-compose.yaml` 增量

新增服务：

```yaml
xvector_web:
  build:
    context: ./xvector_web
  image: xvector-web:local
  ports:
    - "19531:80"
  depends_on:
    gateway:
      condition: service_healthy
  # 可选：轻量 healthcheck curl localhost/
```

访问：

- 登录页：`http://{host}:19531/login`
- API（浏览器侧）：`http://{host}:19531/api/v2/vectordb/...` → Gateway

无需改 Gateway CORS（同源反代）。

---

## 8. 前端 API 封装约定

```ts
// 伪代码
const http = axios.create({ baseURL: '/api', timeout: 60000 });

http.interceptors.request.use((config) => {
  const auth = loadAuth(); // localStorage
  if (auth) {
    config.headers.Authorization = `Bearer ${auth.username}:${auth.password}`;
  }
  return config;
});

http.interceptors.response.use(
  (res) => {
    const body = res.data;
    if (body && typeof body.code === 'number' && body.code !== 0) {
      return Promise.reject(body);
    }
    return res;
  },
  (err) => {
    if (err.response?.status === 401) logoutAndRedirect();
    return Promise.reject(err);
  },
);
```

各资源文件：`api/databases.ts`、`api/collections.ts`、`api/entities.ts`、`api/partitions.ts`、`api/indexes.ts`、`api/aliases.ts`、`api/system.ts`。

---

## 9. 实现分期（coding 阶段按此顺序）

| 阶段 | 内容 | 验收 |
|------|------|------|
| P0 | 工程脚手架、axios、auth store、login、路由守卫、i18n 骨架、Nginx/Dockerfile/compose | 可打开 `/login` 并登录跳转 |
| P1 | Databases 页：healthz/readyz + list/create/drop/describe | 列表与禁删 default |
| P2 | Collections 页：list/create/drop/rename/load/release | CRUD+状态操作可用 |
| P3 | Collection 详情：Schema + Data 游标翻页 + Insert/Upsert/Delete | 数据页完整 |
| P4 | Search Tab | 向量检索可用 |
| P5 | Partitions / Indexes / Aliases Tabs | 三类资源可用 |
| P6 | 文案打磨、空态/错误态、README（`xvector_web/README.md` 简短说明） | compose 一键起全栈可访问 19531 |

---

## 10. 测试与验收清单

手工验收（compose 全栈）：

1. `http://127.0.0.1:19531/login` 可打开；错误密码失败；正确密码进入数据库列表。
2. 顶栏 healthz/readyz 状态正确。
3. 可创建非 default 库；不可删除 `default`；删除其他库有二次确认。
4. 进入库 → Collection 增删改名、load/release。
5. Collection 详情可见 schema；数据上一页/下一页；Insert/Upsert/Delete（删前确认）；Search 返回结果。
6. Partition / Index / Alias 基本 CRUD（删前确认）。
7. 中英切换生效且刷新后保持。
8. 刷新浏览器仍保持登录；退出后需重新登录。
9. 浏览器 Network 中业务请求走 `:19531/api/...`，无直连 `:19530` 的跨域请求。

---

## 11. 风险与开放细节（实现时按此默认，无需再决策）

| 项 | 默认处理 |
|----|----------|
| 主键非 Int64 | 游标 filter 按类型生成（VarChar 用引号与字符串比较）；无法识别主键时禁用翻页并提示 |
| list 后 N+1 拉状态 | Collection 列表默认不强制拉全量 stats；详情/操作时再拉 |
| 大向量列展示 | 表格中截断显示，支持 Modal 查看全文 JSON |
| Create Collection 表单复杂度 | 首期提供「常用模板」+「高级 JSON」两种创建方式，降低表单复杂度 |
| 包管理 | npm + package-lock.json |
| 根 README | coding 完成后在根 `README.md` 增加 Web 访问说明一小段（若你希望完全不改根 README，实现时可只写 `xvector_web/README.md`） |

---

## 12. 待你确认

请审阅本说明书。若无误，请回复 **keep**；收到后按 §9 分期开始 coding。  
若需修改，请直接指出章节与改动点，我更新文档版本后再请你 keep。
