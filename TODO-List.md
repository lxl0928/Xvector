# 仓库说明

此仓库主要功能为打造基于zvec向量数据库的 fastapi http 服务版本 ，其核心功能如下：
    1、服务端底层使用Zvec（Zvec 是一款开源的嵌入式(进程内)向量数据库 — 轻量、极速，可直接嵌入应用程序。以极简的配置提供生产级、低延迟、可扩展的向量检索能力。）作为向量数据库，版本为：v0.6.0（2026 年 7 月 20 日）
        要求支持的向量索引如下：
            Flat（暴力检索）索引
            HNSW（分层可导航小世界）
            HNSW-RaBitQ（HNSW + RaBitQ 量化）
            DiskANN（基于磁盘的近似最近邻）
            IVF（倒排文件索引）
        
        其官网文档连接为：https://github.com/alibaba/zvec/blob/main/README_CN.md
        其Python API为：https://zvec.org/api-reference/python/config/#zvec.init(jieba_dict_dir)

    2、api层使用FastAPI（FastAPI is a modern, fast (high-performance), web framework for building APIs with Python based on standard Python type hints.）作为HTTP API框架，版本为：0.141.1
        FastAPI官网文档连接为：https://github.com/fastapi/fastapi/blob/master/README.md
        要求：API层设计完全参考Milvus的HTTP API（v2版本）
        鉴权：http header "Authorization: Bearer ${TOKEN}", 其中TOKEN为: USERNAME:PASSWORD(来源于服务的环境变量)
        
    3、基于zvec向量数据库的 fastapi http 服务版本的http API设计与实现，要完全参考Milvus的HTTP API（v2版本）格式，Milvus API v2版本的官网链接如下：https://milvus.io/api-reference/restful/v2.4.x/About.md
        Alias (v2)
            Alter
            Create
            Describe
            Drop
            List

        Collection (v2)
            Create
            Describe
            Drop
            Get Load State
            Get Stats
            Has
            List
            Load
            Release
            Rename

        Import (v2)
            Create
            Get Progress
            List

        Index (v2)
            Create
            Describe
            Drop
            Listes

        Partition (v2)
            Create
            Drop
            Get Statistics
            Has
            List
            Load
            Release

        Role (v2)
            Create
            Describe
            Drop
            Grant Privilege
            Lists
            Revoke Privilege

        User (v2)
            Create
            Describe
            Drop
            Grant Role
            Lists
            Revoke Role
            Update Password

        Vector (v2)
            Delete
            Get
            Hybrid Search
            Insert
            Query
            Search
            Upsert


    4、HTTP 服务部署形式为Docker，要求仓库包含Dockerfile、docker-compose.yaml等文件， 支持健康检查接口，且支持挂载容器所在宿主机的磁盘，作为共享盘，并对容器所使用的CPU核心数、内存做严格的限制。

    5、需独立实现pyxvector模块，作为zvec向量数据库的 fastapi http 服务版本的python http 客户端。

    6、仓库需完整包括所有依赖模块的requirements.txt，在上述步骤完成后，需要编写独立的pytest模块，进行相应的API测试。

# 性能测试

说明：在tests目录下，单独生成性能测试目录performance_testing，使用python locust模块，进行性能测试，性能测试要求：
    1、xvector单独写性能测试
    2、xvector单独读性能测试
    3、xvector写、读同时性能测试
    4、以上性能测试项，性能测试结束标志为：读或者写接口平均响应延迟超过200ms时，结束当前性能测试。
    5、以上性能测试特征向量维度为1024维度，索引使用HNSW索引，标量字段为id, timestamp(表示向量写入时间), 向量字段为vector。
    6、以上性能测试的报告单独输出到该测试目录下。
    7、运行单元测试过程中，拉起locust web，让我可观察整个性能测试过程。
    8、你需要充分理解上述性能测试的需求，并按遵循如下原则：
        a、不要直接写代码，请先完成相应TODO项的思考和步骤、边界拆解，有不确定的地方，抛出不确定的问题让我确认或者补充；

        b、你每次可以问我一个问题，用于补充TODO项的详细说明；

        c、TODO-List中的任何一项，直到你有95%的把握完整准确无误执行后，编写设计说明书，让我确认无误后，才开始进行coding。


