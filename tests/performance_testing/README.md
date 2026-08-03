# Xvector Locust 性能测试

基于 Gateway HTTP API 的阶梯加压性能测试（方案 B）。设计说明见同目录 [`DESIGN.md`](./DESIGN.md)。

## 场景

| 场景 | Locust 文件 | 流量 |
|------|-------------|------|
| 仅写 | `locustfile_write.py` | 100% insert（batch=50） |
| 仅读 | `locustfile_read.py` | search:get:query = 80:1:19 |
| 读写混合 | `locustfile_mixed.py` | 写:读 = 20:80（读内部仍 80:1:19） |

压测前底库统一 ≥ **1,000,000**（可复用同名 collection，支持断点续灌）。

## 依赖

```bash
pip install -r requirements.txt
# 或单独：pip install 'locust>=2.20,<3'
```

本目录用例带 `@pytest.mark.performance`，**默认 pytest / CI 会通过 `-m 'not performance'` 排除**。

## 环境变量

| 变量 | 默认 | 说明 |
|------|------|------|
| `XVECTOR_URI` / `XVECTOR_PERF_HOST` | `http://127.0.0.1:19530` | Gateway |
| `XVECTOR_USERNAME` / `XVECTOR_PASSWORD` | `root` / `Xvector` | 拼成 Bearer token |
| `XVECTOR_TOKEN` | `root:Xvector` | 若设置则优先 |
| `XVECTOR_PERF_COLLECTION` | `perf_hnsw_1024` | 可复用的压测 collection |
| `XVECTOR_PERF_TARGET_ROWS` | `1000000` | 底库目标行数；本地冒烟可临时调小 |
| `XVECTOR_PERF_NEXT_ID` | （prepare 打印） | 写流量起始 id |
| `XVECTOR_PERF_MAX_ID` | （prepare 打印） | get/search 所用已有 PK 上界 |
| `XVECTOR_PERF_WEB_PORT` | `8089` | Locust Web 端口 |

鉴权头：`Authorization: Bearer ${USER}:${PASS}`。压测**不**强制 `X-XVector-Refresh`。

## 三步运行

### 1. 启动服务

```bash
docker compose up -d --build
# 等待 Gateway ready（默认 :19530）
```

### 2. pytest 准备环境并打印 Locust 命令

灌 100 万较慢，支持断点续跑（同名 collection 已有数据会续灌/跳过）。

```bash
# 正式：目标 100 万（耗时长）
pytest -m performance tests/performance_testing -o addopts= -s --timeout=0

# 本地冒烟（可选，缩小底库）
XVECTOR_PERF_TARGET_ROWS=2000 pytest -m performance tests/performance_testing -o addopts= -s --timeout=0
```

成功后终端会打印类似：

```bash
export XVECTOR_PERF_NEXT_ID=1000000
export XVECTOR_PERF_MAX_ID=999999
locust -f tests/performance_testing/locustfile_read.py \
  --host http://127.0.0.1:19530 --web-host 0.0.0.0 --web-port 8089 \
  --html tests/performance_testing/reports/read.html
```

写 / 混合场景将 `locustfile_read.py` 换成对应文件即可（pytest 会对三场景各打印一条）。

### 3. 手动启动 Locust Web 并观察

在仓库根目录执行上一步打印的命令，浏览器打开 [http://localhost:8089](http://localhost:8089)，点击 **Start**。

- 阶梯由内置 `LoadTestShape` 自动控制：`1 → 6 → 11 → … → 96`（通项 `1+k·5` 且 `≤100`），每阶 20s
- 该阶写 mean **或** 读 mean 任一 **> 200ms** → 自动停止；有效结果取**上一阶**
- 打到最大并发仍未超阈值 → 正常结束，报告标注「未触达延迟上限」

## 报告

输出目录：`tests/performance_testing/reports/`

| 文件 | 内容 |
|------|------|
| `{scenario}.html` | Locust HTML（含分接口 insert/search/get/query） |
| `{scenario}_steps.json` | 各阶 users、写/读 mean、分接口明细、停止原因、有效阶、是否未触达延迟上限 |

`reports/` 下除 `.gitkeep` 外的生成物已被 gitignore。

## 数据与索引（固定）

- Schema：`id` Int64 PK，`timestamp` Int64，`vector` FloatVector **dim=1024**
- 索引：HNSW，`M=16`，`efConstruction=200`，metric=L2
- search：`TOPN=20`，`ef=64`
- 灌库 batch=200；压测写 batch=50
