# Xvector Locust 性能测试设计说明书

> **状态**：已确认需求，**已实现**（见同目录 README / locustfile_* / common/）  
> **约束**：技术决策以本文为准；实现阶段可小幅补充状态，不改已确认参数与规则。

---

## 1. 背景与目标

Xvector 需要一套可重复、可观测的 HTTP 网关层性能测试方案，用于评估向量库在典型读写负载下的吞吐与延迟表现，并按阶梯加压自动判定性能拐点。

**目标：**

1. 覆盖三种业务场景：仅写、仅读、读写混合。
2. 压测前底库规模统一 ≥ 1,000,000，保证检索类场景具备可比性。
3. 采用阶梯加压（规则 C），以读写 mean 延迟 200ms 为停止阈值，定位有效并发上限。
4. 通过 pytest 完成环境检查与数据准备，通过 Locust Web UI 启动压测，阶梯控制与报告产出在 Locust 内自动完成。

---

## 2. 范围与非目标

### 2.1 范围

- 基于 Gateway HTTP API（`/v2/vectordb/...`）的 Locust 压测。
- 数据准备：创建 collection、创建 HNSW 索引、灌库、load、规模校验。
- 三场景压测脚本与公共模块。
- 每场景产出 Locust HTML 报告 + 阶梯摘要 JSON。
- pytest 侧：服务可用性检查、建库/灌数/load（可复用）、打印 Locust 启动命令后结束。

### 2.2 非目标

- 不进入常规 CI 门禁。
- 不强制压测请求携带 `X-XVector-Refresh`。
- 不覆盖除 insert / search / get / query 以外的其它 API。
- 不做多节点分布式压测编排（单机 Locust Web 即可）。

---

## 3. 数据模型与索引

### 3.1 Schema

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | Int64 | 主键（PK） |
| `timestamp` | Int64 | 时间戳（毫秒） |
| `vector` | FloatVector | 维度 **1024** |

### 3.2 索引与检索参数

| 项 | 值 |
|----|-----|
| 索引类型 | HNSW |
| M | 16 |
| efConstruction | 200 |
| metric | L2 |
| search TOPN（limit） | 20 |
| search ef | 64 |
| annsField | `vector` |

### 3.3 规模与 batch

| 项 | 值 |
|----|-----|
| 三场景压测前底库 | 均 ≥ **1,000,000** |
| 灌库准备 batch | **200** |
| 压测写 batch | **50** |

### 3.4 Gateway 与鉴权

| 项 | 默认值 | 说明 |
|----|--------|------|
| Gateway | `http://127.0.0.1:19530` | 可用环境变量覆盖 |
| Auth | `Authorization: Bearer root:Xvector` | 可用环境变量覆盖 |

### 3.5 数据准备流程

压测前统一执行（可复用同名 collection，支持断点续灌）：

1. `create collection`
2. `create HNSW index`
3. 灌数（batch=200）直至 ≥ 1,000,000
4. `load`
5. 校验规模 ≥ 1,000,000

---

## 4. 压测场景定义

### 4.1 场景一：单独写（仅 insert）

- **流量**：100% insert
- **请求形态**：每批 50 条；`id` 递增；`timestamp=now_ms`；1024 维随机/构造向量
- **刷新**：不强制 `X-XVector-Refresh`

### 4.2 场景二：单独读

读操作内部权重固定为：

| 接口 | 权重 |
|------|------|
| search | **80%** |
| get | **1%** |
| query | **19%** |

即 **search : get : query = 80 : 1 : 19**。

**请求形态：**

- **search**：`limit=20`，`ef=64`，`annsField=vector`
- **get**：使用已存在的 PK；比重 1%
- **query**：如 `timestamp > 0` + `limit`；比重 19%

### 4.3 场景三：读写混合

| 维度 | 比例 |
|------|------|
| 写 : 读 | **20 : 80** |
| 读内部 | 仍为 search:get:query = **80:1:19** |

写侧仍为 insert（batch=50）；读侧形态同场景二。

### 4.4 场景与脚本对应（实现阶段）

| 场景 | Locust 入口文件（规划） |
|------|-------------------------|
| 仅 insert | `locustfile_write.py` |
| 仅读 | `locustfile_read.py` |
| 读写混合 | `locustfile_mixed.py` |

---

## 5. 加压与停止策略（规则 C）

### 5.1 参数

