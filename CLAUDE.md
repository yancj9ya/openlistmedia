# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

### 后端（Python 3.9+）
```bash
pip install -e .                 # 安装 Python 依赖（同时安装 openlist_sdk 为可编辑包）
python -m backend.main           # 推荐启动入口：加载配置、启动 API、启动定时刷新
python serve_media_wall.py       # 兼容入口，内部只是转发到 backend.main.main()
python test_openlist_sdk.py      # OpenList SDK 烟雾测试（真实请求，需要 config.yml）
python test_tmdb_sdk.py          # TMDb SDK 烟雾测试（真实请求）
```

仓库中没有 pytest 测试套件。`test_*.py` 是依赖真实 OpenList/TMDb 服务的手动烟雾脚本，从 `config.yml` 的 `tests.*` 节读取参数，不能在 CI 中无配置跑。

### 前端（Node 18+）
```bash
cd frontend
npm install
npm run dev                      # Vite 5173，/api 代理到 VITE_DEV_API_TARGET（默认 127.0.0.1:8000）
npm run build                    # tsc -b && vite build，输出到 frontend/dist
npm run preview                  # Vite 预览构建产物（4173）
```

### Docker
```bash
docker compose up -d             # 使用 ghcr.io/yancj9ya/openlistmedia:latest
```
`Dockerfile` 分两阶段：`node:20-bookworm` 构建前端，`python:3.11-slim` 运行后端；最终镜像只含 `frontend/dist` 而不是 node_modules。镜像由 `.github/workflows/docker-image.yml` 在 push 到 main/master 时自动构建。

## 架构要点

### 整体形态
单进程 Python 后端 + 独立 React SPA。后端**没有使用 Flask/FastAPI**——直接基于 `http.server.BaseHTTPRequestHandler` + `socketserver.TCPServer`。同源部署模式下，后端既提供 `/api/v1/*`，又在 API 404 时回退托管 `frontend/dist` 静态资源（`backend/api/server.py` 的 `_try_serve_frontend`）。

### backend/ 分层
- `main.py` → `app.py::create_backend_server()` 是唯一启动路径，组装：配置 → `MediaWallService` → `ScheduledRefreshRunner` → `MediaRoutes` → `BackendHTTPRequestHandler` → `ReusableTCPServer`
- `config/settings.py`：把根目录的 `config.yml`（通过 `config_loader.py` 解析）装配为 dataclass（`BackendConfig`、`APIConfig`、`FrontendConfig`、`MediaWallConfig`、`CORSConfig`）。**env 变量优先于 YAML**，支持项见下。
- `api/routes/media_routes.py`：唯一路由分发。GET 走 `handle()`，POST 走 `handle_post()`。路由键全部是 `{api_prefix}/...` 的字符串比较，新增路由需在这里改。
- `service/media_service.py`：业务层。持有 `MediaWallDB`（SQLite repository）和 `OpenListScanner`。
- `repository/media_repository.py`：SQLite 访问层，表 `category_cache` + `media_items` + 最近播放历史。打开 DB 失败会 fallback 到 `.cache/media_wall_fallback.db`。
- `scanner/openlist_scanner.py`：从 OpenList 拉目录 + 匹配目录名 + 调 TMDb 补全元数据。TMDb 结果持久化到 `.cache/media_wall_tmdb_cache.json`。
- `scheduler.py`：自研的 5 字段 cron 解析器 + `ScheduledRefreshRunner` 后台线程，按 `media_wall.refresh_cron` 周期调用 `service.refresh_all_categories()`。

### 按需扫描 + 缓存驱动（核心工作流）
1. 前端请求分类树 → `scanner.list_categories()` 实时列 OpenList（此处**不**写数据库）。
2. 前端请求媒体列表 → service 先看 `category_cache.scanned_at` 是否在 `cache_ttl_seconds` 内；**过期则先同步扫描写库，再从库查**（`get_media_list` 中 `cache_is_fresh` 分支）。
3. 显式 `POST /refresh` 可强制整分类或单媒体刷新。
4. `POST /play-link` 动态拿 `sign` 拼直链；若 OpenList 返回 404/object not found，会用 `_guess_cached_category_path` 猜到最近的已缓存父目录并刷新一次，解决网盘重命名导致的直链失效。

