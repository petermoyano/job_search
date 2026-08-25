from contextlib import asynccontextmanager
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import get_settings
from app.documents.api import router as documents_router
from app.documents.resume_api import router as resume_profiles_router
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


@app.middleware("http")
async def log_http_request(request: Request, call_next):
    if request.url.path == "/health":
        return await call_next(request)

    request_id = (request.headers.get("x-request-id") or "").strip()
    if (
        not request_id
        or len(request_id) > 128
        or not request_id.isascii()
        or not request_id.isprintable()
    ):
        request_id = uuid4().hex
    started_at = perf_counter()
    LOGGER.info(
        "event=http_request_started request_id=%s method=%s path=%s",
        request_id,
        request.method,
        request.url.path,
    )
    try:
        response = await call_next(request)
    except Exception:
        LOGGER.exception(
            "event=http_request_failed request_id=%s method=%s path=%s "
            "duration_ms=%.2f",
            request_id,
            request.method,
            request.url.path,
            (perf_counter() - started_at) * 1000,
        )
        return JSONResponse(
            status_code=500,
            content={"detail": "El servidor no pudo completar la solicitud."},
            headers={"X-Request-ID": request_id},
        )

    response.headers["X-Request-ID"] = request_id
    LOGGER.info(
        "event=http_request_completed request_id=%s method=%s path=%s "
        "status_code=%s duration_ms=%.2f",
        request_id,
        request.method,
        request.url.path,
        response.status_code,
        (perf_counter() - started_at) * 1000,
    )
    return response


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_origin_regex=settings.cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Request-ID"],
)
app.include_router(router)
app.include_router(documents_router)
app.include_router(resume_profiles_router)
