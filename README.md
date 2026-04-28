# OpenListMedia

一个围绕 OpenList 构建的媒体资源浏览项目，提供：

- Python OpenList SDK
- 基于 SQLite 缓存的媒体扫描与查询服务
- 原生 Python HTTP 后端 API
- React + Vite + TypeScript 前端
- 可选 Docker / Docker Compose 部署方式

项目当前已经从“静态海报墙生成”逐步演进为“前后端分离 + 按需扫描 + 缓存驱动”的媒体浏览系统。用户可以通过分类树浏览目录、查看媒体列表与详情、获取播放链接，并支持管理员刷新分类缓存与修改部分配置。

---

## 1. 项目定位

本仓库并不只是一个单独的 SDK，也不只是一个静态站点，而是一个完整的媒体浏览解决方案，主要适用于以下场景：

- OpenList 中已经整理好了影视资源目录
- 希望自动补充 TMDb 元数据
- 希望使用更适合浏览的 Web UI 而不是直接在网盘目录中翻找
- 希望避免每次打开页面都全量扫描远程目录
- 希望在本地或服务器上以较低复杂度部署一套可浏览、可刷新、可维护的媒体库

当前核心机制：

1. 前端先请求分类树
2. 用户进入某个分类后，再按需请求该分类下的媒体列表
3. 后端优先读取 SQLite 缓存
4. 当缓存不存在或已过期时，后端再扫描 OpenList 并写回数据库
5. 前端通过 API 展示分类、详情、筛选结果与播放链接

---

## 2. 功能概览

### 已实现功能

- 分类树浏览
- 媒体列表分页查询
- 媒体详情查看
- 关键词搜索
- 媒体类型筛选
- 年份筛选
- 分类级刷新
- 单媒体项刷新
- 基于口令的访客 / 管理员访问控制
- 前端设置页读取与更新配置
- 前端构建产物由 Python 后端直接托管
- Docker 镜像与 Compose 部署支持
- GitHub Actions 自动构建镜像

### 当前架构特点

- 后端不依赖 Flask / FastAPI，使用原生 Python HTTP 服务
- 前端为独立 React 工程，生产构建后可由后端静态托管
- 媒体数据缓存在 `media_wall.db` 中，减少重复扫描压力
- 支持通过环境变量覆盖敏感配置
- 历史静态媒体墙实现已归档到 `old/`，当前运行链路只保留 API + SPA

### 仍可继续增强的方向

- 更丰富的排序能力
- 多条件复合筛选
- 更细粒度的权限体系
- 更完整的前端缓存策略
- 更细致的错误提示与后台任务反馈

---

## 3. 仓库结构

```text
.
├─ backend/                  # 后端 API、配置、DTO、路由、服务层
├─ frontend/                 # React + Vite 前端工程
├─ openlist_sdk/             # OpenList Python SDK
├─ old/                      # 历史静态媒体墙实现、兼容入口和手动烟雾脚本归档
├─ .github/workflows/        # CI/CD 工作流
├─ config_loader.py          # YAML 配置加载与保存
├─ config.example.yml        # 配置模板
├─ docker-compose.yml        # 容器部署编排
├─ Dockerfile                # 镜像构建文件
├─ tmdb_sdk.py               # TMDb 调用相关代码
├─ media_wall.db             # SQLite 缓存数据库
└─ README.md
```

### 目录职责说明

#### `backend/`

后端核心目录，负责：

- 读取配置
- 初始化服务
- 暴露 HTTP API
- 访问缓存数据库
- 调用扫描器从 OpenList 抽取数据
- 返回前端需要的结构化 DTO

主要模块：

- `backend/main.py`：推荐启动入口
- `backend/app.py`：创建后端服务对象
- `backend/api/server.py`：原生 HTTP Server 与静态文件托管逻辑
- `backend/api/routes/media_routes.py`：API 路由分发
- `backend/service/media_service.py`：业务服务层
- `backend/config/settings.py`：配置读取与环境变量覆盖逻辑
- `backend/repository/`：SQLite 数据访问层
- `backend/scanner/`：OpenList 扫描逻辑
- `backend/dto/`：返回给前端的数据转换层