| 参数 | 值 |
|------|-----|
| `start_users` | 1 |
| 每阶增量 `Δ` | 5 |
| 每阶时长 `T` | 20s |
| `max_users` | 100 |

### 5.2 阶梯序列

```
1 → 6 → 11 → 16 → … → ≤ 100
```

通项：`users = 1 + k·5`，`k = 0, 1, 2, …`，且 `users ≤ 100`。

### 5.3 每阶判定

- 每阶持续 **20s**。
- 该阶时间窗内：
  - **写 mean**：insert 的 mean 延迟
  - **读 mean**：search / get / query 的 **overall read mean**（该阶内三类读请求合计）
- **停止条件**：该阶写 mean **或** 读 mean **任一** > **200ms** → 立即结束压测。
- **有效结果**：取 **上一阶**（未超阈值的最后一阶）作为有效并发结论。
- **未触达上限**：若打到 `max_users` 仍未超过 200ms 阈值 → 正常结束，报告须标明「未触达延迟上限」。

### 5.4 判定口径补充

- 阶梯判定使用 **该阶时间窗 mean**，而非全量累计 mean。
- 仅写场景：主要观察写 mean；读 mean 无样本时可忽略读侧阈值。
- 仅读场景：主要观察读 mean；写 mean 无样本时可忽略写侧阈值。
- 混合场景：写 mean、读 mean 任一超阈值即停。

---

## 6. 目录与模块划分

> 本次仅创建 `DESIGN.md`；下列其余路径为规划，实现阶段再建。

```
tests/performance_testing/
  DESIGN.md                 # 本说明书（已创建）
  README.md                 # 使用说明（待实现）
  conftest.py               # pytest fixture：服务检查、建库/灌数/load（待实现）
  test_*.py                 # pytest：准备完成后打印 locust 命令并结束（待实现）
  locustfile_write.py       # 仅写场景（待实现）
  locustfile_read.py        # 仅读场景（待实现）
  locustfile_mixed.py       # 读写混合场景（待实现）
  common/                   # 公共：鉴权、向量生成、阶梯控制器、报告写入等（待实现）
  reports/                  # 报告输出目录（待实现）
```

### 6.1 模块职责（规划）

| 模块 | 职责 |
|------|------|
| `conftest.py` / `test_*.py` | 检查服务 → 建库/灌数/load（可复用）→ 打印 Locust 命令 → 结束 |
| `common/` | HTTP 客户端封装、Schema/索引常量、ID 生成、阶梯加压与 200ms 判定、报告摘要 |
| `locustfile_*.py` | 场景任务权重、启动 Locust Web、挂载阶梯控制器 |
| `reports/` | 存放每场景 Locust HTML + 阶梯摘要 JSON |

---

## 7. 运行与观测流程（方案 B）

### 7.1 总体流程

```
pytest（准备）                用户手动                  Locust 内部自动
───────────────              ──────────                ────────────────
检查服务可用
  → create / index / 灌库
    / load / 校验 ≥100万
  → 打印 locust 命令
  → pytest 结束
                              复制命令启动 Locust
                              浏览器打开
                              http://localhost:8089
                              点击 Start
                                                        阶梯加 users
                                                        每阶 20s 判定 mean
                                                        >200ms 停测
                                                        写 HTML + JSON 报告
```

### 7.2 pytest 职责（方案 B）

1. 检查 Gateway 服务可用。
2. 建库 / 灌数 / load（支持同名 collection 断点复用）。
3. 打印对应场景的 `locust` 启动命令后结束。
4. **不**在 pytest 内直接跑完整压测闭环。

### 7.3 Locust 启动示例

Web 端口默认 **8089**。

```bash
locust -f tests/performance_testing/locustfile_read.py \
  --host http://127.0.0.1:19530 --web-host 0.0.0.0 --web-port 8089
```

写场景、混合场景将 `locustfile_read.py` 替换为对应文件即可；`--host` 等可用环境变量覆盖默认 Gateway。

### 7.4 Locust 内控制器

- 用户在 Web UI 点击 Start 后，阶梯控制器自动：
  - 按 `1 → 6 → 11 → … → ≤100` 增加 users
  - 每阶 20s 统计该阶写/读 mean
  - 任一 mean > 200ms 则停止
  - 写出报告（含是否触达延迟上限）

---

## 8. 报告产出

每场景产出两类产物，写入 `reports/`（实现阶段约定命名）：

