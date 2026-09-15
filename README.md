# 自动化数据分析 Agent

基于 FastAPI、Pydantic v2 与 Docker 沙箱的 Code Interpreter 系统，按阶段实现。

## 当前进度

| 阶段 | 状态 |
| --- | --- |
| Phase 0：基础设施、执行沙箱 | 代码与单测完成；本机缺少 Docker，真实容器测试交由 CI 验证 |
| Phase 1：文件上传、Schema / 数据概要 | 已实现，包含真实解析接口测试 |
| Phase 2：LLM 状态机、自愈 | 待实现 |
| Phase 3：SSE、Redis 会话与缓存 | 待实现 |
| Phase 4：Next.js 看板 | 待实现，Compose 中仅为占位服务 |
| Phase 5：示例、部署脚本、完整交付 | 待实现 |

当前为本机/单租户开发阶段，没有登录鉴权、租户隔离或数据保留策略，尚未达到生产上线验收条件。Redis 已在 Compose 中配置，但应用尚未接入。

## 本地启动（Python 3.11+）

```sh
python3.11 -m venv .venv
.venv/bin/python -m pip install -r backend/requirements-dev.txt
PYTHONPATH=backend .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

交互接口文档：[Swagger UI](http://127.0.0.1:8000/docs)。文件解析不依赖 Docker 或 LLM 密钥；运行生成的 Python 代码必须使用 Docker。

```sh
curl -f http://127.0.0.1:8000/healthz
curl -f -F 'file=@/absolute/path/sales.csv' http://127.0.0.1:8000/api/v1/datasets
curl -f http://127.0.0.1:8000/api/v1/datasets/DATASET_UUID
```

`POST /api/v1/datasets` 返回 dataset_id、原始文件 SHA-256、总行列数、列名、推断类型、每列缺失数量/比例、前 5 行预览和解析提示。`GET /api/v1/datasets/{dataset_id}` 可在服务重启后读取同一概要。

支持 UTF-8/BOM CSV、XLSX、XLS、Parquet。Excel 默认只读取第一张工作表，公式仅使用文件中保存的结果，绝不执行公式。CSV 空字段及 Pandas 默认 NA 标记记作缺失值；不自动猜测文本日期。重复/空列名直接拒绝，避免静默改名影响后续代码生成。

## 解析资源与存储

- 默认上传上限 20 MiB、100,000 行、200 列、解码后 DataFrame 上限 128 MiB；超限直接拒绝，不以抽样冒充全量概要。
- ASGI 中间件按实际请求字节计数，支持无 Content-Length 请求；为 multipart 元数据另预留 64 KiB。文件大小另行校验。
- 文件解析在独立、可终止的子进程中进行，默认 30 秒墙钟超时；每个 API 进程最多 2 个解析任务。Linux 额外限制解析进程 2 GiB 虚拟地址空间及 30 秒 CPU，macOS 不保证地址空间限制。此进程只运行固定解析器，不运行 LLM 代码。
- XLSX 展开总大小限制 100 MiB；Parquet 检查元数据中的行数及解码大小。成功结果保存为规范化 Parquet 和 JSON 概要；源文件与失败暂存文件会清理。
- 文件存储在 `DATASET_DIR`（默认 `uploads/`）下，由服务器生成 UUID 目录；上传文件名仅用于展示。整个目录被 Git 忽略。
- 预览单元格字符串最多 256 字符，非有限数值在 JSON 预览中为 null；规范化数据仍保留原始值。
- `build_dataset_context()` 只传 Schema 和最多 5 行样例，默认最多 12,000 字符，截断时明确记录遗漏列数。字符上限不是精确 Token 计数；接入具体模型后还需按模型上下文窗口约束。Phase 2 将接入此构造器。

## Docker 沙箱

```sh
docker compose config --quiet
docker compose up --build backend redis sandbox-executor
```

沙箱按执行请求创建独立容器：禁网、非 root、只读根文件系统、丢弃 Linux capabilities、禁止权限提升、512 MiB 内存且禁用额外 swap、1 CPU、64 PID、默认 10 秒超时。脚本通过 Python 参数执行，FastAPI 进程不使用 `exec` / `eval`。stdout/stderr 分别返回，每路最多保留 256 KiB，并限制 Docker 日志轮转大小。OOM、非零退出与超时返回不同状态。

Compose 的 Docker socket 挂载目前仅是开发配置。后端非 root 用户需要部署者提供正确的 socket 组权限（例如通过 Compose override 的 `group_add`），或配置有访问权限的远程/rootless Docker Engine。Docker socket 持有者拥有很高的宿主机权限；生产环境应使用专用执行节点和受控执行服务。当前尚未实现这层隔离，也未将数据集装载到代码沙箱；后者属于 Phase 2。

## 验证

```sh
PYTHONPATH=backend .venv/bin/python -m pytest -q
.venv/bin/ruff check backend

# 真实 Docker 测试（需要已启动的 Docker Engine）：
docker build -t data-analysis-sandbox:latest sandbox-runtime
PYTHONPATH=backend RUN_DOCKER_TESTS=1 .venv/bin/python -m pytest backend/tests/test_sandbox_integration.py -q
```

未设置 `RUN_DOCKER_TESTS=1` 时明确跳过真实容器测试，不将 mock 单测当成沙箱安全验收。GitHub Actions 使用 Python 3.11，构建镜像并执行包括真实禁网、只读文件系统、超时和 OOM 在内的测试。

此仓库暂未提供 `CLAUDE.md`；提交遵循用户要求：检查测试与忽略规则、明确暂存源文件、Conventional Commit、推送当前分支。请勿提交 `.env`、上传数据、虚拟环境或临时产物。
