from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from weixin.weixin_channel import WeixinEngine

# 1. 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)
logger = logging.getLogger(__name__)

# ==========================================
# 2. 全局消息队列 (核心枢纽)
# ==========================================
wechat_message_queue = []

engine = WeixinEngine()
_engine_thread: threading.Thread | None = None

class SendRequest(BaseModel):
    user_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1)

# 3. 生命周期管理 (启动/关闭引擎)
@asynccontextmanager
async def lifespan(_: FastAPI):
    global _engine_thread
    
    # 【神级操作】：把全局队列直接挂载到 engine 对象上
    # 这样底层收到消息就能直接塞进来，不需要来回传参
    engine.message_queue = wechat_message_queue 

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

# 4. 初始化 FastAPI
app = FastAPI(title="Weixin Sidecar Bridge", version="1.0.0", lifespan=lifespan)

# 5. CORS 跨域配置 (解决前端 fetch 时的 403 / CORS 拦截)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 允许所有局域网/本地前端访问
    allow_credentials=True,
    allow_methods=["*"],  # 允许 GET, POST 等
    allow_headers=["*"],
)

# 6. API 路由
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

@app.get("/api/queue")
async def get_message_queue():
    global wechat_message_queue
    
    # 将队列中的消息拿出来
    current_messages = list(wechat_message_queue)
    # 立刻清空队列，防止下次轮询时拿到重复消息
    wechat_message_queue.clear()
    
    # 打印日志：让你在黑框框里清楚看到哪条消息被酒馆前端拿走了
    for msg in current_messages:
        logger.info(f"📤 [队列拉取] 酒馆已成功取走消息 -> 发送者: {msg['user_id']} | 内容: {msg['content']}")
        
    return current_messages

@app.get("/health")
def health() -> dict:
    return {"ok": True}

# 7. 启动入口
if __name__ == "__main__":
    import uvicorn
    # 保持运行在 8080 端口，与你的前端配置一致
    uvicorn.run(app, host="127.0.0.1", port=8080)