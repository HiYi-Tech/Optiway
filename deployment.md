# 部署到 FastAPI Cloud

本项目是单仓库根目录应用：FastAPI 同时提供 API 和静态 H5 页面。部署只需要两条命令：

```bash
uv run fastapi login
uv run fastapi deploy
```

## 首次部署

1. 在仓库根目录执行 `uv run fastapi login`，按提示在浏览器完成登录或注册。
2. 执行 `uv run fastapi deploy`。
3. CLI 会让你选择团队，并创建或关联一个 FastAPI Cloud App。
4. **Application Directory 留空**。本项目没有 `backend/` 子目录，应用入口由 `pyproject.toml` 的 `[tool.fastapi]` 指定：

   ```toml
   [tool.fastapi]
   entrypoint = "app.main:app"
   ```

5. 不需要创建数据库、Redis 或其他集成，也不需要配置环境变量。

部署完成后，CLI 会输出应用地址，通常是：

- 应用与 H5：`https://<app>.fastapicloud.dev`
- API 文档：`https://<app>.fastapicloud.dev/docs`

## 后续部署

在同一个目录再次执行：

```bash
uv run fastapi deploy
```

CLI 会复用 `.fastapicloud/` 中的关联信息，打包、构建并零停机发布。该目录已被 `.gitignore` 忽略。

## 环境变量

不配置任何变量也能运行。默认 `ROUTE_PROVIDER=auto`：

- 没有 Google Key 时使用 OSRM 公共演示服务；
- OSRM 不可用时自动降级到本地模拟。

### 启用 Google Routes

在 Google Cloud 中启用 **Routes API**，准备一个 API Key，然后：

```bash
uv run fastapi cloud env set GOOGLE_MAPS_API_KEY <your-key> --secret
uv run fastapi deploy
```

也可以登录 FastAPI Cloud Dashboard，在 App 的 **Environment Variables** 页面添加，并选择 **Save and Redeploy**。

可选的变量：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `ROUTE_PROVIDER` | `auto` | `auto` / `google` / `osrm` / `local` |
| `GOOGLE_MAPS_API_KEY` | 空 | Google Routes API Key |
| `OSRM_BASE_URL` | `https://router.project-osrm.org` | 自建 OSRM 时可替换 |
| `HTTP_TIMEOUT_SECONDS` | `15` | 外部路线服务超时时间 |
| `MAP_TILE_URL` | OpenStreetMap Germany | 底图瓦片 URL 模板，可按需切换 |
| `MAP_TILE_ATTRIBUTION` | OSM 署名 | 底图署名，切换瓦片时同步修改 |
| `MAP_TILE_MAX_ZOOM` | `19` | 底图最大缩放级别 |

> Google 服务在部分网络环境下不可达。未配置 Key 或调用失败时，`auto` 模式会自动回退，页面仍可演示。

## 可选：GitHub Actions 持续部署

如果希望 push 到 `master` 自动部署，可以在 FastAPI Cloud 中生成 Deploy Token，并把 `FASTAPI_CLOUD_TOKEN`、`FASTAPI_CLOUD_APP_ID` 配置为 GitHub Repository Secrets。工作流核心步骤：

```yaml
- uses: actions/checkout@v4
- uses: astral-sh/setup-uv@v5
- run: uv sync
- run: uv run fastapi deploy
  env:
    FASTAPI_CLOUD_TOKEN: ${{ secrets.FASTAPI_CLOUD_TOKEN }}
    FASTAPI_CLOUD_APP_ID: ${{ secrets.FASTAPI_CLOUD_APP_ID }}
```

也可以直接运行：

```bash
uv run fastapi cloud setup-ci --app-id <your-app-id>
```

该命令会帮助生成或更新 GitHub Actions 配置。

## 常见问题

**`App not found`**

当前登录账号与 App 所属账号不一致，或本地 `.fastapicloud/` 关联了其他 App。可以重新登录，或使用 `uv run fastapi cloud link` 关联正确的 App。

**部署成功但页面没有数据源**

检查 `https://<app>.fastapicloud.dev/api/health`：

- `google_configured` 为 `false` 且 OSRM 不可达时，`auto` 会降级到本地模拟；
- 结果中的 `fallback_reason` 会说明具体原因。

**Google 请求报 403**

确认 Google Cloud 项目已启用 Routes API、API Key 没有来源限制，并且已绑定结算账号。

**OSRM 请求超时**

公共演示实例可能限流或不可达。重试、切换到本地模拟，或部署自建 OSRM 并通过 `OSRM_BASE_URL` 指向它。
