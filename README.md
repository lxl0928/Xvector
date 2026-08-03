# Xvector

基于 [zvec](https://github.com/alibaba/zvec) 0.6.0 的向量库 HTTP 服务，API 风格对齐 **Milvus REST v2**（`/v2/vectordb/...`）。部署形态为 Docker Compose 三容器：**Gateway（鉴权+路由）/ Writer（独占写）/ Reader（只读）**。

设计契约见 [`docs/DESIGN.md`](docs/DESIGN.md)。

## 架构速览

```text
Client / pyxvector  --HTTP:19530-->  Gateway  --写/DDL--> Writer:18081
                                         |----读/Search--> Reader:18082
共享数据盘: 宿主机 ${XVECTOR_HOST_DATA_DIR:-./data} ↔ 容器 /data
```

## 快速启动

```bash
cp .env.example .env
# 编辑 XVECTOR_USERNAME / XVECTOR_PASSWORD
# 可选：改 XVECTOR_HOST_DATA_DIR（默认 ./data，bind mount 到容器 /data）

docker compose up -d --build
./scripts/wait_ready.sh http://127.0.0.1:19530/readyz
```

健康检查：

- `GET /healthz` — 存活（无需鉴权）
- `GET /readyz` — Gateway 聚合 Writer/Reader 就绪

鉴权：`Authorization: Bearer ${USERNAME}:${PASSWORD}`（密码中的 `:` 仅按第一个冒号分割）。

### 管理控制台（xvector_web）

Compose 会额外启动 Web 控制台（Nginx 静态站 + `/api` 反代 Gateway）：

- 登录页：`http://127.0.0.1:19531/login`
- 设计说明：[`docs/DESIGN-xvector-web.md`](docs/DESIGN-xvector-web.md)
- 前端目录：[`xvector_web/`](xvector_web/)

## 环境变量（常用）

| 变量 | 默认 | 说明 |
|------|------|------|
| `XVECTOR_USERNAME` / `XVECTOR_PASSWORD` | `root` / `Xvector` | 引导管理员（支持 env 热更新覆盖校验） |
| `XVECTOR_DATA_DIR` | `/data` | 容器内共享数据根 |
| `XVECTOR_HOST_DATA_DIR` | `./data` | 宿主机数据目录（compose bind mount 到 `/data`） |
| `XVECTOR_HTTP_PORT` | `19530` | Gateway 端口 |
| `XVECTOR_AUTO_LOAD` | `false` | `true` 时未 Load 可懒打开 |
| `XVECTOR_READER_REFRESH_SECONDS` | `10` | Reader 定时 reopen |
| `XVECTOR_INTERNAL_TOKEN` | 空 | 内网转发可选令牌 |

完整列表见 DESIGN §11。

## pyxvector 客户端示例

```bash
pip install -r requirements-client.txt
# 或把仓库根目录加入 PYTHONPATH
```

```python
from pyxvector import XvectorClient

client = XvectorClient(uri="http://127.0.0.1:19530", token="root:Xvector")
client.create_collection(
    "demo",
    schema={
        "fields": [
            {"name": "id", "dataType": "Int64", "isPrimaryKey": True},
            {"name": "vector", "dataType": "FloatVector", "dim": 4},
        ]
    },
)
client.create_index("demo", "vector", index_type="FLAT", metric_type="L2")
client.load_collection("demo")
client.insert("demo", [{"id": 1, "vector": [0.1, 0.2, 0.3, 0.4]}])
# 写后读：带 refresh 立即可见（否则最多约 N=10s）
hits = client.search("demo", [[0.1, 0.2, 0.3, 0.4]], anns_field="vector", limit=3, refresh=True)
print(hits)
client.drop_collection("demo")
client.close()
```

## 测试

```bash
# 集群需已 compose up
pip install -r requirements.txt   # 含 pytest；zvec 在镜像内安装
pytest tests/unit -v              # 不依赖 Docker
pytest tests/e2e -v --timeout=120 # 打 Gateway:19530
```

说明：

- DiskANN 用例在非 Linux 上自动 skip（以 Docker/Linux 为准）。
- Import E2E 需要 Writer 能读到 `/data/imports/...`；数据已 bind mount 到宿主机 `./data`（或 `XVECTOR_HOST_DATA_DIR`），可直接往该目录放导入文件。
- 读侧最终一致：E2E 默认使用 Header `X-XVector-Refresh: true`。

## 本地开发（单角色）

```bash
export XVECTOR_DATA_DIR=./.data
export XVECTOR_USERNAME=root XVECTOR_PASSWORD=Xvector
export XVECTOR_ROLE=writer XVECTOR_WRITER_PORT=18081
python -m xvector --role writer
```

Gateway / Reader 同理（需先装好 `zvec==0.6.0`，Python 3.10–3.12）。

## 与官方 Milvus 的主要差异

1. **最终一致读**（默认 ≤10s），非 Strong/Session；可用 `X-XVector-Refresh` 强制刷新。
2. **Privilege 仅持久化，不拦截**业务 API。
3. Import 首版仅 **JSON/JSONL**；Partition 为混合目录策略。
4. 不支持 gRPC / pymilvus 原生协议。
5. DiskANN 仅保证 Linux/Docker。

更多见 DESIGN §16。

## 仓库结构

- `xvector/` — 服务端共享库（gateway / writer / reader）
  - `api/` — FastAPI 应用入口与健康检查
  - `gateway/` — 鉴权与读写路由代理
  - `services/` — Collection / Vector / Index 等业务逻辑
  - `engine/` — zvec 打开/关闭、WAL seal、分区句柄
  - `meta/` — Catalog 元数据与快照
  - `common/` — 请求/响应模型、路径与错误类型
- `xvector_web/` — Vue 管理控制台（Compose 端口 19531）
- `pyxvector/` — 薄 HTTP 客户端
- `tests/`
  - `unit/` — 不依赖 Docker 的单元测试
  - `e2e/` — Compose 真集群 E2E
  - `performance_testing/` — 压测与吞吐脚本
- `docs/` — 设计文档（`DESIGN.md` 为实现权威）
- `scripts/` — 就绪等待等运维脚本
- `docker-compose.yaml` / `Dockerfile` — 三角色 + Web 部署
- `data/` — 默认宿主机数据目录（bind mount → 容器 `/data`）
