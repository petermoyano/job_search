from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine


LOGGER = logging.getLogger(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)
logging.getLogger("app").setLevel(logging.INFO)

settings = get_settings()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if settings.initialize_database:
        LOGGER.info("Initializing database schema")
        Base.metadata.create_all(bind=engine)
    else:
        LOGGER.info("Skipping database schema initialization")
    yield


app = FastAPI(
    title="Direct Product Job Radar",
    version="0.1.0",
    description="Backend-only MVP for transparent direct-product job opportunity analysis.",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
