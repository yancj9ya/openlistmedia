# OpenList 影视海报墙

这个项目现在是按需扫描模式：

- 前端先读取分类目录树
- 你点到哪个分类，前端就请求哪个分类
- 后端优先读 SQLite 缓存
- 没缓存或缓存过期时，再扫描 OpenList 并写入数据库
- `热更` 这类目录可以配置为跳过

## 入口文件

- `media_wall_builder.py`
  - 旧的全量构建脚本，保留作参考
- `media_wall_service.py`
  - OpenList 扫描
  - TMDb 元数据补全
  - SQLite 缓存
- `serve_media_wall.py`
  - 本地启动静态页面和 API 服务

## 配置文件

项目统一从根目录的 `config.yml` 读取配置。

```yaml
openlist:
  base_url: "http://127.0.0.1:5244"
  token: ""
  username: ""
  password: ""
  hash_login: false

tmdb:
  read_access_token: ""
  api_key: ""
  language: "zh-CN"

media_wall:
  media_root: "/影视资源"
  site_dir: "media_wall_site"
  port: 8000
  database_path: "media_wall.db"
  cache_ttl_seconds: 86400
  item_url_template: "http://127.0.0.1:5244/d{path}"
  list_retry_count: 2
  retry_delay_seconds: 1.0
  skip_failed_directories: true
  skip_directories:
    - "热更"
```

如果你不用 token，就填 `username/password`。

## 启动页面

```powershell
python serve_media_wall.py
```

然后打开 `http://127.0.0.1:8000`。

## API

- `GET /api/categories`
  - 读取可浏览的分类树
- `GET /api/category?path=/影视资源/电影`
  - 读取某个分类的缓存或触发扫描
- `GET /api/category?path=/影视资源/电影&refresh=1`
  - 强制刷新当前分类

## 目录命名约定

媒体目录格式：

```text
标题 (年份) {tmdb-12345}
```

电视剧目录推荐使用：

```text
Season 1
Season 2
```

单集文件如果带 `S01E01` 或 `S01E03-E05`，也会被识别。

如果某些目录偶发返回 `502`，后端会按配置重试，并在分类响应的 `failed_paths` 里返回被跳过的目录。