#### `frontend/`

前端单页应用工程，基于：

- React 18
- React Router 6
- TypeScript
- Vite 5

页面包含：

- 访问口令页
- 分类页
- 媒体列表页
- 媒体详情页
- 设置页（管理员）
- 404 页面

#### `openlist_sdk/`

对 OpenList HTTP API 的 Python 封装，可单独被其他项目使用。

#### `old/`

历史归档目录，包含早期静态媒体墙实现、旧兼容入口、旧说明文档和依赖真实服务的手动烟雾脚本；当前主业务不再从这里启动或加载代码。

---

## 4. 技术栈

### 后端

- Python 3.9+
- requests
- PyYAML
- SQLite
- 原生 `http.server` / `socketserver`

### 前端

- React 18
- TypeScript 5
- Vite 5
- React Router DOM 6

### 外部依赖服务

- OpenList
- TMDb（可选，但建议启用以获得更完整元数据）

---

## 5. 运行前准备

在启动本项目之前，建议先确认以下条件：

### 必备条件

- 已安装 Python 3.9 或更高版本
- 已安装 Node.js（建议 Node 18+）
- 已有可访问的 OpenList 服务
- 已准备好 OpenList 的 token 或用户名密码

### 推荐条件

- 具备 TMDb 访问凭证，以便补充媒体元数据
- 已规划好 OpenList 中的媒体目录结构
- 如果是服务器部署，已确认对外端口与反向代理策略

---

## 6. 安装

### 安装 Python 依赖

在仓库根目录执行：

```bash
pip install -e .
```

安装来源见 `pyproject.toml`，当前基础依赖包括：

- `requests>=2.31.0`
- `PyYAML>=6.0.2`

### 安装前端依赖

```bash
cd frontend
npm install
```

前端依赖定义于 `frontend/package.json`。

---

## 7. 配置说明

项目统一从根目录的 `config.yml` 读取配置。首次使用时，先从模板复制：

```bash
copy config.example.yml config.yml
```

然后按实际环境修改 `config.yml`。

### 配置模板示例

```yaml
openlist:
  base_url: http://127.0.0.1:5244
  token: ''
  username: admin
  password: your-password
  hash_login: false

tmdb:
  read_access_token: ''
  api_key: ''
  language: zh-CN

media_wall:
  media_root: /影视资源
  port: 8000
  item_url_template: http://127.0.0.1:5244/d{path}?sign={sign}
  database_path: media_wall.db
  cache_ttl_seconds: 86400
  list_retry_count: 2
  retry_delay_seconds: 1
  skip_failed_directories: true
  skip_directories:
    - 热更

backend:
  host: 0.0.0.0
  port: 8000
  api_prefix: /api/v1
  admin_token: ''
  cors:
    allow_origins:
      - http://127.0.0.1:5173
      - http://localhost:5173
    allow_methods:
      - GET
      - POST
      - OPTIONS
    allow_headers:
      - Content-Type
      - X-Admin-Token
      - X-Access-Passcode

frontend:
  site_url: http://127.0.0.1:8000
  dev_server_url: http://127.0.0.1:5173
  dist_dir: frontend/dist
  reverse_proxy_api_prefix: /api/v1
  admin_passcode: admin
  visitor_passcode: yancj
```

### 配置分块说明

#### `openlist`

用于连接 OpenList：

- `base_url`：OpenList 服务地址
- `token`：优先使用的认证 token
- `username` / `password`：未配置 token 时可使用账号密码登录
- `hash_login`：是否使用哈希密码登录接口

#### `tmdb`

用于补充媒体元数据：

