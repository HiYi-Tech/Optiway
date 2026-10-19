# Optiway

> 多点路线优化 H5 Demo —— 验证「多个地点的拜访顺序优化 + 行程安排」需求能否落地。

一个可直接部署到 [FastAPI Cloud](https://fastapicloud.com) 的极简全栈 demo：FastAPI 提供路线优化 API，原生移动端 H5（Leaflet）提供地图与交互。**不需要数据库、登录、前端构建或 Docker**。

## 能验证什么

- **默认仅固定起点**：系统对起点之后的全部点位排序，并自动选择最后一站；也可以切换为固定终点模式。
- 输入起点与最多 10 个拜访点，自动计算更省时的拜访顺序。
- 展示优化后的站点顺序、总里程、总耗时、分段里程/耗时与累计耗时。
- 在地图上显示真实道路路线或直线示意，支持点击地图选点。
- 三种数据源可切换：Google Routes、OSRM 公共演示服务、本地模拟。
- 推荐地点（北京/上海/广州/深圳/杭州/成都）、手动坐标、浏览器定位。
- 移动端优先布局，桌面端自动切换为地图 + 表单双栏。

## 路线数据源

| 数据源 | 需要 Key | 路线几何 | 顺序优化 | 说明 |
| --- | --- | --- | --- | --- |
| Google Routes API | 是 | 真实道路 | `optimizeWaypointOrder` | 驾车模式使用实时路况；需要启用 Routes API 和结算账号 |
| OSRM 公共演示服务 | 否 | 真实道路 | `/trip` 服务 | 仅支持驾车；公共实例有公平使用限制，不保证 SLA |
| 本地模拟 | 否 | 直线示意 | Held-Karp 精确求解 | 完全离线；按平均速度估算耗时，仅用于验证排序逻辑 |

> Google `computeRoutes` 本身要求固定终点。开放路线模式下，系统先用本地精确算法选择最后一站，再由 Google 优化其余点位顺序；OSRM `/trip` 和本地算法则直接支持“只固定起点”的开放路径。

`auto`（默认）的解析顺序：

1. 配置了 `GOOGLE_MAPS_API_KEY` → 优先 Google Routes；
2. 否则使用 OSRM 公共演示服务；
3. 上述服务不可用时自动降级到本地模拟，并在结果中展示降级原因。

## 快速开始

前置条件：[uv](https://docs.astral.sh/uv/)（会自动安装 `.python-version` 指定的 Python 3.14）。

```bash
uv sync
uv run fastapi dev
```

打开 <http://127.0.0.1:8000>，交互式 API 文档在 <http://127.0.0.1:8000/docs>。

页面加载后会载入北京示例路线，点击「开始优化行程」即可看到效果，无需任何密钥。

### 可选：启用 Google Routes

```bash
cp .env.example .env
# 编辑 .env，填入 GOOGLE_MAPS_API_KEY
uv run fastapi dev
```

在 Google Cloud 中启用 **Routes API** 并绑定结算账号。Google 服务在部分网络环境下不可达；`auto` 模式会自动回退，不影响 demo 演示。

## 一键部署到 FastAPI Cloud

```bash
uv run fastapi login    # 浏览器登录 / 注册
uv run fastapi deploy   # 从仓库根目录部署
```

首次部署时：

- 选择或创建一个 App；
- **Application Directory 留空**（应用就在仓库根目录）；
- 不需要数据库、Redis 或其他集成；
- 不需要配置任何环境变量即可运行（自动使用 OSRM / 本地模拟）。

部署完成后访问 CLI 输出的 `https://<app>.fastapicloud.dev` 即可。静态 H5 由 FastAPI 直接托管，没有额外构建步骤。

### 可选：在云端配置 Google Key

```bash
uv run fastapi cloud env set GOOGLE_MAPS_API_KEY <your-key> --secret
```

然后在 Dashboard 中重新部署，或再次执行 `uv run fastapi deploy`。也可以直接在 FastAPI Cloud Dashboard 的 **Environment Variables** 中添加。

更多细节见 [deployment.md](./deployment.md)。

## API

### `GET /api/health`

返回服务状态、默认数据源、Google 是否已配置、点位上限。

### `GET /api/places`

返回内置城市与推荐地点，用于 H5 的地点选择器。

### `POST /api/optimize`

开放路线请求示例（默认，仅固定起点）：

```json
{
  "origin": { "name": "天安门广场", "lat": 39.9087, "lng": 116.3975 },
  "end_mode": "open",
  "intermediates": [
    { "name": "故宫博物院", "lat": 39.9163, "lng": 116.3972 },
    { "name": "景山公园", "lat": 39.9251, "lng": 116.3967 },
    { "name": "北海公园", "lat": 39.9254, "lng": 116.3891 },
    { "name": "什刹海", "lat": 39.9403, "lng": 116.383 },
    { "name": "南锣鼓巷", "lat": 39.9376, "lng": 116.4032 }
  ],
  "travel_mode": "DRIVE",
  "optimize": true,
  "provider": "auto"
}
```

- `end_mode`:
  - `open`（默认）：仅固定起点，`intermediates` 中的全部点位由算法排序，最后一站也由算法选择；此时不能提供 `destination`。
  - `fixed`：起点和终点固定，只优化 `intermediates` 的顺序；此时必须提供 `destination`。
- `travel_mode`: `DRIVE` | `WALK` | `BICYCLE`
- `provider`: `auto` | `google` | `osrm` | `local`（省略时使用服务端默认值）
- `optimize`: 是否优化顺序；关闭后保持输入顺序（开放模式下最后一站为输入中的最后一个点位）。

固定终点模式请求示例：

```json
{
  "origin": { "name": "天安门广场", "lat": 39.9087, "lng": 116.3975 },
  "end_mode": "fixed",
  "destination": { "name": "南锣鼓巷", "lat": 39.9376, "lng": 116.4032 },
  "intermediates": [
    { "name": "故宫博物院", "lat": 39.9163, "lng": 116.3972 },
    { "name": "北海公园", "lat": 39.9254, "lng": 116.3891 }
  ],
  "provider": "auto"
}
```

命令行验证开放路线（离线、无网络依赖）：

```bash
curl -s http://127.0.0.1:8000/api/optimize \
  -H 'Content-Type: application/json' \
  -d '{
    "origin": {"name": "A", "lat": 39.9087, "lng": 116.3975},
    "end_mode": "open",
    "intermediates": [
      {"name": "C", "lat": 39.9251, "lng": 116.3967},
      {"name": "B", "lat": 39.9163, "lng": 116.3972}
    ],
    "provider": "local"
  }'
```

响应中的关键字段：

- `provider` / `provider_label`：实际使用的数据源及展示名称；
- `end_mode`：实际执行的路线模式；
- `optimized`：是否执行了顺序优化；
- `stops`：按最终顺序排列的站点，包含每段里程、耗时和累计耗时；
- `total_distance_meters` / `total_duration_seconds`：总里程与总耗时；
- `geometry`：`[lng, lat]` 坐标数组，可直接交给地图绘制；
- `optimized_indices`：排序后非起点点位在原始输入中的下标。开放模式包含算法选择的最后一站；固定模式只包含中间点位；
- `fallback_reason`：`auto` 模式发生降级时的原因。

## 项目结构

```text
app/
├── main.py              # FastAPI 应用与静态页面托管
├── api.py               # /api/health、/api/places、/api/optimize
├── routing.py           # 数据源选择与自动降级
├── tsp.py               # Haversine + Held-Karp（固定终点 / 开放路径）
├── config.py            # 环境变量配置
├── schemas.py           # Pydantic 请求/响应模型
├── places.py            # 内置城市与推荐地点
├── providers/
│   ├── google.py        # Google Routes API + polyline 解码
│   ├── osrm.py          # OSRM route/trip 服务
│   └── local.py         # 本地模拟与开放路线
└── static/
    ├── index.html
    ├── styles.css
    ├── app.js
    └── vendor/leaflet/  # 本地化的 Leaflet 资源
tests/                   # pytest 单元测试与 API 测试
pyproject.toml           # 依赖与 [tool.fastapi] entrypoint
```

## 技术实现

这一节按「前端调用 API → 后端访问数据源 → 前端把返回结果画到地图上」的链路说明实现细节，便于开发人员快速上手。

### API 调用

**前端如何调用后端**（`app/static/app.js`）

页面加载时通过 `fetch` 并行请求两个接口：

- `GET /api/health`：读取 `google_configured`（决定 Google 选项是否可用）、`default_provider`，以及 `map_tile_url` / `map_tile_attribution` / `map_tile_max_zoom`（用于初始化底图）。请求失败时顶部状态徽标显示「后端未连接」。
- `GET /api/places`：读取内置城市与推荐地点；失败时回退到 `app.js` 内的 `FALLBACK_CITIES`，页面仍可操作。

另外，`app.js` 顶部的 `MAX_INTERMEDIATES = 10` 是后端 `MAX_INTERMEDIATES` 的镜像常量，调整上限时两处需要同步。

点击「开始优化行程」后，`runOptimize()` 组装 JSON 并 `POST /api/optimize`：

```js
const payload = {
  origin: { name, lat, lng },
  end_mode: state.endMode,        // "open" | "fixed"
  intermediates: [...],
  travel_mode: state.travelMode,  // "DRIVE" | "WALK" | "BICYCLE"
  optimize: state.optimize,
  provider: state.provider,       // "auto" | "google" | "osrm" | "local"
};
if (state.endMode === "fixed") payload.destination = { name, lat, lng };
```

开放模式不发送 `destination`，固定模式才发送。请求期间 `setBusy(true)` 禁用表单并显示 spinner；成功后用 `renderResult(data)` 更新统计与站点列表、用 `drawResult(data)` 重绘地图；失败时 `extractError()` 读取 FastAPI 的 `detail` 字段并 toast 提示。

**后端如何调用数据源**（`app/providers/`）

`POST /api/optimize` 先由 `app/schemas.py` 的 Pydantic 模型校验 `end_mode` 与 `destination` 的互斥关系，再检查 `MAX_INTERMEDIATES` 上限，最后由 `app/routing.py` 分派：

- **Google Routes**（`google.py`）：`httpx.AsyncClient.post()` 调用
  `https://routes.googleapis.com/directions/v2:computeRoutes`。
  - Header：`X-Goog-Api-Key`、`X-Goog-FieldMask`（仅请求 `duration`、`distanceMeters`、`encodedPolyline`、`optimizedIntermediateWaypointIndex`、`legs`）、`X-Server-Timeout`。
  - Body：`origin` / `destination` / `intermediates` 统一为 `{location: {latLng: {latitude, longitude}}}`；`optimizeWaypointOrder` 控制是否让 Google 排序；驾车模式附加 `routingPreference: "TRAFFIC_AWARE"`。
  - 开放路线适配：`computeRoutes` 必须提供 destination，因此先用本地 `optimal_open_order()` 选出末站作为 destination，其余点位作为 intermediates 交给 Google；返回后再把 Google 的局部下标映射回原始输入下标。
- **OSRM**（`osrm.py`）：`httpx.AsyncClient.get()` 调用
  `{OSRM_BASE_URL}/trip/v1/driving/{lng,lat;lng,lat;...}`（不优化或点数 ≤ 2 时改用 `/route/`）。
  - 固定终点：`roundtrip=false&source=first&destination=last`；
  - 开放路线：`roundtrip=false&source=first`，不传 `destination`，由 OSRM 自行选择最后一站；
  - 固定参数：`geometries=geojson&overview=simplified&steps=false`。
- **本地模拟**（`local.py`）：不发起网络请求，直接用 `app/tsp.py` 的 Haversine + Held-Karp（`O(2^n·n²)`，最多 10 个点位）求解顺序，按平均速度估算耗时（驾车 32 / 步行 4.8 / 骑行 15 km/h）。
- **auto 降级**（`routing.py`）：已配置 Key 时先试 Google，否则直接试 OSRM；两者都失败则回退本地模拟，错误信息汇总到 `fallback_reason` 一并返回。

三种实现最终都产出同构的 `OptimizeResponse`，前端不需要关心实际数据源。`GOOGLE_MAPS_API_KEY` 只在服务端读取，不会下发到浏览器。

### 地图实现

- Leaflet 1.9.4 已本地化到 `app/static/vendor/leaflet/`，`index.html` 用普通 `<script>` 引入，无 CDN、无构建步骤。
- `app.js` 启动时创建地图，缩放控件放在右下角：

```js
const map = L.map("map", { zoomControl: false, attributionControl: false })
  .setView(DEFAULT_CENTER, 12);
L.control.zoom({ position: "bottomright" }).addTo(map);
```

- 底图是标准 `L.tileLayer`，瓦片地址、最大缩放和署名来自 `/api/health`（对应 `MAP_TILE_URL` 等环境变量），默认使用 OpenStreetMap 德国镜像。`tileerror` 只提示「底图加载失败，路线仍可正常显示」，不会阻断路线绘制。
- 地图上挂三个 `L.layerGroup`，每次渲染前先 `clearLayers()`，互不干扰：
  - `previewLayer`：编辑阶段的预览（虚线 + 起/途经/终标记）；
  - `routeLayer`：优化结果（真实路径 + 有序站点标记）；
  - `meLayer`：浏览器定位得到的当前位置圆点。
- 站点图标用 `L.divIcon` + CSS 绘制（`makeIcon(label, kind)`），不依赖图片资源；`kind` 为 `start` / `stop` / `end` 决定配色，`label` 是「起」「终」或途经序号。

### 根据 API 返回绘制路径

后端在三种数据源中把几何统一成 `geometry: [[lng, lat], ...]`：

- **Google**：`decode_polyline()` 解码 `polyline.encodedPolyline`，把 Google 的 1e5 定点编码还原为 `[lng, lat]`；
- **OSRM**：`geometries=geojson` 返回的 `geometry.coordinates` 本身就是 `[lng, lat]`（`/trip` 取 `trips[0]`，`/route` 取 `routes[0]`）；
- **本地模拟**：用相邻站点坐标构造直线段。

任一路径缺少几何时，后端都会退化为「按最终顺序连接各站点」的直线，保证前端始终有可画的数据。

前端 `drawResult(data)` 的绘制过程：

1. **坐标顺序转换**：Leaflet 使用 `[lat, lng]`，而后端统一返回 `[lng, lat]`，因此这里要反转并过滤非法值：

```js
const latlngs = (data.geometry || [])
  .map(([lng, lat]) => [Number(lat), Number(lng)])
  .filter(([lat, lng]) => Number.isFinite(lat) && Number.isFinite(lng));
```

2. **绘制折线**：先画一条 10px 白色描边，再叠加一条 5px 橙色主线，形成高对比的「描边 + 芯线」效果；`lineCap` / `lineJoin` 设为 `round`，让转弯处更自然：

```js
L.polyline(latlngs, {
  color: "#ffffff", weight: 10, opacity: 0.9,
  lineCap: "round", lineJoin: "round",
}).addTo(routeLayer);
L.polyline(latlngs, {
  color: "#e4572e", weight: 5, opacity: 0.96,
  lineCap: "round", lineJoin: "round",
}).addTo(routeLayer);
```

3. **按最终顺序打点**：遍历 `data.stops`（后端已按优化后的顺序排列），根据 `stop.role`（`origin` / `intermediate` / `destination`）生成「起」、序号或「终」图标；每个 marker 绑定 popup，显示站名和「上一站到此」的分段里程、耗时。
4. **自动取景**：用 `map.fitBounds(L.latLngBounds(latlngs), { padding..., maxZoom: 15 })` 让整条路线落入可视区域；结果面板展开后延迟调用 `map.invalidateSize()`，避免容器尺寸变化导致地图错位。

编辑地点时的 `renderPreview()` 使用另一套逻辑：按当前输入顺序（不做优化）把点位连成橙色虚线，只用于展示分布；发起优化后，`drawResult()` 会先清空预览层和旧路线，再绘制结果。

### 测试与质量

- `tests/test_api.py`：通过 `TestClient` 覆盖健康检查、地点库、两种模式的参数校验与本地路线。
- `tests/test_local_optimizer.py`：Haversine 距离、固定终点排序、开放路径排序。
- `tests/test_provider_parsing.py`：直接调用 Google/OSRM 的解析函数，用固定 JSON 样本验证顺序映射、末站选择与降级逻辑，不发起真实网络请求。
- `tests/test_polyline.py`：Google polyline 解码。
- 质量门槛：`ruff check`、`ruff format --check`、`mypy --strict`（见 `pyproject.toml`），配置为 Python 3.14。

## 开发与测试

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

更多说明见 [development.md](./development.md)。

## 设计取舍与限制

- **最多 10 个拜访点/途经点**：为移动端交互和公共 OSRM 实例负载设置的上限，可通过 `MAX_INTERMEDIATES` 调整。Google Routes API 本身支持更多点位。
- **开放路线与固定终点**：默认开放路线只固定起点，算法会同时决定点位顺序和最后一站；固定终点模式则保留原有的“起终点固定、只排中间点位”行为。
- **Google 开放路线的终点选择**：Google Routes `computeRoutes` 要求固定终点，因此开放模式下先用本地精确算法选出最后一站，再由 Google 优化其余点位；结果可能不是 Google 路网下的全局最优终点组合。
- **OSRM 公共实例仅驾车**：步行/骑行在未配置 Google 时会回退到本地模拟，并在界面上提示。
- **本地模拟是直线距离**：只用于验证排序逻辑和交互流程，不代表真实道路里程。
- **暂未包含地址搜索**：当前支持推荐地点、地图选点、坐标输入。接入 Google Places/Geocoding 或高德地名搜索即可补齐。
- **底图可配置**：默认使用 OpenStreetMap 德国镜像（在更多网络下可访问），通过 `MAP_TILE_URL` / `MAP_TILE_ATTRIBUTION` 可切换为其他 OSM 镜像、自建瓦片或已授权的地图服务。生产环境请遵守所选瓦片服务的条款。
- **这是集成验证 demo**：没有数据库、用户体系、权限、持久化和订单/时间窗约束。生产化时应把路线结果、人员与时间窗持久化，并加入并发限流与缓存。

## License

MIT
