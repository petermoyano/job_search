from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router
from app.db.base import Base
from app.db.session import engine


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Direct Product Job Radar",
    version="0.1.0",
    description="Backend-only MVP for transparent direct-product job opportunity analysis.",
    lifespan=lifespan,
)
app.include_router(router)