- `read_access_token`：TMDb 推荐使用的读令牌
- `api_key`：备用 API Key
- `language`：元数据语言，默认 `zh-CN`

#### `media_wall`

媒体扫描和缓存策略：

- `media_root`：OpenList 中作为媒体根目录的路径
- `port`：后端兼容读取的端口配置，未配置 `backend.port` 时可复用
- `item_url_template`：播放直链模板
- `database_path`：SQLite 数据库路径
- `cache_ttl_seconds`：缓存有效期（秒）
- `list_retry_count`：目录扫描失败重试次数
- `retry_delay_seconds`：重试间隔
- `skip_failed_directories`：是否允许跳过失败目录
- `skip_directories`：需要完全跳过的目录名列表

#### `backend`

后端 API 服务配置：

- `host`：监听地址
- `port`：监听端口
- `api_prefix`：API 前缀，默认 `/api/v1`
- `admin_token`：受保护刷新接口的管理令牌
- `cors.allow_origins`：跨域来源白名单
- `cors.allow_methods`：允许的方法
- `cors.allow_headers`：允许的请求头

#### `frontend`

前端运行与访问控制：

- `site_url`：生产环境站点 URL
- `dev_server_url`：开发环境前端地址
- `dist_dir`：前端构建输出目录
- `reverse_proxy_api_prefix`：反向代理下的 API 前缀
- `admin_passcode`：管理员访问口令
- `visitor_passcode`：普通访客访问口令

---

## 8. 环境变量覆盖

敏感信息建议优先通过环境变量注入，避免直接写入配置文件。

当前已支持的环境变量包括：

- `OPENLIST_TOKEN`
- `OPENLIST_PASSWORD`
- `TMDB_READ_ACCESS_TOKEN`
- `TMDB_API_KEY`
- `MEDIA_WALL_ADMIN_TOKEN`
- `MEDIA_WALL_CORS_ALLOW_ORIGINS`
- `MEDIA_WALL_FRONTEND_SITE_URL`

说明：

- 后端会优先读取环境变量，再回退到 `config.yml`
- `MEDIA_WALL_CORS_ALLOW_ORIGINS` 支持逗号分隔，也兼容 `|` 分隔
- 更适合在 Docker、CI/CD、服务器进程管理器中使用

---

## 9. 本地开发

项目本地开发通常分为“后端 API”与“前端开发服务器”两个部分。

### 9.1 启动后端 API

推荐方式：

```bash
python -m backend.main
```

启动后会监听 `backend.host` 与 `backend.port` 指定的地址，并提供：

- API 接口
- 已构建前端的静态托管能力（如果 `frontend/dist` 存在）

### 9.2 启动前端开发服务器

```bash
cd frontend
npm run dev
```

前端默认通过 Vite 启动开发服务器，通常地址为：

- `http://127.0.0.1:5173`
- 或 `http://localhost:5173`

### 9.3 前端环境变量

参考 `frontend/.env.example`：

```env
VITE_API_BASE_URL=
VITE_DEV_API_TARGET=http://127.0.0.1:8000
VITE_SITE_BASE_URL=http://127.0.0.1:5173
VITE_ADMIN_TOKEN=
```

说明如下：

- `VITE_API_BASE_URL`：
  - 留空时，前端默认使用 `/api/v1`
  - 生产环境同源部署时通常可保持为空
  - 如需直连独立 API 域名，可显式配置完整 URL
- `VITE_DEV_API_TARGET`：开发期 Vite 代理转发目标
- `VITE_SITE_BASE_URL`：站点基础地址
- `VITE_ADMIN_TOKEN`：调用受保护刷新接口时可使用的管理令牌

### 9.4 推荐开发流程

1. 根目录配置好 `config.yml`
2. 启动后端：`python -m backend.main`
3. 启动前端：`cd frontend` 后执行 `npm run dev`
4. 浏览器访问前端开发地址
5. 输入访客或管理员口令进入系统

---