# xvector api文档 及 日志优化
说明：利用fastapi自身的功能，生成接口文档，要求：访问：http://{xvector api host}:19530/docs时，能完整看到xvector api的所有文档，包括不限于探活、认证、状态检测、writer下所有api、reader下所有api，且需补充完整调用链的trace_id。

要求：
    1、gatway、writer、reader的docker container 日志输出，要补充完整的trace_id，trace_id来源于gateway层收到请求后进行初始化，初始化的traceid，需完整带入到请求writer或者reader的请求头中
    2、要求trace_id具有完整的调用链，并在docker container console log中输出。
    3、gatway层、reader层、writer层，在现有结束请求日志127.0.0.1:52486 {trace_id} "GET /healthz HTTP/1.1" 200 OK基础上，在收到请求时，打印: 127.0.0.1:52486 {trace_id} "GET /healthz HTTP/1.1" Start...，注意日志中还需要补充时间
    4、每个api请求完成后，在response.body中，补充 requestId: {trace id}
    5、按说明在http://{xvector api host}:19530/docs 处，补充完整xvector api的接口文档，及文档使用、api调用方式的说明
    6、你需要充分理解上述接口文档及日志优化的需求，并按遵循如下原则：
        a、不要直接写代码，请先完成相应TODO项的思考和步骤、边界拆解，有不确定的地方，抛出不确定的问题让我确认或者补充；

        b、你每次可以问我一个问题，用于补充TODO项的详细说明；

        c、TODO-List中的任何一项，你都可以提问，提问的方式最好是A、B、C、D多种备选项的方式，让我确认选哪一个或者补充说明，直到你有95%的把握完整准确无误执行后，你编写设计说明书文档落盘，让我确认无误keep后，才开始按设计说明书，逐项进行coding。


# xvector dashboard web
说明：利用vue3前端框架 + Antdesign  UI组件库作为前端web技术，参考Milvus attu，代码仓库：https://github.com/zilliztech/attu，实现xvector的管理web的功能。
前端模块：在仓库根目录下，新增：xvector_web，表示前端部分。

功能如下：
    1、登录页，使用USERNAME:PASSWORD来登录；
    2、登录后，默认跳转到当前USERNAME的数据库列表页：
        列表页上方，展示当前向量数据库的状态，数据来源于/healthz, /readyz接口
        当前USERNAME下的向量数据库列表（默认至少有_default库）
        当前USERNAME下的向量数据库新增、删除、更新、详情
    3、点击某个数据库详情，进入某个数据库的collection管理页
        collection列表、详情、删除、更新、新增
    4、点击某个collection详情，可以查看collection的schema定义，可以进行向量search，可以查看当前 
        collection的具体数据列表，应支持分页。
    5、页面所有接口均尽可能使用writer、reader、gatway提供的原生接口，尽量不再定义新的dashboard业务接口。
    6、注意，完成所有coding后，你需要更新Dockerfile、docker-compose文件，以便xvector_web以独立web服务的方式，在19531端口启动，并可通过：http://{xvector api host}:19531/login访问登录页
    6、你需要充分理解上述说明、功能需求，并按遵循如下原则：
        a、不要直接写代码，请先充分理解，完成相应TODO项的思考和步骤、边界拆解，有不确定的地方，抛出不确定的问题让我确认或者补充；

        b、你每次可以问我一个问题，用于补充TODO项的详细说明；

        c、TODO-List中的任何一项，你都可以提问，提问的方式最好是A、B、C、D多种备选项的方式，让我确认选哪一个或者让我补充说明直到你有95%的把握完整准确无误执行当前项后，你再进行设计说明书文档编写并落盘，最后，需要让我确认文档无误keep后，你才能开始按设计说明书文档，逐项进行coding。