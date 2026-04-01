# OpenList Python SDK

基于 OpenList 官方 API 文档 `https://openlist.apifox.cn/` 整理的一个轻量 Python SDK。

## 安装

```bash
pip install -e .
```

或把 `openlist_sdk` 目录直接拷到你的项目里使用。

## 配置

仓库里的测试脚本和海报墙构建脚本统一从根目录 `config.yml` 读取配置。

### 前后端分离相关配置

- 后端 API 默认读取 `backend.host`、`backend.port`、`backend.api_prefix`。
- 跨域白名单读取 `backend.cors.allow_origins`，开发期默认允许 `http://127.0.0.1:5173` 与 `http://localhost:5173`。
- 前端站点地址与部署边界读取 `frontend.site_url`、`frontend.dev_server_url`、`frontend.dist_dir`、`frontend.reverse_proxy_api_prefix`。
- 敏感信息优先通过环境变量覆盖：
  - `OPENLIST_TOKEN`
  - `OPENLIST_PASSWORD`
  - `TMDB_READ_ACCESS_TOKEN`
  - `TMDB_API_KEY`
  - `MEDIA_WALL_ADMIN_TOKEN`
  - `MEDIA_WALL_CORS_ALLOW_ORIGINS`
  - `MEDIA_WALL_FRONTEND_SITE_URL`

## React 前端工程

新前端位于 `frontend/`，采用 React + Vite + TypeScript。

### 本地开发

```bash
cd frontend
npm install
npm run dev
```

默认规则：

- `VITE_API_BASE_URL` 留空时，开发环境通过 Vite 代理把 `/api` 转发到 `VITE_DEV_API_TARGET`。
- 默认 `VITE_DEV_API_TARGET=http://127.0.0.1:8000`，对应 Python 后端 API。
- 若前端需要直连独立 API 域名，可设置 `VITE_API_BASE_URL=http://your-api-host/api/v1`。
- 如需调用受保护的刷新接口，可设置 `VITE_ADMIN_TOKEN`。

### 生产部署

```bash
cd frontend
npm run build
```

- 构建产物输出到 `frontend/dist/`。
- 当前后端已支持直接托管 `frontend/dist/`，因此生产环境可由同一个 Python 服务同时提供前端页面与 `/api/v1` API。
- 生产环境可保持 `VITE_API_BASE_URL` 为空，走同源 `/api/v1`；也可显式指向独立 API 域名。
- 旧 `media_wall_site/` 仅作为兼容说明页，不再承载主业务逻辑。

### Docker 部署

仓库提供了 [`Dockerfile`](Dockerfile)、[`docker-compose.yml`](docker-compose.yml)、[`.dockerignore`](.dockerignore) 与配置模板 [`config.example.yml`](config.example.yml)。

准备配置：

```bash
copy config.example.yml config.yml
```

然后按实际环境修改本地 [`config.yml`](config.yml)。

启动方式：

```bash
docker compose up -d
```

说明：

- 当前 [`docker-compose.yml`](docker-compose.yml) 面向服务器拉取镜像，直接使用 `ghcr.io/yancj9ya/openlistmedia:latest`。
- 容器内已同时提供前端静态资源与后端 API。
- 对外默认暴露端口 `8000`，对应 [`docker-compose.yml`](docker-compose.yml:8)。
- 本地真实配置文件 [`config.yml`](config.yml) 已被 [`.gitignore`](.gitignore) 忽略，不建议提交到 Git。
- 建议把模板配置维护在 [`config.example.yml`](config.example.yml) 中。

### GitHub Actions 自动构建镜像

仓库已新增工作流 [`docker-image.yml`](.github/workflows/docker-image.yml)，会在推送到默认分支时自动构建并推送镜像到 `ghcr.io`。

行为说明：

- 工作流文件：[`docker-image.yml`](.github/workflows/docker-image.yml)
- 触发条件：`push` 到 `main` / `master`，以及手动触发
- 推送目标：`ghcr.io/yancj9ya/openlistmedia`
- 默认标签包括：分支名、提交 SHA、默认分支上的 `latest`

