import logging
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.validation import router

logging.basicConfig(
    level=getattr(logging, os.environ.get("LOG_LEVEL", "INFO").upper(), logging.INFO),
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%H:%M:%S",
)
# Silenciar librerías HTTP que volcarían base64 en sus propios DEBUG logs.
for _noisy in ("httpx", "httpcore", "anthropic", "openai", "google", "urllib3"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)

app = FastAPI(
    title="Packaging Validator",
    description="Validación de packaging — comparación artwork vs embalaje físico.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173",
                   "http://localhost:5174", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.get("/metrics", include_in_schema=False)
async def metrics_root() -> dict:
    from app.services.metrics import get_summary
    return get_summary()