## 10. 生产构建与部署

### 10.1 构建前端

```bash
cd frontend
npm run build
```

构建完成后：

- 输出目录为 `frontend/dist`
- Python 后端可直接托管该目录下的静态资源
- 用户访问后端根路径时，可直接返回前端页面

### 10.2 同源部署方式

这是当前最推荐的生产模式：

- 前端静态资源放在 `frontend/dist`
- 后端统一对外监听，例如 `http://127.0.0.1:8000`
- API 前缀保持 `/api/v1`
- 前端通过同源方式访问 API

优势：

- 部署简单
- 避免复杂跨域问题
- 便于反向代理与统一入口管理

### 10.3 反向代理场景

如果你使用 Nginx、Caddy 或其他网关，也可以：

- 让 `/` 指向前端静态资源
- 让 `/api/v1` 反向代理到后端服务
- 在前端保留相对 API 前缀，减少环境差异

---

## 11. Docker 部署

仓库已提供：

- `Dockerfile`
- `docker-compose.yml`
- `.dockerignore`
- `config.example.yml`

### 11.1 准备配置文件

```bash
copy config.example.yml config.yml
```

修改本地 `config.yml` 后再启动容器。

### 11.2 使用 Compose 启动

```bash
docker compose up -d
```

### 11.3 Docker 部署说明

- 当前 `docker-compose.yml` 面向直接拉取镜像部署
- 默认镜像地址为：`ghcr.io/yancj9ya/openlistmedia:latest`
- 容器内同时包含前端静态资源与后端 API
- 默认对外暴露端口为 `8000`
- 建议不要把真实 `config.yml` 提交到仓库中

### 11.4 推荐做法

- 仓库中只维护 `config.example.yml`
- 真实环境使用单独挂载的 `config.yml`
- token、密码类敏感内容尽量用环境变量注入

---

## 12. GitHub Actions 自动构建镜像

仓库内已提供自动构建工作流：

- `.github/workflows/docker-image.yml`

主要行为：

- 当推送到 `main` / `master` 时自动触发
- 支持手动触发
- 自动构建并推送镜像到 GitHub Container Registry（GHCR）
- 默认生成分支名、提交 SHA、以及默认分支 `latest` 等标签

镜像示例：

```text
ghcr.io/yancj9ya/openlistmedia:latest
```

使用前提：

- 仓库托管在 GitHub
- GitHub Actions 有权限写入 GitHub Packages
- 工作流使用 `GITHUB_TOKEN` 登录 GHCR

---

## 13. API 概览

以下为当前后端核心接口摘要。

> 默认 API 前缀：`/api/v1`

### 健康检查

- `GET /api/v1/health`

返回服务状态、媒体根目录、数据库路径等基础信息。

### 分类树

- `GET /api/v1/categories`
- `GET /api/v1/categories?path=/影视资源/电影`

用于获取分类树或指定分类下的子分类结构。

### 设置读取

- `GET /api/v1/settings`

请求头需要：

- `X-Access-Passcode: <admin_passcode>`

### 媒体列表

- `GET /api/v1/media`

常见查询参数：

- `category_path`
- `include_descendants=1`
- `year`
- `page`
- `page_size`
- `keyword`
- `type`
- `sort_by`
- `sort_order`

### 媒体详情

- `GET /api/v1/media/{mediaId}`

### 刷新提示

- `GET /api/v1/refresh`

如果开启了 `backend.admin_token`，请求头需要：

- `X-Admin-Token: <admin_token>`

### 访问认证

- `POST /api/v1/auth/login`

请求体示例：

```json
{
  "passcode": "your-passcode"
}
```

返回角色：

- `admin`
- `visitor`

### 获取播放链接

- `POST /api/v1/play-link`

请求体示例：

```json
{
  "path": "/影视资源/电影/示例电影 (2024) {tmdb-123}/movie.mp4"
}
```

### 保存设置并触发重启

