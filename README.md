# Optiway

> 多点路线优化 H5 Demo —— 验证「多个地点的拜访顺序优化 + 行程安排」需求能否落地。

一个可直接部署到 [FastAPI Cloud](https://fastapicloud.com) 的极简全栈 demo：FastAPI 提供路线优化 API，原生移动端 H5（Leaflet）提供地图与交互。**不需要数据库、登录、前端构建或 Docker**。

## 能验证什么

- 输入起点、终点与最多 10 个途经点，自动计算更省时的拜访顺序。
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

返回服务状态、默认数据源、Google 是否已配置、途经点上限。

### `GET /api/places`

返回内置城市与推荐地点，用于 H5 的地点选择器。

### `POST /api/optimize`

请求示例：

```json
{
  "origin": { "name": "天安门广场", "lat": 39.9087, "lng": 116.3975 },
  "destination": { "name": "南锣鼓巷", "lat": 39.9376, "lng": 116.4032 },
  "intermediates": [
    { "name": "故宫博物院", "lat": 39.9163, "lng": 116.3972 },
    { "name": "景山公园", "lat": 39.9251, "lng": 116.3967 },
    { "name": "北海公园", "lat": 39.9254, "lng": 116.3891 },
    { "name": "什刹海", "lat": 39.9403, "lng": 116.383 }
  ],
  "travel_mode": "DRIVE",
  "optimize": true,
  "provider": "auto"
}
```

- `travel_mode`: `DRIVE` | `WALK` | `BICYCLE`
- `provider`: `auto` | `google` | `osrm` | `local`（省略时使用服务端默认值）
- `optimize`: 是否优化途经点顺序；起点和终点始终固定。

命令行验证（离线、无网络依赖）：

```bash
curl -s http://127.0.0.1:8000/api/optimize \
  -H 'Content-Type: application/json' \
  -d '{
    "origin": {"name": "A", "lat": 39.9087, "lng": 116.3975},
    "destination": {"name": "D", "lat": 39.9376, "lng": 116.4032},
    "intermediates": [
      {"name": "C", "lat": 39.9251, "lng": 116.3967},
      {"name": "B", "lat": 39.9163, "lng": 116.3972}
    ],
    "provider": "local"
  }'
```

响应中的关键字段：

- `provider` / `provider_label`：实际使用的数据源及展示名称；
- `optimized`：是否执行了顺序优化；
- `stops`：按最终顺序排列的站点，包含每段里程、耗时和累计耗时；
- `total_distance_meters` / `total_duration_seconds`：总里程与总耗时；
- `geometry`：`[lng, lat]` 坐标数组，可直接交给地图绘制；
- `optimized_indices`：优化后的途经点在原始输入中的下标；
- `fallback_reason`：`auto` 模式发生降级时的原因。

## 项目结构

```text
app/
├── main.py              # FastAPI 应用与静态页面托管
├── api.py               # /api/health、/api/places、/api/optimize
├── routing.py           # 数据源选择与自动降级
├── config.py            # 环境变量配置
├── schemas.py           # Pydantic 请求/响应模型
├── places.py            # 内置城市与推荐地点
├── providers/
│   ├── google.py        # Google Routes API + polyline 解码
│   ├── osrm.py          # OSRM route/trip 服务
│   └── local.py         # Haversine + Held-Karp 本地模拟
└── static/
    ├── index.html
    ├── styles.css
    ├── app.js
    └── vendor/leaflet/  # 本地化的 Leaflet 资源
tests/                   # pytest 单元测试与 API 测试
pyproject.toml           # 依赖与 [tool.fastapi] entrypoint
```

## 开发与测试

```bash
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

更多说明见 [development.md](./development.md)。

## 设计取舍与限制

- **最多 10 个途经点**：为移动端交互和公共 OSRM 实例负载设置的上限，可通过 `MAX_INTERMEDIATES` 调整。Google Routes API 本身支持更多途经点。
- **OSRM 公共实例仅驾车**：步行/骑行在未配置 Google 时会回退到本地模拟，并在界面上提示。
- **本地模拟是直线距离**：只用于验证排序逻辑和交互流程，不代表真实道路里程。
- **暂未包含地址搜索**：当前支持推荐地点、地图选点、坐标输入。接入 Google Places/Geocoding 或高德地名搜索即可补齐。
- **底图可配置**：默认使用 OpenStreetMap 德国镜像（在更多网络下可访问），通过 `MAP_TILE_URL` / `MAP_TILE_ATTRIBUTION` 可切换为其他 OSM 镜像、自建瓦片或已授权的地图服务。生产环境请遵守所选瓦片服务的条款。
- **这是集成验证 demo**：没有数据库、用户体系、权限、持久化和订单/时间窗约束。生产化时应把路线结果、人员与时间窗持久化，并加入并发限流与缓存。

## License

MIT
