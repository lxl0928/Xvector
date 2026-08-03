# Xvector Writer / Reader API Request & Response Models 设计说明书

> 版本：v1.1（已确认，实现中）  
> 范围：Writer / Reader 各业务 API 的 request body model、response body model、`__example__` / OpenAPI examples  
> 前置：`docs/DESIGN.md`（整体架构）、`docs/DESIGN-api-docs-and-logging.md`（Gateway 注入 `requestId`、OpenAPI 合并）

---

## 已确认决策

| # | 主题 | 已确认决策 |
|---|------|------------|
| Q1 | Request 字段严格度 | **仅接受 camelCase**（OpenAPI 与运行时一致；snake_case 请求 → 422）。用户表述「选 A」的实际意图为此严格模式，**不是**「运行时仍 AliasChoices 接受 snake_case」。 |
| Q2 | Role describe privileges | **A**：API 响应规范为 camelCase（`objectType` / `objectName` / `privilege`）；catalog 存储可仍 snake_case，API 层映射 |
| 客户端 / 测试 | 全面 camelCase | **pyxvector** 请求/响应字段严格 camelCase；**tests/**（unit/e2e/performance 等）请求参数与响应断言全面改为 camelCase；仓库内其它上下游调用方一并对齐 |
| UserCreateData | 响应键名 | 保持 `username`（与历史 service 一致） |
| schema.fields | 字段键名 | 对外仅 camelCase：`dataType` / `isPrimaryKey` / `autoID` / `enableDynamicField` 等（不再接受 `data_type` / `is_primary_key`） |

---

## 1. 背景与目标

### 1.1 背景

当前 Writer / Reader 路由（`xvector/api/v2/routes.py`）几乎全部使用：

```python
body = await request.json()
return ok(await svc.xxx(...))
```

- **无** Pydantic request/response model
- **无** `response_model` / OpenAPI `components.schemas`
- Gateway 合并 `/openapi.json` 后，Swagger 只能看到路径，**看不到**结构化 body 与示例
- `docs/DESIGN.md` 规划了 `xvector/common/models.py`，**仓库中尚不存在**

同时：

- 业务语义与字段以 **services + pyxvector + e2e/性能测试调用** 为准
- 路径风格对齐 **Milvus REST API v2**（`/v2/vectordb/...`，多为 POST + JSON）
- Gateway 对外 JSON 会注入 `requestId`（见 `DESIGN-api-docs-and-logging.md`）；Writer/Reader **不改 body**

### 1.2 目标（确认 keep 后实现）

1. 为 Writer / Reader **全部业务 API** 定义 request / response Pydantic model。
2. 成功响应外壳统一为 `code` / `message` / `data`，并在模型层 **预留** `requestId`（OpenAPI 可见；运行时由 Gateway 注入）。
3. 每个对外业务操作附带可在 Swagger 展示的 example（`json_schema_extra.examples` 或等价）。
4. 路由改为声明式：`body: XxxRequest` + `response_model=ApiResponse[XxxData]`（或等价包装），使 Writer/Reader `/openapi.json` 可被 Gateway 合并出完整文档。

### 1.3 非目标

1. **不**在本阶段改动 services 业务逻辑（除非发现契约与实现严重冲突，列入「差距」待 keep 后处理）。
2. **不**把 `/internal/*` 默认暴露进对外 docs（与 logging 设计一致）；本说明书仍给出内部 model 建议，实现时 `include_in_schema=False`。
3. **不**引入 OpenTelemetry 等；`requestId` 仅兼容 Gateway 注入约定。
4. **不**强制实现 Milvus「Quick Setup」建表（仅 `dimension` 无 `schema`）——当前 `parse_milvus_schema` **不支持**；本设计以现有实现为准，Quick Setup 标为后续可选增强。
5. ~~不修改 pyxvector~~ → **已确认**：pyxvector / tests 全面严格 camelCase。

---

## 2. 总则

### 2.1 命名约定

| 项 | 约定 |
|----|------|
| JSON 字段 | **仅 camelCase**（对齐 Milvus REST / pyxvector；snake_case → 422） |
| Python 模型类名 | `PascalCase`，后缀 `Request` / `Data` / `Response` |
| 文件/模块 | `xvector/common/models/` 包（按资源拆分；见 §7） |
| 路径资源名 | Alias / Collection / Import / Index / Partition / Role / User / Vector；另含 **Database**（代码已实现） |
| Vector 路径 | HTTP 仍为 `/entities/*`；OpenAPI tag 资源名 **Vector** |

**字段别名策略（已确认：仅 camelCase）**

- OpenAPI / 文档字段：**仅 camelCase**
- 运行时校验：**不**接受 snake_case（如 `collection_name`、`data_type`）；同语义的 camelCase 变体可保留（如 `oldName`↔`collectionName`、`password`↔`oldPassword`、`name`↔`fieldName`）
- 序列化输出：响应只出 camelCase

### 2.2 公共字段与外壳

#### 2.2.1 成功响应外壳

```json
{
  "code": 0,
  "message": "success",
  "data": { },
  "requestId": "xv-0123456789abcdef0123456789abcdef"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `int` | 成功固定 `0` |
| `message` | `str` | 成功固定 `"success"`（与 `errors.ok` 一致） |
| `data` | `T` | 业务载荷；无业务数据时为 `{}`；列表类接口可为 `array` |
| `requestId` | `str \| null` | **可选**；Gateway 注入；Writer/Reader 直连时通常缺失 |

建议泛型：

```python
class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T
    requestId: str | None = None  # Gateway 注入；模型层允许缺失
```

> **兼容要点**：`requestId` 不得标为 required；`extra` 建议 `ignore`（或对 envelope 允许未知字段），避免 Gateway 注入后客户端严格校验失败。W/R 实现阶段 **仍不**在本地写入 `requestId`。

#### 2.2.2 错误响应外壳

对齐 `XvectorError.to_dict` / `internal_error_body`：

```json
{
  "code": 100,
  "message": "...",
  "requestId": "xv-..."
}
```

500 额外可有 `error_message`：

```json
{
  "code": 2000,
  "message": "Internal Error: ...",
  "error_message": "...",
  "requestId": "xv-..."
}
```

建议模型：

| Model | 字段 |
|-------|------|
| `ErrorResponse` | `code: int`, `message: str`, `requestId: str \| None = None` |
| `InternalErrorResponse` | 继承上表 + `error_message: str` |

常用 `code`（来自 `xvector/common/errors.py`）：`100` 参数、`1001` 未找到、`1200` 未加载、`1800` 未授权、`1801` 禁止、`2000` 内部、`2100` 索引不支持、`2200` 导入失败、`65535` 已存在。

#### 2.2.3 公共请求片段

| Model | 关键字段 | 说明 |
|-------|----------|------|
| `DbScopedRequest` | `dbName: str = "default"` | 几乎所有业务 body；pyxvector `_with_db` 总会带上 |
| `CollectionScopedRequest` | `dbName`, `collectionName: str` | Collection / Partition / Index / Vector 等 |
| `EmptyObject` | （无字段 / 允许空对象） | `data: {}` 成功体；`list` 类可空 body |
| `HasData` | `has: bool` | has_collection / has_partition |
| `RowCountData` | `rowCount: int` | get_stats |

### 2.3 Example 约定

1. **优先** Pydantic v2：

   ```python
   model_config = ConfigDict(
       json_schema_extra={
           "examples": [
               {"collectionName": "demo", "dbName": "default"}
           ]
       }
   )
   ```

2. 若需兼容用户口中的 `__example__`：可在模块级常量 `XxxRequest.__example__ = {...}`，并在 `json_schema_extra` 中引用同一对象，避免双份维护。
3. Example **必须**：
   - 字段名 camelCase
   - 可被当前 service 接受（或标明「文档示例 / 最小可用」）
   - 不含真实密码明文时可使用占位：`"password": "******"`（User 类除外可给演示值 `Passw0rd!`）
4. 向量示例维度用 **小维度**（如 4 或 8），避免 Swagger 刷屏；注明生产常用 768/1024。
5. `ApiResponse` 的 example **包含** `requestId`，标明「经 Gateway 时出现」。

### 2.4 OpenAPI / FastAPI 绑定约定

| 项 | 建议默认 |
|----|----------|
| 方法 | 业务接口一律已有的 `POST`（保持不变） |
| Request | `body: XxxRequest`（勿再 `await request.json()` 手工拆，除非 Empty body） |
| Response | `response_model=ApiResponse[XxxData]`；列表用 `ApiResponse[list[...]]` |
| 空 data | `ApiResponse[EmptyObject]` 或 `ApiResponse[dict[str, Any]]` 且 example `{}` |
| 校验失败 | 已有 `RequestValidationError` → HTTP 422 + `code=100`；保持 |
| tags | 资源级短名（`Collection` / `Vector`…）；Gateway 合并改写为 `Writer / Collection` |
| Internal | `include_in_schema=False` |

### 2.5 `requestId` 兼容（强制）

| 角色 | body.`requestId` | 模型要求 |
|------|------------------|----------|
| Gateway | 注入/覆盖 | 对外契约含该字段 |
| Writer / Reader | **不写入** | Response model **可选**字段即可 |
| 客户端 / pyxvector | 可忽略 | `HttpClient` 只取 `data`；不破坏 |

实现时禁止把 `requestId` 做成必填，禁止因缺省 `requestId` 导致 response_model 校验失败（若启用响应校验，需 `response_model_exclude_unset` 或可选字段）。

---

## 3. Writer API 清单

> 路径前缀均为 `/v2/vectordb`。`data` 列指外壳内的业务载荷类型。  
> 统计：**逻辑操作 35**（不含 health/heartbeat/internal）；其中 Import / Role list / User list 存在路径别名，共用同一对 Request/Response model。

### 3.1 Database（Writer）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| W1 | `POST /databases/create` | `DatabaseCreateRequest` | `EmptyObject` | `dbName` | `{"dbName":"demo_db"}` |
| W2 | `POST /databases/drop` | `DatabaseDropRequest` | `EmptyObject` | `dbName` | 同上 |

### 3.2 Alias（Writer）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| W3 | `POST /aliases/create` | `AliasCreateRequest` | `EmptyObject` | `aliasName`, `collectionName`, `dbName?` | 绑定 alias→collection |
| W4 | `POST /aliases/drop` | `AliasDropRequest` | `EmptyObject` | `aliasName`, `dbName?` | |
| W5 | `POST /aliases/alter` | `AliasAlterRequest` | `EmptyObject` | `aliasName`, `collectionName`, `dbName?` | 改绑定 |

### 3.3 Collection（Writer）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| W6 | `POST /collections/create` | `CollectionCreateRequest` | `EmptyObject` | `collectionName`, `schema.fields`（含唯一 PK + ≥1 向量）, `dbName?`, `enableDynamicField?`, `shardsNum?`, `consistencyLevel?` | 完整 schema；**不**宣称 Quick Setup |
| W7 | `POST /collections/drop` | `CollectionNameRequest` | `EmptyObject` | `collectionName` | |
| W8 | `POST /collections/rename` | `CollectionRenameRequest` | `EmptyObject` | `collectionName`, `newCollectionName` | 兼容 camelCase 旧键 `oldName`/`newName`（非 snake_case） |
| W9 | `POST /collections/load` | `CollectionLoadRequest` | `EmptyObject` | `collectionName`, `replicaNumber?=1` | |
| W10 | `POST /collections/release` | `CollectionNameRequest` | `EmptyObject` | `collectionName` | |

**`CollectionCreateRequest` 结构要点（对齐 `schema_map.parse_milvus_schema` + tests）**

```json
{
  "dbName": "default",
  "collectionName": "demo",
  "schema": {
    "autoID": false,
    "enableDynamicField": false,
    "fields": [
      {"name": "id", "dataType": "Int64", "isPrimaryKey": true, "autoID": false},
      {"name": "vector", "dataType": "FloatVector", "dim": 8}
    ]
  }
}
```

字段模型建议：`SchemaField`（`name`/`fieldName`，`dataType`/`type`，`isPrimaryKey`/`isPrimary`，`dim`，`autoID`…）、`CollectionSchema`、`CollectionCreateRequest`。**不**接受 `data_type` / `is_primary_key`。

### 3.4 Partition（Writer）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| W11 | `POST /partitions/create` | `PartitionNameRequest` | `EmptyObject` | `collectionName`, `partitionName` | 禁止 `_default`（service 校验） |
| W12 | `POST /partitions/drop` | `PartitionNameRequest` | `EmptyObject` | 同上 | 禁止 drop `_default` |
| W13 | `POST /partitions/load` | `PartitionLoadReleaseRequest` | `EmptyObject` | `collectionName`, `partitionNames[]` 或单 `partitionName` | |
| W14 | `POST /partitions/release` | `PartitionLoadReleaseRequest` | `EmptyObject` | 同上 | |

### 3.5 Index（Writer）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| W15 | `POST /indexes/create` | `IndexCreateRequest` | `EmptyObject` | `collectionName`, `fieldName`, `indexName?`, `indexType`/`indexParams`, `metricType`, `params?` | HNSW：`{"M":16,"efConstruction":200}` |
| W16 | `POST /indexes/drop` | `IndexDropRequest` | `EmptyObject` | `collectionName`, `indexName` | |

**`IndexCreateRequest` 兼容形态（与 service 一致）**

- 扁平：`indexType`, `metricType`, `params`
- 或 `indexParams` 为 object / Milvus 风格 `{key,value}[]`
- pyxvector 使用扁平形态 —— example 以扁平为准

### 3.6 Import（Writer）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| W17 | `POST /jobs/import/create` **及** `/import/create` | `ImportCreateRequest` | `ImportCreateData` | `collectionName`, `files[]`, `format?=json`, `partitionName?` | `format`: `json`\|`jsonl`；文件可为本地路径或 `s3://` |
| W18 | `POST /jobs/import/get_progress` **及** `/import/get_progress` | `ImportProgressRequest` | `ImportProgressData` | `jobId` | |
| W19 | `POST /jobs/import/list` **及** `/import/list` | `ImportListRequest` | `list[ImportListItem]` | `dbName?`, `collectionName?` | 可空过滤 |

**Response data 字段（来自 `ImportService`）**

| Model | 字段 |
|-------|------|
| `ImportCreateData` | `jobId: str` |
| `ImportProgressData` | `jobId`, `state`, `progress`, `importedRows`, `totalRows`, `reason` |
| `ImportListItem` | `jobId`, `collectionName`, `state`, `progress` |

`state` 示例值：`Pending` / `Downloading` / `Parsing` / `Importing` / `Completed` / `Failed`。

### 3.7 Role（Writer）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| W20 | `POST /roles/create` | `RoleNameRequest` | `EmptyObject` | `roleName` | |
| W21 | `POST /roles/drop` | `RoleNameRequest` | `EmptyObject` | `roleName` | 禁删 `admin` |
| W22 | `POST /roles/describe` | `RoleNameRequest` | `RoleDescribeData` | `roleName` | privileges 列表 |
| W23 | `POST /roles/list` **及** `/roles/lists` | `EmptyRequest` | `list[str]` | （可空 body） | |
| W24 | `POST /roles/grant_privilege` | `RolePrivilegeRequest` | `EmptyObject` | `roleName`, `objectType`, `objectName`, `privilege` | |
| W25 | `POST /roles/revoke_privilege` | `RolePrivilegeRequest` | `EmptyObject` | 同上 | |

**`RoleDescribeData`（建议规范化，见待确认 Q2）**

```json
{
  "roleName": "data_admin",
  "privileges": [
    {"objectType": "Collection", "objectName": "demo", "privilege": "Insert"}
  ]
}
```

> 现状 service 返回 privileges 元素为 **snake_case**（`object_type`…）。实现阶段建议在 **API 层映射为 camelCase**，与 request / Milvus 对齐；catalog 存储可不变。

### 3.8 User（Writer）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| W26 | `POST /users/create` | `UserCreateRequest` | `UserCreateData` | `userName`, `password` | data: `{"username":"..."}`（注意：service 返回键为 `username` 非 `userName`） |
| W27 | `POST /users/drop` | `UserNameRequest` | `EmptyObject` | `userName` | |
| W28 | `POST /users/describe` | `UserNameRequest` | `UserDescribeData` | `userName` | `{"userName","roles":[]}` |
| W29 | `POST /users/list` **及** `/users/lists` | `EmptyRequest` | `list[str]` | | |
| W30 | `POST /users/update_password` | `UserUpdatePasswordRequest` | `EmptyObject` | `userName`, `password`（旧密码）, `newPassword`；兼容 `oldPassword` | pyxvector 用 `password`+`newPassword` |
| W31 | `POST /users/grant_role` | `UserRoleRequest` | `EmptyObject` | `userName`, `roleName` | |
| W32 | `POST /users/revoke_role` | `UserRoleRequest` | `EmptyObject` | 同上 | |

**差距标注**：`UserCreateData` 当前为 `{"username": ...}`，与请求字段 `userName` 不一致。设计建议：

- **建议默认**：响应模型文档化为 `username`（保持现状兼容 pyxvector/e2e），同时在 example 中写清；或 keep 后统一改为 `userName`（需改 service + 测试）。列入 §6，实现前按 Q 确认——见文末 **仅保留更高优先级待确认**，此项默认 **保持 `username`**。

### 3.9 Vector（Writer）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| W33 | `POST /entities/insert` | `VectorInsertRequest` | `VectorInsertData` | `collectionName`, `data`（object\|array）, `partitionName?` | `insertCount`, `insertIds` |
| W34 | `POST /entities/upsert` | `VectorUpsertRequest` | `VectorUpsertData` | 同 insert | `upsertCount`, `upsertIds` |
| W35 | `POST /entities/delete` | `VectorDeleteRequest` | `VectorDeleteData` | `collectionName`, `id`/`ids` **或** `filter`/`expr`, `partitionName?`/`partitionNames?` | `deleteCount` |

**实体 `data` 元素**：`dict[str, Any]`（动态字段依赖 collection schema）；example 给固定形状：

```json
{
  "collectionName": "demo",
  "dbName": "default",
  "data": [
    {"id": 1, "vector": [0.1, 0.2, 0.3, 0.4]}
  ]
}
```

### 3.10 Writer 非对外业务（模型可选，默认不进 schema）

| 路径 | Request | Response | 备注 |
|------|---------|----------|------|
| `POST /internal/auth/verify` | `{username, password}` | `{ok: bool}` | 非 Milvus 外壳；`include_in_schema=False` |
| `GET /v2/vectordb/heartbeat` | — | `{code, data:{role,version}}` | 非标准 `ok()`；可单独模型 |
| `GET /healthz`, `GET /readyz` | — | 健康检查既有结构 | 不在本设计展开 |

---

## 4. Reader API 清单

> 统计：**逻辑操作 18**（不含 internal/health）。

### 4.1 Database（Reader）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| R1 | `POST /databases/list` | `EmptyRequest` / 可空 | `list[str]` | body 可缺省 | |
| R2 | `POST /databases/describe` | `DatabaseDescribeRequest` | `DatabaseDescribeData` | `dbName` | `{"dbName","properties":{}}` |

### 4.2 Alias（Reader）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| R3 | `POST /aliases/describe` | `AliasDescribeRequest` | `AliasDescribeData` | `aliasName` | `aliasName`,`collectionName`,`dbName` |
| R4 | `POST /aliases/list` | `AliasListRequest` | `list[str]` | `collectionName?` | 可按 collection 过滤 |

### 4.3 Collection（Reader）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| R5 | `POST /collections/describe` | `CollectionNameRequest` | `CollectionDescribeData` | `collectionName` | 含 `schema`,`indexes[]`,`autoId`,`shardsNum`,`consistencyLevel` |
| R6 | `POST /collections/has` | `CollectionNameRequest` | `HasData` | | `{"has":true}` |
| R7 | `POST /collections/list` | `DbScopedRequest` / 可空 | `list[str]` | `dbName?` | |
| R8 | `POST /collections/get_load_state` | `CollectionNameRequest` | `LoadStateData` | | `state`/`loadState`：`LoadStateLoaded`\|`LoadStateNotLoad` |
| R9 | `POST /collections/get_stats` | `CollectionNameRequest` | `RowCountData` | | `{"rowCount":0}` |

**`CollectionDescribeData`（对齐 `CollectionService.describe_collection`）**

```json
{
  "collectionName": "demo",
  "dbName": "default",
  "schema": {},
  "shardsNum": 1,
  "consistencyLevel": "Eventually",
  "indexes": [
    {"fieldName": "vector", "indexName": "vector_idx", "indexType": "HNSW", "metricType": "L2"}
  ],
  "autoId": false
}
```

### 4.4 Partition（Reader）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| R10 | `POST /partitions/has` | `PartitionNameRequest` | `HasData` | `collectionName`,`partitionName` | |
| R11 | `POST /partitions/list` | `CollectionNameRequest` | `list[str]` | | 含 `_default` |
| R12 | `POST /partitions/get_stats` | `PartitionNameRequest` | `RowCountData` | `partitionName` 缺省 `_default` | |

### 4.5 Index（Reader）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| R13 | `POST /indexes/describe` | `IndexDescribeRequest` | `list[IndexDescribeItem]` | `collectionName`, `indexName?` | **data 直接为数组**（现状） |
| R14 | `POST /indexes/list` | `CollectionNameRequest` | `list[str]` | | indexName 列表 |

**`IndexDescribeItem`**：`indexName`, `fieldName`, `indexType`, `metricType`, `indexState`, `params`。

### 4.6 Vector（Reader）

| # | 方法/路径 | Request | Response `data` | 关键字段 | Example 要点 |
|---|-----------|---------|-----------------|----------|--------------|
| R15 | `POST /entities/get` | `VectorGetRequest` | `list[Entity]` | `collectionName`, `id`/`ids`, `outputFields?` | 支持 header `X-XVector-Refresh`（非 body 必填；body 可有 `refresh`） |
| R16 | `POST /entities/query` | `VectorQueryRequest` | `list[Entity]` | `filter`/`expr`, `limit`/`topk`, `outputFields?`, `partitionNames?` | |
| R17 | `POST /entities/search` | `VectorSearchRequest` | `list[list[SearchHit]]` | `data`/`vectors`, `annsField`, `limit`, `filter?`, `searchParams?`, `outputFields?`, `partitionNames?` | 外层按 query 向量分组 |
| R18 | `POST /entities/hybrid_search` | `VectorHybridSearchRequest` | `list[list[SearchHit]]` | `search[]`, `rerank?`, `limit`, `outputFields?` | 默认 RRF `k=60` |

**`SearchHit` / `Entity`**：开放字典 + 文档字段约定：`id`、PK 字段、标量/向量、`score`/`distance`（search/hybrid）。

**`VectorHybridSearchRequest` example**

```json
{
  "collectionName": "demo",
  "dbName": "default",
  "search": [
    {"data": [[0.1, 0.2, 0.3, 0.4]], "annsField": "vector", "limit": 10}
  ],
  "rerank": {"strategy": "rrf", "params": {"k": 60}},
  "limit": 10,
  "outputFields": ["id"]
}
```

### 4.7 Reader Internal（默认不进 schema）

| 路径 | Request 要点 | Response |
|------|--------------|----------|
| `POST /internal/open` | `dbName`, `collectionName`, `partitionNames?` | `{ok:true}` |
| `POST /internal/close` | 同上 + `fence?` | `{ok:true}` |
| `POST /internal/unfence` | 同上 | `{ok:true}` |
| `POST /internal/reload` | 可空 | `{ok:true}` / `{ok:false,error}` |

---

## 5. 共享 model / 复用策略

```text
xvector/common/models/
  __init__.py          # 导出常用类型
  envelope.py          # ApiResponse[T], ErrorResponse, EmptyObject, EmptyRequest
  common.py            # DbScoped, CollectionName, PartitionName, HasData, RowCountData, LoadStateData
  database.py
  alias.py
  collection.py        # SchemaField, CollectionSchema, Create/Describe...
  partition.py
  index.py
  import_job.py
  role.py
  user.py
  vector.py            # Insert/Upsert/Delete/Get/Query/Search/Hybrid + Entity/SearchHit
```

**复用原则**

1. **同一 Request 多路由复用**：如 `CollectionNameRequest` 用于 drop/release/describe/has/stats/load_state/list_indexes 等。
2. **Writer/Reader 共享同一模型类**（不要 W/R 各写一份）；差异仅在路由注册角色。
3. **路径别名共享 model**：`/import/*` ↔ `/jobs/import/*`；`/roles/lists` ↔ `/roles/list`；`/users/lists` ↔ `/users/list`。
4. **`data: {}` 统一 `EmptyObject`**，避免几十个空类。
5. **动态实体**用 `dict[str, Any]` 或 `Entity = dict[str, Any]` TypedAlias；不为每个业务 schema 生成代码。
6. **与 `errors.ok` 衔接**：handler 可继续 `return ok(model.model_dump())`，或直接返回 `ApiResponse` 实例；建议默认保持 `ok(...)` + `response_model` 注解，减少大爆炸重构。

---

## 6. 与现有代码差距

| 状态 | 说明 |
|------|------|
| **缺失** | 整个 `xvector/common/models/`（或 `models.py`）不存在 |
| **缺失** | routes 无 `body: BaseModel`、无 `response_model`、无 tags、无 examples |
| **缺失** | OpenAPI `components.schemas` 几乎为空（仅框架默认） |
| **已有（行为）** | services 字段契约完整；`errors.ok` / 错误码齐全 |
| **已有（调用方）** | pyxvector camelCase payload；e2e + performance_testing 覆盖主路径 |
| **已有（文档设计）** | `DESIGN-api-docs-and-logging.md` 规定 Gateway 注入 `requestId`；模型 docs 需兼容 |
| **需改签名（实现阶段）** | `routes.py` 各 handler：`Request` JSON → Pydantic body；增加 `response_model` |
| **建议小改（实现阶段）** | `RoleService.describe` 输出 privileges 转 camelCase（或在 API 层转换） |
| **建议保持** | `UserService.create` 返回 `username` 键（与 pyxvector 无强依赖字段名，但 e2e 可能宽松） |
| **不支持（文档如实）** | Milvus Quick Setup（仅 `dimension`）——`parse_milvus_schema` 要求 `schema.fields` |
| **类型特例** | `indexes/describe` 的 `data` 为 **array**；`search`/`hybrid_search` 为 **array of array**；list 类多为 `string[]` |
| **壳文件** | `api/v2/collection.py` 等仅为占位注释，真实路由在 `routes.py`——实现时可逐步拆分或继续集中 |

---

## 7. 建议实现顺序与涉及文件

### 7.1 顺序

1. **envelope + common**：`ApiResponse`、`ErrorResponse`、`EmptyObject`、公共 scoped request。
2. **Database / Alias / Collection（读+写）**：字段多、被其它资源依赖（schema）。
3. **Partition / Index**。
4. **User / Role**（可顺带 privilege camelCase 映射）。
5. **Vector**（insert/upsert/delete/get/query/search/hybrid）+ examples。
6. **Import** + 路径别名绑定同一 model。
7. **改造 `routes.py`**：逐组替换为声明式 body/`response_model`；补 tags。
8. **回归**：现有 e2e + 抽查 Gateway `/docs` schema 与 Try it out example。
9. （可选）拆分 `routes.py` 到 `api/v2/*.py` 实路由——非必须。

### 7.2 涉及文件

| 文件 | 改动 |
|------|------|
| `docs/DESIGN-api-models.md` | 本说明书（已落盘） |
| `xvector/common/models/**` | **新增** 全部 model + examples |
| `xvector/api/v2/routes.py` | 绑定 request/response model |
| `xvector/services/role.py` 或 API 适配层 | （建议）privilege 响应 camelCase |
| `xvector/common/errors.py` | 通常不改；必要时补充类型别名 |
| `tests/e2e/**`、`tests/unit/**` | 增补 model 单测 / OpenAPI schema 冒烟（实现阶段） |
| `pyxvector/**` | 确保 JSON payload 严格 camelCase；示例/文档对齐 |
| `tests/**` | 请求/断言改为 camelCase（含 schema.`dataType`/`isPrimaryKey`） |

---

## 8. 覆盖范围摘要（计数）

| 分类 | 逻辑 API 数 | 说明 |
|------|-------------|------|
| Writer 业务 | **35** | Database2 + Alias3 + Collection5 + Partition4 + Index2 + Import3 + Role6 + User7 + Vector3 |
| Reader 业务 | **18** | Database2 + Alias2 + Collection5 + Partition3 + Index2 + Vector4 |
| 路径别名（不另计 model） | Import×2 路径、Role lists、User lists | 共用 model |
| Writer/Reader Internal | 5 | 默认不进对外 OpenAPI |
| Gateway System（非本文件实现重点） | healthz/readyz/heartbeat/auth/openapi.refresh | 外壳仍遵循 `requestId` 约定 |
| **合计（本设计强制覆盖）** | **53** | Writer35 + Reader18 |

对照 TODO 资源：Alias / Collection / Import / Index / Partition / Role / User / Vector **均已覆盖**；Database 为代码已有扩展，一并覆盖。

---

## 9. 自检清单与结果

| # | 检查项 | 结果 | 说明 |
|---|--------|------|------|
| 1 | 路径覆盖：`routes.py` Writer/Reader 业务路由均有对应 Request/Response 设计 | ✅ | 见 §3 / §4 编号表 |
| 2 | 路径覆盖：`router_table.ROUTE_TABLE` 与设计角色一致 | ✅ | W/R 归属与表一致；Import/Role/User 别名已标注 |
| 3 | TODO 八大资源 API 动作齐全 | ✅ | 另含 Database |
| 4 | 读写角色归属正确 | ✅ | Role/User/Import 全在 Writer（含 describe/list）；读路径在 Reader |
| 5 | 字段与 services 返回值一致 | ✅ | 已逐服务核对；Role privileges 键名见待确认 Q2 |
| 6 | 与 pyxvector payload 一致 | ✅ | camelCase 主字段对齐 `pyxvector/client.py` |
| 7 | 与 e2e / perf 调用一致 | ✅ | `milvus_schema` / insertCount / search body 等已对照 |
| 8 | `requestId` 兼容 Gateway 注入 | ✅ | envelope 可选字段；W/R 不强制写入 |
| 9 | OpenAPI 可生成性 | ✅ | 计划用 Pydantic v2 + `response_model`；动态 Entity 用 dict |
| 10 | Example 可展示性 | ✅ | 约定 `json_schema_extra.examples` + 可选 `__example__` 同源 |
| 11 | 错误响应可文档化 | ✅ | `ErrorResponse` / `InternalErrorResponse` |
| 12 | 无业务代码冒进 | ✅ | 本阶段仅文档 |

### 自检结论

**自检通过**

说明：设计层路径、角色、字段与调用方已闭合；实现前仅有少量契约规范化选择（见 §10），**不阻塞** model 骨架落地。若 keep 时选择维持 Role privilege snake_case，则实现时 Response model 按存储字段定义即可。

---

## 10. 待确认 → 已确认

### Q1 — Request 字段别名严格度 → **仅接受 camelCase**

（设计原文选项 B；用户确认「实际意图 = 严格 camelCase」，snake_case → 422。）

### Q2 — Role `describe` privileges 字段风格 → **A**

API 响应：`objectType` / `objectName` / `privilege`（存储层可仍 snake_case，API 映射）。

---

## 11. 关键模型字段速查（实现用）

### 11.1 Envelope

```text
ApiResponse[T]     = { code:0, message:"success", data:T, requestId?:str }
ErrorResponse      = { code:int, message:str, requestId?:str }
InternalErrorResponse = ErrorResponse + { error_message:str }
EmptyObject        = { }
EmptyRequest       = { dbName?:str }  # 允许完全空 JSON
```

### 11.2 Vector 响应

```text
VectorInsertData = { insertCount:int, insertIds:list[Any] }
VectorUpsertData = { upsertCount:int, upsertIds:list[Any] }
VectorDeleteData = { deleteCount:int }
# get/query data: list[Entity]
# search/hybrid data: list[list[SearchHit]]
```

### 11.3 与 refresh 相关（Reader Vector）

非 body 契约主体，但 example/description 应注明：

- Header：`X-XVector-Refresh: true`
- 或 body：`refresh: true` / `refreshSeconds: 0`
- 实现继续走现有 `parse_refresh_flags`；**不必**为 refresh 单独拆 API

---

# ✅ 确认区

**已确认并实现**（Q1=仅接受 camelCase；Q2=A；pyxvector/tests 全面 camelCase）。
