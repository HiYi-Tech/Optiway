from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app import __version__
from app.api import router
from app.config import settings

APP_DIR = Path(__file__).resolve().parent
STATIC_DIR = APP_DIR / "static"

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=__version__,
    description=(
        "多点路线优化 demo：输入起点、终点和途经点，返回优化后的拜访顺序、"
        "里程、耗时和路线几何。支持 Google Routes、OSRM 公共演示服务和本地模拟。"
    ),
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
app.include_router(router)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/favicon.svg", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(STATIC_DIR / "favicon.svg")
