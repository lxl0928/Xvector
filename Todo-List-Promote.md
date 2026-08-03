# 仓库说明

此仓库主要功能为打造基于 zvec 向量数据库的 FastAPI HTTP 服务版本，其核心功能如下：

1. 服务端底层使用 Zvec（Zvec 是一款开源的嵌入式（进程内）向量数据库 — 轻量、极速，可直接嵌入应用程序。以极简的配置提供生产级、低延迟、可扩展的向量检索能力。）作为向量数据库，版本为：v0.6.0（2026 年 7 月 20 日）。

   要求支持的向量索引如下：

   - Flat（暴力检索）索引
   - HNSW（分层可导航小世界）
   - HNSW-RaBitQ（HNSW + RaBitQ 量化）
   - DiskANN（基于磁盘的近似最近邻）
   - IVF（倒排文件索引）

   相关链接：

   - 官网文档：<https://github.com/alibaba/zvec/blob/main/README_CN.md>
   - Python API：<https://zvec.org/api-reference/python/config/#zvec.init(jieba_dict_dir)>

2. API 层使用 FastAPI（FastAPI is a modern, fast (high-performance), web framework for building APIs with Python based on standard Python type hints.）作为 HTTP API 框架，版本为：0.141.1。

   - FastAPI 官网文档：<https://github.com/fastapi/fastapi/blob/master/README.md>
   - 要求：API 层设计完全参考 Milvus 的 HTTP API（v2 版本）
   - 鉴权：HTTP Header `Authorization: Bearer ${TOKEN}`，其中 TOKEN 为：`USERNAME:PASSWORD`（来源于服务的环境变量）

3. 基于 zvec 向量数据库的 FastAPI HTTP 服务版本的 HTTP API 设计与实现，要完全参考 Milvus 的 HTTP API（v2 版本）格式，Milvus API v2 版本的官网链接如下：<https://milvus.io/api-reference/restful/v2.4.x/About.md>

   - Alias (v2)
     - Alter
     - Create
     - Describe
     - Drop
     - List

   - Collection (v2)
     - Create
     - Describe
     - Drop
     - Get Load State
     - Get Stats
     - Has
     - List
     - Load
     - Release
     - Rename

   - Import (v2)
     - Create
     - Get Progress
     - List

   - Index (v2)
     - Create
     - Describe
     - Drop
     - List

   - Partition (v2)
     - Create
     - Drop
     - Get Statistics
     - Has
     - List
     - Load
     - Release

   - Role (v2)
     - Create
     - Describe
     - Drop
     - Grant Privilege
     - List
     - Revoke Privilege

   - User (v2)
     - Create
     - Describe
     - Drop
     - Grant Role
     - List
     - Revoke Role
     - Update Password

   - Vector (v2)
     - Delete
     - Get
     - Hybrid Search
     - Insert
     - Query
     - Search
     - Upsert

4. HTTP 服务部署形式为 Docker，要求仓库包含 `Dockerfile`、`docker-compose.yaml` 等文件，支持健康检查接口，且支持挂载容器所在宿主机的磁盘，作为共享盘，并对容器所使用的 CPU 核心数、内存做严格的限制。

5. 需独立实现 `pyxvector` 模块，作为 zvec 向量数据库的 FastAPI HTTP 服务版本的 Python HTTP 客户端。

6. 仓库需完整包括所有依赖模块的 `requirements.txt`，在上述步骤完成后，需要编写独立的 pytest 模块，进行相应的 API 测试。

# 性能测试

说明：在 `tests` 目录下，单独生成性能测试目录 `performance_testing`，使用 Python locust 模块，进行性能测试，性能测试要求：

1. xvector 单独写性能测试。
2. xvector 单独读性能测试。
3. xvector 写、读同时性能测试。
4. 以上性能测试项，性能测试结束标志为：读或者写接口平均响应延迟超过 200ms 时，结束当前性能测试。
5. 以上性能测试特征向量维度为 1024 维度，索引使用 HNSW 索引，标量字段为 id、timestamp（表示向量写入时间），向量字段为 vector。
6. 以上性能测试的报告单独输出到该测试目录下。
7. 运行单元测试过程中，拉起 locust web，让我可观察整个性能测试过程。
8. 你需要充分理解上述性能测试的需求，并遵循如下原则：

   1. 不要直接写代码，请先完成相应 TODO 项的思考和步骤、边界拆解，有不确定的地方，抛出不确定的问题让我确认或者补充；
   2. 你每次可以问我一个问题，用于补充 TODO 项的详细说明；
   3. TODO-List 中的任何一项，直到你有 95% 的把握完整准确无误执行后，编写设计说明书，让我确认无误后，才开始进行 coding。