使用前提：

- 仓库需托管在 GitHub
- 需要允许 Actions 写入 GitHub Packages
- 工作流默认使用 [`GITHUB_TOKEN`](.github/workflows/docker-image.yml) 登录 `ghcr.io`

镜像地址示例：
```text
ghcr.io/yancj9ya/openlistmedia:latest
```
```

### MVP 已落地与预留项

已落地：

- 分类浏览页
- 媒体列表页
- 媒体详情页
- 关键词搜索
- 类型筛选
- 手动刷新当前分类

预留：

- 高级排序
- 多条件筛选
- 更完整的前端缓存策略
- 管理员鉴权 UI

## 启动后端 API

```bash
python -m backend.main
```

或继续使用兼容入口：

```bash
python serve_media_wall.py
```

兼容入口会提示已降级，并转交独立后端 API 启动逻辑。

## 快速开始

```python
from openlist_sdk import OpenListClient

client = OpenListClient("http://127.0.0.1:5244")
token = client.login("admin", "your-password")

print("token:", token)
print("me:", client.me())
print("site settings:", client.public_settings())
print("root files:", client.list_dir("/"))
```

## 使用哈希密码登录

OpenList 文档里提供了 `/api/auth/login/hash`，密码需要先做：

```python
from openlist_sdk import OpenListClient

client = OpenListClient("http://127.0.0.1:5244")
token = client.login_hashed("admin", "your-password")
```

SDK 内部按文档约定自动执行：

```text
sha256(password + "-https://github.com/alist-org/alist")
```

## 常见文件操作

```python
from openlist_sdk import OpenListClient

with OpenListClient("http://127.0.0.1:5244", token="your-token") as client:
    files = client.list_dir("/")
    info = client.get_fs_info("/movie/demo.mp4")
    search = client.search("/", "demo")

    client.mkdir("/test-dir")
    client.rename("/test-dir", "test-dir-2")
    client.move("/", "/backup", ["test-dir-2"])
    client.copy("/backup", "/", ["test-dir-2"])
    client.remove("/backup", ["test-dir-2"])
```

## 上传文件

表单上传：

```python
from openlist_sdk import OpenListClient

with OpenListClient("http://127.0.0.1:5244", token="your-token") as client:
    result = client.upload_file("/uploads", "demo.txt", as_task=True)
    print(result)
```

流式上传：

```python
from openlist_sdk import OpenListClient

with OpenListClient("http://127.0.0.1:5244", token="your-token") as client:
    with open("big.iso", "rb") as stream:
        result = client.upload_stream("/uploads/big.iso", stream, as_task=True)
        print(result)
```

## Admin 接口

SDK 已经封装一批高频管理接口：

```python
client.list_users()
client.get_user(1)
client.list_settings()
client.get_setting("token")
client.list_storages()
client.list_driver_names()
client.upload_task_info()
```

如果你需要文档里的其他接口，也可以直接走通用请求：

```python
data = client.request("POST", "/api/admin/setting/save", json={
    "key": "custom_key",
    "value": "custom_value",
})
```

## 异常处理

```python
from openlist_sdk import OpenListAPIError, OpenListClient, OpenListHTTPError

try:
    client = OpenListClient("http://127.0.0.1:5244")
    client.login("admin", "wrong-password")
except OpenListAPIError as exc:
    print(exc.code, exc.message, exc.data)
except OpenListHTTPError as exc:
    print(exc.status_code, exc.response_text)
```

## 说明

- SDK 依据 OpenList Apifox 文档中公开的路径与示例请求整理。
- 一些 admin 接口在文档示例里没有完整展示 header 或参数细节，因此 SDK 同时保留了 `request()` 通用入口，便于你补充未封装接口。
- `Authorization` 头按文档示例直接发送 token 原文，不额外加 `Bearer ` 前缀。
- 前端部署时请避免把敏感配置写入前端构建产物，管理员 token 仅建议在受控环境中临时使用。
