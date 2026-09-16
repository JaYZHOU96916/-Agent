# 部署、验收与排错

本手册对应仓库自带的本机单用户 Compose 配置。后端、Redis、前端为常驻服务；`sandbox-executor` 只负责构建并验证运行镜像，退出码 0 是正常状态。分析时后端通过 Docker SDK 创建新沙箱，执行结束后移除该容器。

## 启动与配置

启动 Docker Desktop / Engine 的 Linux 容器模式，安装 Compose v2，然后在仓库运行 `./start.sh`。脚本使用自己的目录定位 Compose 和 `.env`，支持包含空格的路径。它检查配置、构建镜像、等待服务健康，并运行 `scripts/verify_stack.py`。构建时间取决于下载速度；120 秒健康等待不包括镜像构建。

首次启动创建权限为 `600` 的 `.env`。已有文件不会被覆盖或作为 shell 脚本加载；修改配置后重跑 `./start.sh` 让 Compose 重建需要更新的容器。不要仅用 `docker compose restart` 应用环境变量变更。

| 配置 | 用途 / 默认值 |
| --- | --- |
| `LLM_BASE_URL` | 兼容模型接口的基础地址，由后端追加 `/chat/completions` |
| `LLM_API_KEY`、`LLM_MODEL` | 两项都填写才启用分析；仅服务端使用 |
| `LLM_TIMEOUT_SECONDS` | 单次模型 HTTP 请求默认 60 秒 |
| `API_TOKEN` | 可选共享工作台令牌；浏览器连接设置填写同一值 |
| `DOCKER_GID` | 后端补充组；脚本在 Linux 读取宿主 socket GID，macOS Docker Desktop 使用容器内代理 socket 的组 0 |
| `DOCKER_SOCKET_PATH` | 宿主机 Docker socket，默认 `/var/run/docker.sock`；脚本可自动识别 macOS 用户目录 socket |
| `SANDBOX_IMAGE` | 默认 `data-analysis-sandbox:latest`；改值前自行准备匹配镜像 |
| `SANDBOX_TIMEOUT_SECONDS` | 默认 10 秒，不能高于 10 |
| `SANDBOX_MEMORY_LIMIT_MB` | 默认 512 MiB，不能高于 512 |
| `SANDBOX_CPU_NANO_CPUS` | 默认 1,000,000,000，即 1 CPU，上限 1 CPU |
| `REDIS_URL` | Compose 默认 `redis://redis:6379/0`；本地 Python 开发改用实际 Redis 地址 |
| `CACHE_TTL_SECONDS` | 会话及缓存默认 3600 秒，不控制磁盘数据集清理 |
| `SEMANTIC_CACHE_ENABLED`、`EMBEDDING_MODEL` | 语义缓存默认关闭；启用前配置兼容 embedding 模型，会增加模型调用 |
| `SEMANTIC_CACHE_THRESHOLD` | 向量相似度默认 0.98，另需数字一致和模型等价确认 |
| `UPLOAD_MAX_BYTES` | 默认 20 MiB；前端也有 20 MiB 固定上限 |
| `DATASET_MAX_ROWS`、`DATASET_MAX_COLUMNS` | 默认 100,000 行 / 200 列 |
| `PROFILING_TIMEOUT_SECONDS` | 固定解析子进程默认 30 秒 |
| `DATASET_DIR` | 仅本地 Python 开发路径；Compose 固定 `/app/uploads` 并绑定数据卷 |

Linux 手动启动 Compose 时可先运行 `stat -c '%g' /var/run/docker.sock`，将输出写入 `.env` 的 `DOCKER_GID`。macOS Docker Desktop 可使用默认 Docker socket；若只提供 `$HOME/.docker/run/docker.sock`，`start.sh` 会自动设置 `DOCKER_SOCKET_PATH`。Docker Desktop 的 VM 代理在容器内通常将该 socket 显示为 `root:root`，因此脚本为后端非 root 用户增加组 0；可用 `docker compose exec backend ls -l /var/run/docker.sock` 核实。仅宿主机 `docker info` 成功不足以证明后端用户有权限，因此脚本还实际执行沙箱探针。若在 macOS 主机上直接运行 Docker 集成测试，可设置 `DOCKER_HOST=unix://$HOME/.docker/run/docker.sock`。远程 Docker context/rootless 配置需要匹配的端点与挂载，不在当前脚本的自动配置范围内。

## 日常操作与数据持久化

```sh
./start.sh
docker compose ps -a
docker compose logs --tail=100 backend frontend redis
docker compose exec -T backend python - < scripts/verify_stack.py
docker compose down
```

`docker compose down` 保留 `dataset-data` 和 `redis-data` 数据卷。不要加 `--volumes` / `-v`，除非明确要永久删除上传数据和 Redis 状态。启动失败不会自动删除容器或卷，便于查看状态。重新构建镜像不等于备份数据。

