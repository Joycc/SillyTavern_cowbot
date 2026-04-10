from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from weixin.weixin_channel import WeixinEngine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

engine = WeixinEngine()
_engine_thread: threading.Thread | None = None


class SendRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _engine_thread

    _engine_thread = threading.Thread(target=engine.startup, daemon=True, name="weixin-engine")
    _engine_thread.start()
    logger.info("Weixin engine thread started")

    try:
        yield
    finally:
        engine.stop()
        if _engine_thread and _engine_thread.is_alive():
            _engine_thread.join(timeout=3)
        logger.info("Weixin engine stopped")


app = FastAPI(title="Weixin Sidecar Bridge", version="1.0.0", lifespan=lifespan)


@app.get("/api/qrcode")
def get_qrcode() -> dict:
    return {
        "status": engine.login_status,
        "base64": engine.current_qr_base64,
    }


@app.post("/api/send")
def send_message(payload: SendRequest) -> dict:
    try:
        engine.send_text(payload.user_id, payload.content)
        return {"ok": True}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@app.get("/health")
def health() -> dict:
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
