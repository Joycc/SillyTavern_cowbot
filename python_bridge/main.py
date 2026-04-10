from __future__ import annotations

import base64
import threading
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

import itchat
from fastapi import FastAPI


class WechatStatus(str, Enum):
    WAITING_QR = "WAITING_QR"
    SCANNING = "SCANNING"
    LOGGED_IN = "LOGGED_IN"


@dataclass
class SharedState:
    status: WechatStatus = WechatStatus.WAITING_QR
    qr_data: str = ""
    last_qr_status_code: Optional[int] = None
    running: bool = False
    lock: threading.RLock = field(default_factory=threading.RLock)

    def snapshot(self) -> dict:
        with self.lock:
            return {
                "status": self.status.value,
                "qr_data": self.qr_data,
            }


class WechatEngine:
    def __init__(self, state: SharedState):
        self.state = state
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            print("[wechat_engine] thread already running", flush=True)
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="wechat-engine-thread",
            daemon=True,
        )
        self._thread.start()
        with self.state.lock:
            self.state.running = True
        print("[wechat_engine] thread started", flush=True)

    def stop(self) -> None:
        self._stop_event.set()
        try:
            itchat.logout()
        except Exception:
            pass

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)

        with self.state.lock:
            self.state.running = False
        print("[wechat_engine] thread stopped", flush=True)

    def _run(self) -> None:
        try:
            print("[wechat_engine] calling itchat.auto_login(...)", flush=True)
            itchat.auto_login(
                hotReload=True,
                enableCmdQR=False,
                qrCallback=self._on_qr_event,
                loginCallback=self._on_login,
                exitCallback=self._on_exit,
            )
            print("[wechat_engine] auto_login returned, starting itchat.run", flush=True)

            # 使用非阻塞 run，便于由 FastAPI 生命周期控制退出
            try:
                itchat.run(blockThread=False)
            except TypeError:
                # 兼容可能不支持 blockThread 参数的版本
                itchat.run()

            while not self._stop_event.is_set():
                time.sleep(0.5)
        except Exception as exc:
            print(f"[wechat_engine] fatal error: {exc}", flush=True)
            with self.state.lock:
                self.state.status = WechatStatus.WAITING_QR

    def _on_qr_event(self, uuid: str, status: int, qrcode: bytes) -> None:
        # itchat 常见状态：0/1(等待扫码)、201(已扫码待确认)、200(确认登录)
        qr_base64 = base64.b64encode(qrcode).decode("utf-8") if qrcode else ""

        with self.state.lock:
            self.state.last_qr_status_code = status
            if status in (201,):
                self.state.status = WechatStatus.SCANNING
            elif status in (200,):
                self.state.status = WechatStatus.LOGGED_IN
            else:
                self.state.status = WechatStatus.WAITING_QR

            if qr_base64:
                self.state.qr_data = qr_base64

        print(
            f"[wechat_engine] qrCallback status={status} uuid={uuid} qr_len={len(qr_base64)}",
            flush=True,
        )

    def _on_login(self) -> None:
        with self.state.lock:
            self.state.status = WechatStatus.LOGGED_IN
        print("[wechat_engine] loginCallback => LOGGED_IN", flush=True)

    def _on_exit(self) -> None:
        with self.state.lock:
            self.state.status = WechatStatus.WAITING_QR
        print("[wechat_engine] exitCallback => WAITING_QR", flush=True)


state = SharedState()
engine = WechatEngine(state)


@asynccontextmanager
async def lifespan(_: FastAPI):
    engine.start()
    try:
        yield
    finally:
        engine.stop()


app = FastAPI(
    title="SillyTavern WeChat Python Bridge (itchat-uos)",
    version="1.0.0",
    lifespan=lifespan,
)


@app.get("/api/status")
def get_status() -> dict:
    return state.snapshot()


@app.get("/health")
def health() -> dict:
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8080)