规范化数据与概要存于 `dataset-data`，原始上传文件解析后清理。Redis 开启 AOF，保存有 TTL 的会话事件和缓存。当前尚未提供磁盘数据集自动保留期或删除 API，需要部署方制定清理与卷备份方案；备份时协调写入，并对恢复后的概要读取做验证。不要把 `.env` 或数据卷导出物提交仓库。

## 真实模型验收

脚本探针不调用模型。配置真实模型后，在工作台上传合成 `sales.csv` 并执行 examples/README.md 的演示步骤。核对总销售额 7,540,350、SSE 正常完成、图表可切换和导出、再次同问命中缓存；再用一份 XLSX 或 Parquet 验证入口一致性。

模型配置存在只表示两个字段非空，不代表密钥、模型名和配额有效。真实调用会将问题、概要和最多 5 行样例发送到配置的模型服务；代码执行仍在本地 Docker 内。记录模型名、测试时间及结果，日志与截图中不要包含密钥。

需要以命令行验证 SSE 时，先准备 `dataset_id`；启用共享令牌时为 API 请求设置 `X-API-Key`。例如在未启用令牌的本地环境：

```sh
curl --fail-with-body -F 'file=@examples/generated/sales.csv' \
  http://127.0.0.1:8000/api/v1/datasets
# 用上传响应中的 UUID 替换下面的 DATASET_UUID：
curl --no-buffer --fail-with-body \
  -H 'Content-Type: application/json' \
  --data '{"dataset_id":"DATASET_UUID","question":"按月汇总 revenue，画趋势图并给出全年总和"}' \
  http://127.0.0.1:8000/api/v1/analyses
```

必须看到 `event: done` 且 `status` 为 `completed`；仅 HTTP 200 不代表分析成功，流内仍可能出现最终失败。`error` 的 `recoverable: true` 表示正在修复，同一连接会继续。断线后可查询会话，但当前客户端不支持按 SSE ID 断点续传。

## 演示访问

仓库未配置公网 Demo 域名或托管服务。启动后本机可访问 `http://127.0.0.1:3000`；接口文档在 `http://127.0.0.1:8000/docs`。若在自己的远程服务器运行，可在本地终端建立 SSH 隧道：

```sh
ssh -N -L 3000:127.0.0.1:3000 your-user@your-server
```

然后访问本地 3000 端口。前端同源代理会访问服务器上的后端，无须同时公开 8000 端口。

## 常见故障

| 现象 | 处理 |
| --- | --- |
| 找不到 Docker / 无法连接 daemon | 安装并启动 Docker，确认 `docker info` 成功 |
| 不支持 `--wait-timeout` | 更新 Compose v2；脚本在构建前检测该参数 |
| Backend 启动失败或沙箱 `engine_error` | 检查 socket 存在、后端用户 GID 和沙箱镜像；查看 backend 日志 |
| Redis 健康但沙箱失败 | Redis 与执行引擎是独立依赖，仍需检查 Docker SDK 的权限 |
| API 401 | 浏览器连接设置输入 `.env` 的 `API_TOKEN`；刷新后需要重新输入 |
| 分析接口 503、模型未配置 | 设置 `LLM_API_KEY` 和 `LLM_MODEL` 后重跑启动脚本 |
| 模型 HTTP 错误或超时 | 核对模型服务地址、模型名、配额和后端网络；不要将密钥贴到日志 |
| 端口冲突 | 使用 `docker compose ps` 检查本项目；确认占用端口的程序后自行处理 |
| 上传失败 | 检查格式、重复/空列名、文件大小和数据集限制 |
| 缺失中文或静态 PNG 不正确 | Compose 后端镜像内置中文字体；本地 Python 开发需安装对应字体 |
| SSE 长时间不显示或被代理截断 | 检查代理缓冲、压缩与超时，保留 `text/event-stream` 和心跳；Nginx 示例见下 |

仅在已有认证和 TLS 的部署中加入反向代理时，可用下列路径规则转发前端及 SSE。该片段不构成完整公网部署配置：

```nginx
location / {
    proxy_pass http://127.0.0.1:3000;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_buffering off;
    proxy_cache off;
    proxy_read_timeout 300s;
}
```

## 公网上线边界

当前 Next.js 14 存在已记录的上游安全告警；共享令牌不是账户系统。正式对外开放还需升级受影响依赖、用户认证与租户授权、数据保留和备份、流量限制、可观测性，以及将高权限 Docker socket 与 Web 服务隔离。沙箱的禁网、资源限制和非 root 限制不等于宿主机的强安全边界。Phase 5 不宣称这些独立上线工作已经完成。

Compose 健康检查和启动依赖的行为参考 [Docker 官方文档](https://docs.docker.com/compose/how-tos/startup-order/)，参数参考 [docker compose up](https://docs.docker.com/reference/cli/docker/compose/up/)。
