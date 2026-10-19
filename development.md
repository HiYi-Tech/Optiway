# 本地开发

## 环境

- Python 3.14（由 `.python-version` 指定，`uv` 会自动安装）
- [uv](https://docs.astral.sh/uv/)

```bash
uv sync
uv run fastapi dev
```

- H5：<http://127.0.0.1:8000>
- API 文档：<http://127.0.0.1:8000/docs>
- 健康检查：<http://127.0.0.1:8000/api/health>

`fastapi dev` 会自动读取 `pyproject.toml` 中的入口：

```toml
[tool.fastapi]
entrypoint = "app.main:app"
```

## 配置

复制 `.env.example` 为 `.env` 后按需修改：

```bash
cp .env.example .env
```

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ROUTE_PROVIDER` | `auto` | `auto` / `google` / `osrm` / `local` |
| `GOOGLE_MAPS_API_KEY` | 空 | 配置后 `auto` 优先使用 Google Routes |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` | OSRM 服务地址 |
| `HTTP_TIMEOUT_SECONDS` | `15` | 外部请求超时 |
| `MAP_TILE_URL` | OpenStreetMap Germany | Leaflet 瓦片 URL 模板 |
| `MAP_TILE_ATTRIBUTION` | OSM 署名 | 地图署名弹层内容 |
| `MAP_TILE_MAX_ZOOM` | `19` | 底图最大缩放级别 |

`.env` 不会被打包到 FastAPI Cloud（见 `.fastapicloudignore`）。

## 数据源实现

### Google Routes

`app/providers/google.py` 调用：

```text
POST https://routes.googleapis.com/directions/v2:computeRoutes
```

关键点：

- 请求体设置 `optimizeWaypointOrder: true`；
- `X-Goog-FieldMask` 必须包含 `routes.optimizedIntermediateWaypointIndex`，否则请求会失败；
- 驾车模式使用 `routingPreference: TRAFFIC_AWARE`；
- 返回的 `polyline.encodedPolyline` 会被解码为 `[lng, lat]` 数组。

Google 官方文档：

- <https://developers.google.com/maps/documentation/routes/compute_route>
- <https://developers.google.com/maps/documentation/routes/opt-way>

### OSRM

`app/providers/osrm.py`：

- 需要优化顺序且存在途经点时调用 `/trip/v1/driving/...`，参数为
  `roundtrip=false&source=first&destination=last`；
- 不优化时调用 `/route/v1/driving/...`；
- 公共演示实例只提供驾车 profile，步行/骑行会回退到本地模拟。

### 本地模拟

`app/providers/local.py`：

- Haversine 距离；
- Held-Karp 动态规划求精确的最短访问顺序（最多 10 个途经点，计算量很小）；
- 按平均速度估算耗时：驾车 32 km/h、步行 4.8 km/h、骑行 15 km/h；
- 几何为站点之间的直线，仅用于演示。

## 前端

`app/static/` 是原生 HTML/CSS/JS 单页应用：

- `index.html`：页面结构与底部地点选择器；
- `styles.css`：移动端优先样式，桌面端 900px 以上切换双栏；
- `app.js`：状态管理、Leaflet 地图、API 调用；
- `vendor/leaflet/`：本地化的 Leaflet 1.9.4，避免依赖 CDN。

底图默认使用 OpenStreetMap 德国镜像 `tile.openstreetmap.de`。若用户网络无法访问瓦片，页面会提示，但路线折线和标记仍会显示。可以通过 `MAP_TILE_URL` 和 `MAP_TILE_ATTRIBUTION` 切换为其他 OSM 镜像、自建瓦片或已授权的地图服务；切换后请同步更新署名。

## 测试与检查

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

测试不依赖外部网络：

- `tests/test_local_optimizer.py`：距离计算与 Held-Karp 排序；
- `tests/test_polyline.py`：Google polyline 解码；
- `tests/test_api.py`：健康检查、地点库、参数校验、本地路线。

## 常见改动

### 调整途经点上限

修改 `app/config.py` 的 `MAX_INTERMEDIATES`，同时同步前端 `app/static/app.js` 中的 `MAX_INTERMEDIATES` 常量。Google Routes API 可支持更多途经点；OSRM 公共实例请控制请求规模。

### 增加地址搜索

当前地点来源是内置推荐地点、地图选点和坐标输入。可以：

- 在 `app/api.py` 增加 `/api/geocode`，服务端调用 Google Geocoding / Places API；
- 或接入高德地图 Web 服务 API；
- 前端在 `renderPlaces()` 旁增加搜索框，选中结果后复用 `applyPlace()`。

### 增加时间窗 / 人员排班

当前目标是「最短行程时间/距离」。若需要「在指定时间窗内拜访」，可在 `OptimizeRequest` 中为每个地点增加 `earliest` / `latest` / `service_minutes`，并把本地优化器替换为带时间窗的 VRP 求解器；Google Routes API 的 `optimizeWaypointOrder` 本身不处理时间窗。