# xvector api文档 及 日志优化

说明：利用 FastAPI 自身的功能，生成接口文档，要求：访问 `http://{xvector api host}:19530/docs` 时，能完整看到 xvector api 的所有文档，包括但不限于探活、认证、状态检测、writer 下所有 api、reader 下所有 api，且需补充完整调用链的 trace_id。

要求：

1. gateway、writer、reader 的 docker container 日志输出，要补充完整的 trace_id，trace_id 来源于 gateway 层收到请求后进行初始化，初始化的 trace_id，需完整带入到请求 writer 或者 reader 的请求头中。
2. 要求 trace_id 具有完整的调用链，并在 docker container console log 中输出。
3. gateway 层、reader 层、writer 层，在现有结束请求日志 `127.0.0.1:52486 {trace_id} "GET /healthz HTTP/1.1" 200 OK` 基础上，在收到请求时，打印：`127.0.0.1:52486 {trace_id} "GET /healthz HTTP/1.1" Start...`，注意日志中还需要补充时间。
4. 每个 api 请求完成后，在 response.body 中，补充 `requestId: {trace id}`。
5. 按说明在 `http://{xvector api host}:19530/docs` 处，补充完整 xvector api 的接口文档，及文档使用、api 调用方式的说明。
6. 你需要充分理解上述接口文档及日志优化的需求，并遵循如下原则：

   1. 不要直接写代码，请先完成相应 TODO 项的思考和步骤、边界拆解，有不确定的地方，抛出不确定的问题让我确认或者补充；
   2. 你每次可以问我一个问题，用于补充 TODO 项的详细说明；
   3. TODO-List 中的任何一项，你都可以提问，提问的方式最好是 A、B、C、D 多种备选项的方式，让我确认选哪一个或者补充说明，直到你有 95% 的把握完整准确无误执行后，你编写设计说明书文档落盘，让我确认无误 keep 后，才开始按设计说明书，逐项进行 coding。

# xvector dashboard web

说明：利用 Vue 3 前端框架 + Ant Design UI 组件库作为前端 web 技术，参考 Milvus attu，代码仓库：<https://github.com/zilliztech/attu>，实现 xvector 的管理 web 的功能。

前端模块：在仓库根目录下，新增：`xvector_web`，表示前端部分。

功能如下：

1. 登录页，使用 `USERNAME:PASSWORD` 来登录；
2. 登录后，默认跳转到当前 USERNAME 的数据库列表页：

   - 列表页上方，展示当前向量数据库的状态，数据来源于 `/healthz`、`/readyz` 接口
   - 当前 USERNAME 下的向量数据库列表（默认至少有 `_default` 库）
   - 当前 USERNAME 下的向量数据库新增、删除、更新、详情

3. 点击某个数据库详情，进入某个数据库的 collection 管理页：

   - collection 列表、详情、删除、更新、新增

4. 点击某个 collection 详情，可以查看 collection 的 schema 定义，可以进行向量 search，可以查看当前 collection 的具体数据列表，应支持分页。
5. 页面所有接口均尽可能使用 writer、reader、gateway 提供的原生接口，尽量不再定义新的 dashboard 业务接口。
6. 注意，完成所有 coding 后，你需要更新 `Dockerfile`、`docker-compose` 文件，以便 `xvector_web` 以独立 web 服务的方式，在 19531 端口启动，并可通过：`http://{xvector api host}:19531/login` 访问登录页。
7. 你需要充分理解上述说明、功能需求，并遵循如下原则：

   1. 不要直接写代码，请先充分理解，完成相应 TODO 项的思考和步骤、边界拆解，有不确定的地方，抛出不确定的问题让我确认或者补充；
   2. 你每次可以问我一个问题，用于补充 TODO 项的详细说明；
   3. TODO-List 中的任何一项，你都可以提问，提问的方式最好是 A、B、C、D 多种备选项的方式，让我确认选哪一个或者让我补充说明直到你有 95% 的把握完整准确无误执行当前项后，你再进行设计说明书文档编写并落盘，最后，需要让我确认文档无误 keep 后，你才能开始按设计说明书文档，逐项进行 coding。
