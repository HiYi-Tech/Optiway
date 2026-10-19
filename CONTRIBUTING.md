# Contributing

这是一个用于验证多点路线优化需求的 demo 项目，保持简单、可运行、无需数据库。

## 本地检查

```bash
uv sync
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy app
```

## 代码约定

- 后端：FastAPI + Pydantic，类型标注完整；外部服务调用统一放在 `app/providers/`。
- 前端：原生 HTML/CSS/JS，不引入构建步骤；Leaflet 资源本地化。
- 新增数据源时实现 `OptimizeResponse` 返回格式，并在 `app/routing.py` 的 `auto` 回退链中注册。
- 不要在仓库中提交 API Key；本地使用 `.env`，云端使用 FastAPI Cloud 环境变量。

## 提交前

- 确认 `auto` 模式在无 Key、无外网的情况下仍能降级到本地模拟；
- 如果修改了 API 请求/响应结构，同步更新 README 与前端。