### 媒体识别规则（规则驱动整个 scanner）
- 媒体目录名必须匹配 `MEDIA_PATTERN = r"^(?P<title>.+?)\s*\((?P<year>\d{4})\)\s*\{tmdb-(?P<tmdb_id>\d+)\}\s*$"`，例如 `Interstellar (2014) {tmdb-157336}`。
- 剧集子目录匹配 `SEASON_PATTERN = r"^Season\s+(?P<number>\d+)$"`。
- 分集文件名匹配 `EPISODE_PATTERN = r"S(\d{1,2})E(\d{1,3})(?:-E?(\d{1,3}))?"`。
- 视频扩展名白名单见 `VIDEO_SUFFIXES`（`.mp4/.mkv/.avi/...`）。
- 改动上述正则会直接影响缓存/元数据/前端展示，需同步考虑已有库里的数据。

### 环境变量覆盖
YAML 中的敏感字段会被以下 env 变量优先取代（逻辑在 `config/settings.py::_env_or_config`）：
- `OPENLIST_TOKEN`, `OPENLIST_PASSWORD`
- `TMDB_READ_ACCESS_TOKEN`, `TMDB_API_KEY`
- `MEDIA_WALL_ADMIN_TOKEN`
- `MEDIA_WALL_CORS_ALLOW_ORIGINS`（逗号或 `|` 分隔字符串，会被 `_string_list` 拆成数组）
- `MEDIA_WALL_FRONTEND_SITE_URL`

前端 Vite 变量（`frontend/.env*`）：`VITE_API_BASE_URL`、`VITE_DEV_API_TARGET`、`VITE_SITE_BASE_URL`、`VITE_ADMIN_TOKEN`。`VITE_API_BASE_URL` 留空时默认 `/api/v1`（同源部署）。

### 保存设置会重启进程
`POST /api/v1/settings` 成功后 service 会起一个守护线程调用 `os.execv(sys.executable, [sys.executable, "-m", "backend.main"])` 替换进程。这意味着：
- Windows 下 CWD 会保持；
- 请求端会看到连接被切断；
- **不要在保存设置后马上做依赖 DB 连接的操作**；
- 调试时改 `backend/service/media_service.py::_restart_process` 需要手动重启验证。

另外 `update_settings` 对比 `skip_directories` 变化，一旦不同会调 `db.clear_all_cache()` 丢弃所有分类缓存。

### 访问控制
- 双口令：`frontend.admin_passcode` / `frontend.visitor_passcode`，由后端 `/auth/login` 校验并返回 `role`。
- 前端在 `src/app/providers.tsx` 把 `{role, passcode}` 存入 `localStorage['openlistmedia:auth']`；`RequireAuth`/`RequireAdmin` 是路由级门禁。
- `/settings` 的 GET/POST 要求请求头 `X-Access-Passcode` 等于 admin_passcode。
- `/refresh` 在 `backend.admin_token` 非空时额外要求请求头 `X-Admin-Token`。

### 前端目录约定（类 FSD）
- `app/`：路由、全局 provider、布局
- `pages/`：一页一文件
- `features/`：跨实体能力（如 `media-browser` 的数据钩子、`admin-refresh`）
- `entities/`：领域模型 + 展示卡（`category`、`media`）
- `shared/`：`api/`（client、config、types、media-api）、`lib/`、`ui/`、`styles/`
- 所有 HTTP 统一走 `shared/api/client.ts::requestJson`，错误封装为 `ApiClientError`；新增接口加在 `shared/api/media-api.ts`。

## 历史遗留（不要在这里改功能）
- `media_wall_builder.py`、`media_wall_service.py`、`media_wall_site/`：旧的"一次性全量构建静态海报墙"实现，仍存在但不再承载主业务。
- `serve_media_wall.py`：已降级为转调 `backend.main` 的兼容壳。
- 根目录的 `media_wall.db` 是真实运行中的缓存库，体积较大（16MB+），**修改前确认是否要备份**。