- `POST /api/v1/settings`

请求头需要：

- `X-Access-Passcode: <admin_passcode>`

保存后后端会请求重启进程。

### 刷新分类或单媒体项

- `POST /api/v1/refresh`

请求体二选一：

刷新分类：

```json
{
  "category_path": "/影视资源/电影"
}
```

刷新单媒体项：

```json
{
  "media_path": "/影视资源/电影/示例电影 (2024) {tmdb-123}"
}
```

---

## 14. 前端页面与访问逻辑

当前前端路由包含：

- `/`：访问口令页
- `/categories`：分类页
- `/media`：媒体列表页
- `/media/:mediaId`：媒体详情页
- `/settings`：设置页（仅管理员）
- `*`：404 页面

访问控制规则：

- 未认证用户会被引导回首页输入口令
- 普通访客可浏览分类与媒体内容
- 管理员可进入设置页并执行管理操作

---

## 15. 缓存与扫描机制

项目的关键价值之一是“按需扫描 + SQLite 缓存”。

### 工作方式

- 请求分类树时，后端按配置扫描 OpenList 目录结构
- 请求媒体列表时，优先从数据库查询
- 如果某个分类缓存已过期，则先刷新该分类再返回结果
- 刷新分类会把该分类下的媒体重新写入数据库
- 刷新单媒体项会替换数据库中的对应记录

### 缓存优势

- 减少频繁访问 OpenList 带来的延迟
- 降低远程目录扫描成本
- 改善前端翻页、筛选、搜索体验
- 为后续更复杂的排序与筛选提供基础

### 异常处理策略

对于目录读取异常：

- 支持按配置自动重试
- 某些失败目录可以被跳过
- 可通过 `skip_directories` 排除不需要扫描的目录

---

## 16. 媒体目录命名建议

为了获得更好的识别效果，建议媒体目录尽量遵循统一命名规则。

### 电影目录建议

```text
标题 (年份) {tmdb-12345}
```

示例：

```text
Interstellar (2014) {tmdb-157336}
```

### 剧集目录建议

季目录推荐：

```text
Season 1
Season 2
```

单集文件名如果带有类似模式，也更容易被系统识别：

```text
S01E01
S01E03-E05
```

### 命名建议总结

- 标题尽量准确
- 年份尽量保留
- 如果已知 TMDb ID，建议直接写入目录名
- 剧集分季命名保持统一
- 避免在目录层级中混入大量非媒体文件

---

## 17. OpenList SDK 使用说明

除了完整媒体系统之外，仓库中的 `openlist_sdk/` 也可以独立使用。

### 17.1 安装

```bash
pip install -e .
```

或者直接复制 `openlist_sdk` 目录到你的项目中。

### 17.2 快速开始

```python
from openlist_sdk import OpenListClient

client = OpenListClient("http://127.0.0.1:5244")
token = client.login("admin", "your-password")

print("token:", token)
print("me:", client.me())
print("site settings:", client.public_settings())
print("root files:", client.list_dir("/"))
```

### 17.3 使用哈希密码登录

```python
from openlist_sdk import OpenListClient

client = OpenListClient("http://127.0.0.1:5244")
token = client.login_hashed("admin", "your-password")
```

SDK 内部会按 OpenList 文档规则计算：

```text
sha256(password + "-https://github.com/alist-org/alist")
```

### 17.4 常见文件操作

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

### 17.5 上传文件

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

### 17.6 Admin 接口

```python
client.list_users()
client.get_user(1)
client.list_settings()
client.get_setting("token")
client.list_storages()
client.list_driver_names()
client.upload_task_info()
```

### 17.7 通用请求入口

如果某些接口尚未封装，可直接调用：

```python
data = client.request("POST", "/api/admin/setting/save", json={
    "key": "custom_key",
    "value": "custom_value",
})
```

### 17.8 异常处理

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

### 17.9 SDK 说明