| 产物 | 内容 |
|------|------|
| Locust HTML | Locust 标准 HTML 报告 |
| 阶梯摘要 JSON | 各阶 users、时长、写 mean、读 mean、停止原因、有效阶、是否未触达延迟上限等 |

### 8.1 报告明细要求

- 含 **分接口明细**（insert / search / get / query），因 get 仅 1%，需单独可见以免被 overall 掩盖。
- 阶梯摘要须标明：
  - 停止原因（超阈值 / 达到 max_users）
  - 有效结果阶（上一阶）或「未触达延迟上限」

---

## 9. 依赖与约束

| 项 | 说明 |
|----|------|
| 依赖 | 增加 **locust** 依赖（实现阶段写入项目依赖清单） |
| CI | 压测 **不进** 常规 CI 门禁 |
| 鉴权 | `Authorization: Bearer root:Xvector`（可环境变量覆盖） |
| Refresh | 压测 **不强制** `X-XVector-Refresh` |
| 复用 | 灌库耗时长，支持断点复用同名 collection |
| Web | Locust Web 默认端口 8089 |

### 9.1 API 参考（来自代码库）

| 操作 | 方法与路径 |
|------|------------|
| 创建集合 | `POST /v2/vectordb/collections/create` |
| 创建索引 | `POST /v2/vectordb/indexes/create` |
| Load | `POST /v2/vectordb/collections/load` |
| Insert | `POST /v2/vectordb/entities/insert` |
| Search | `POST /v2/vectordb/entities/search` |
| Get | `POST /v2/vectordb/entities/get` |
| Query | `POST /v2/vectordb/entities/query` |

**Auth：** `Authorization: Bearer root:Xvector`

---

## 10. 风险与边界

| 风险 / 边界 | 说明与应对 |
|-------------|------------|
| 灌库耗时长 | 支持断点复用同名 collection，避免重复全量灌数 |
| get 样本偏少 | 权重仅 1%；报告必须含分接口明细，避免统计不稳定被忽略 |
| 阶梯 mean 口径 | 严格使用该阶时间窗 mean，避免全量均值稀释拐点 |
| 仅写 / 仅读判定 | 无对应样本的一侧不参与 200ms 停止判定 |
| 服务未就绪 | pytest 准备阶段先检查服务，失败则不打印压测命令 |
| 不进 CI | 避免长耗时灌库与人工 Web 启动阻塞流水线 |
| max_users 未触顶 | 报告明确标注「未触达延迟上限」，避免误读为已找到拐点 |
| 单机 Locust | 本方案不保证压测机本身不是瓶颈；必要时需单独扩容压测端 |

---

## 11. 实现清单

1. [x] 增加 `locust` 依赖（不接入常规 CI 门禁）
2. [x] 编写 `README.md`（准备、三场景启动、报告位置）
3. [x] 实现 `common/`：鉴权与环境变量、向量/ID 生成、HTTP 封装、阶梯控制器（规则 C）、报告写入
4. [x] 实现 `conftest.py` / `test_*.py`：服务检查 → create → index → 灌数(batch=200) → load → 校验 ≥100万 → 打印 locust 命令
5. [x] 实现 `locustfile_write.py`（仅 insert，batch=50）
6. [x] 实现 `locustfile_read.py`（search:get:query = 80:1:19）
7. [x] 实现 `locustfile_mixed.py`（写:读 = 20:80；读内部 80:1:19）
8. [x] 报告：每场景 Locust HTML + 阶梯摘要 JSON（含分接口明细与是否触达延迟上限）
9. [ ] 手工验收：三场景各跑通一轮阶梯加压与停止逻辑

---

## 附录 A：已确认决策速查

| 决策项 | 已确认内容 |
|--------|------------|
| 场景 | 仅写；仅读 80:1:19；混合写:读=20:80（读内仍 80:1:19） |
| 维度 / 索引 | 1024；HNSW M=16 efConstruction=200 L2；search TOPN=20 ef=64 |
| 底库 | ≥ 1,000,000；灌库 batch=200；压测写 batch=50 |
| Refresh | 不强制 |
| Gateway | `http://127.0.0.1:19530`，Bearer `root:Xvector`（可环境变量覆盖） |
| 加压规则 | 规则 C：start=1，Δ=5，T=20s，max=100；任一 mean>200ms 停，有效取上一阶 |
| 运行方式 | 方案 B：pytest 准备并打印命令；用户手动 Locust Web；控制器内置 |
| 报告 | Locust HTML + 阶梯摘要 JSON |
| CI | 不进常规门禁 |