- SDK 基于 OpenList Apifox 文档公开接口整理
- 一些管理接口细节在官方示例中不够完整，因此保留 `request()` 通用入口
- `Authorization` 请求头按当前项目实现直接发送 token 原文，不额外加 `Bearer ` 前缀

---

## 18. 常见问题

### 1）访问前端后看不到数据

排查顺序：

- 确认后端是否成功启动
- 确认 `config.yml` 中 `openlist.base_url` 是否正确
- 确认 OpenList token / 用户密码是否有效
- 确认 `media_wall.media_root` 是否真实存在
- 查看数据库是否已生成缓存记录

### 2）前端开发环境请求失败或跨域

- 确认后端端口与 `VITE_DEV_API_TARGET` 一致
- 确认 `backend.cors.allow_origins` 包含前端实际访问地址
- 如果使用 `127.0.0.1` 启动前端，不要只配置 `localhost`

### 3）刷新接口返回 403

可能原因：

- 已配置 `backend.admin_token`，但请求头未带 `X-Admin-Token`
- 使用了错误的管理口令访问设置接口
- 前端环境变量中的 `VITE_ADMIN_TOKEN` 未配置或不匹配

### 4）媒体信息不完整

- 检查目录命名是否规范
- 检查 TMDb 凭证是否有效
- 确认目录名是否包含年份 / TMDb ID

### 5）生产环境打开页面 404

- 确认已经执行前端构建
- 确认 `frontend/dist` 存在
- 确认 `frontend.dist_dir` 指向正确目录

---

## 19. 历史归档说明

项目早期更偏向静态海报墙生成，目前已经演进为 API + SPA 的方式。

旧实现已统一归档到 `old/`：

- `old/media_wall_builder.py`
- `old/media_wall_service.py`
- `old/media_wall_site/`
- `old/serve_media_wall.py`
- `old/test_openlist_sdk.py`
- `old/test_tmdb_sdk.py`
- `old/MEDIA_WALL.md`

当前推荐启动入口是 `backend/main.py`，正式前端入口是 `frontend/`。

---

## 20. 开发建议

如果你准备继续扩展本项目，建议优先关注以下模块：

### 后端扩展建议

- 在 `backend/api/routes/` 中继续拆分路由
- 在 `backend/service/` 中补充更细粒度的业务逻辑
- 在 `backend/repository/` 中增强查询能力与索引策略
- 在 `backend/scanner/` 中改进目录识别与异常处理

### 前端扩展建议

- 增加更细化的筛选 UI
- 补充 loading / retry / error 交互
- 为设置页增加字段校验与提示
- 优化移动端布局与详情页展示

### 运维建议

- 通过环境变量管理敏感值
- 将数据库与配置文件使用持久卷挂载
- 在反向代理层做 HTTPS 与访问控制
- 对 OpenList 与本项目日志进行统一采集

---

## 21. 安全提醒

- 不要把真实 `config.yml` 提交到代码仓库
- 不要把 OpenList 密码、TMDb 凭证、管理员 token 明文暴露在前端构建产物中
- 如果对外开放服务，请至少配置反向代理、HTTPS 与访问限制
- `visitor_passcode` 和 `admin_passcode` 应根据实际环境修改，不要保留默认值

---

## 22. 总结

如果你希望获得一套：

- 可以连接 OpenList 的媒体浏览系统
- 可以按需扫描并缓存媒体信息
- 可以通过 Web UI 浏览分类、列表和详情
- 可以在本地快速跑起来，也可以通过 Docker 部署
- 同时还能复用一个独立的 Python OpenList SDK

那么这个仓库已经提供了较完整的基础能力。

当前推荐使用方式是：

1. 配置 `config.yml`
2. 启动 `python -m backend.main`
3. 开发时单独启动 `frontend/` 的 Vite
4. 生产环境构建前端并交由后端统一托管

这也是本项目目前最稳定、最清晰的使用路径。
