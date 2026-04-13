"""
Weixin long-poll engine (framework-independent).

职责：
- 处理二维码登录与 token 持久化
- 轮询 getUpdates 接收消息
- 将文本消息存入本地消息队列供前端拉取 (已剥离对 ST 后端的直接依赖)
- 提供 send_text 能力回发消息
"""

from __future__ import annotations

import json
import logging
import os
import threading
import time
from typing import Optional

from weixin.weixin_api import CDN_BASE_URL, DEFAULT_BASE_URL, WeixinApi
from weixin.weixin_message import WeixinMessage

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_FAILURES = 3
BACKOFF_DELAY = 30
RETRY_DELAY = 2
SESSION_EXPIRED_ERRCODE = -14
QR_LOGIN_TIMEOUT_S = 480
QR_MAX_REFRESHES = 10


class WeixinEngine:
    LOGIN_STATUS_WAITING_QR = "WAITING_QR"
    LOGIN_STATUS_SCANNING = "SCANNING"
    LOGIN_STATUS_LOGGED_IN = "LOGGED_IN"

    def __init__(self):
        self.api: Optional[WeixinApi] = None
        self._stop_event = threading.Event()
        self._context_tokens: dict[str, str] = {}
        self._seen_msg_ids: set[str] = set()
        self._get_updates_buf = ""
        self._credentials_path = os.path.expanduser("~/.weixin_bridge_credentials.json")

        # 按要求暴露状态
        self.current_qr_base64 = ""
        self.status = self.LOGIN_STATUS_WAITING_QR
        self.login_status = self.LOGIN_STATUS_WAITING_QR

        self.base_url = DEFAULT_BASE_URL
        self.cdn_base_url = CDN_BASE_URL

    # ── lifecycle ───────────────────────────────────────────────────────

    def startup(self):
        self._stop_event.clear()

        token, base_url = self._load_or_login()
        if not token:
            logger.error("[WeixinEngine] login failed, engine startup aborted")
            return

        self.api = WeixinApi(base_url=base_url, token=token, cdn_base_url=self.cdn_base_url)
        self._set_status(self.LOGIN_STATUS_LOGGED_IN)
        logger.info("[WeixinEngine] startup success, entering poll loop")
        self._poll_loop()

    def stop(self):
        logger.info("[WeixinEngine] stop called")
        self._stop_event.set()

    # ── login ───────────────────────────────────────────────────────────

    def _set_status(self, value: str):
        self.status = value
        self.login_status = value

    def _load_credentials(self) -> dict:
        try:
            if os.path.exists(self._credentials_path):
                with open(self._credentials_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.warning(f"[WeixinEngine] load credentials failed: {e}")
        return {}

    def _save_credentials(self, data: dict):
        try:
            os.makedirs(os.path.dirname(self._credentials_path), exist_ok=True)
            with open(self._credentials_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            try:
                os.chmod(self._credentials_path, 0o600)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"[WeixinEngine] save credentials failed: {e}")

    def _load_or_login(self) -> tuple[str, str]:
        creds = self._load_credentials()
        token = creds.get("token", "")
        base_url = creds.get("base_url", self.base_url)

        if token:
            logger.info("[WeixinEngine] token loaded from credentials")
            return token, base_url

        result = self._qr_login(base_url)
        if not result:
            return "", ""
        return result["token"], result.get("base_url", base_url)

    def _qr_login(self, base_url: str) -> dict:
        api = WeixinApi(base_url=base_url)

        try:
            qr_resp = api.fetch_qr_code()
        except Exception as e:
            logger.error(f"[WeixinEngine] fetch_qr_code failed: {e}")
            return {}

        qrcode = qr_resp.get("qrcode", "")
        qrcode_img_content = qr_resp.get("qrcode_img_content", "")
        if not qrcode:
            logger.error("[WeixinEngine] missing qrcode in response")
            return {}

        self.current_qr_base64 = qrcode_img_content or ""
        self._set_status(self.LOGIN_STATUS_WAITING_QR)

        scanned_printed = False
        refresh_count = 0
        deadline = time.time() + QR_LOGIN_TIMEOUT_S

        while not self._stop_event.is_set():
            if time.time() >= deadline:
                logger.warning(f"[WeixinEngine] QR login timeout after {QR_LOGIN_TIMEOUT_S}s")
                return {}

            try:
                status_resp = api.poll_qr_status(qrcode)
            except Exception as e:
                logger.error(f"[WeixinEngine] poll_qr_status failed: {e}")
                return {}

            q_status = status_resp.get("status", "wait")
            if q_status == "wait":
                self._set_status(self.LOGIN_STATUS_WAITING_QR)

            elif q_status == "scaned":
                self._set_status(self.LOGIN_STATUS_SCANNING)
                if not scanned_printed:
                    logger.info("[WeixinEngine] QR scanned, waiting confirm")
                    scanned_printed = True

            elif q_status == "expired":
                refresh_count += 1
                if refresh_count >= QR_MAX_REFRESHES:
                    logger.warning("[WeixinEngine] QR expired too many times")
                    return {}
                try:
                    qr_resp = api.fetch_qr_code()
                    qrcode = qr_resp.get("qrcode", "")
                    qrcode_img_content = qr_resp.get("qrcode_img_content", "")
                    self.current_qr_base64 = qrcode_img_content or ""
                    self._set_status(self.LOGIN_STATUS_WAITING_QR)
                    scanned_printed = False
                except Exception as e:
                    logger.error(f"[WeixinEngine] refresh QR failed: {e}")
                    return {}

            elif q_status == "confirmed":
                bot_token = status_resp.get("bot_token", "")
                bot_id = status_resp.get("ilink_bot_id", "")
                result_base_url = status_resp.get("baseurl", base_url)

                if not bot_token or not bot_id:
                    logger.error("[WeixinEngine] confirmed but missing token/bot_id")
                    return {}

                self.current_qr_base64 = ""
                self._set_status(self.LOGIN_STATUS_LOGGED_IN)

                creds = {
                    "token": bot_token,
                    "base_url": result_base_url,
                    "bot_id": bot_id,
                    "user_id": status_resp.get("ilink_user_id", ""),
                }
                self._save_credentials(creds)
                logger.info(f"[WeixinEngine] login confirmed, bot_id={bot_id}")
                return {"token": bot_token, "base_url": result_base_url}

            self._stop_event.wait(1)

        return {}

    def _relogin(self) -> bool:
        if os.path.exists(self._credentials_path):
            try:
                os.remove(self._credentials_path)
            except Exception:
                pass

        self._set_status(self.LOGIN_STATUS_WAITING_QR)
        result = self._qr_login(self.base_url)
        if not result:
            return False

        self.api = WeixinApi(
            base_url=result.get("base_url", self.base_url),
            token=result["token"],
            cdn_base_url=self.cdn_base_url,
        )
        self._context_tokens.clear()
        self._set_status(self.LOGIN_STATUS_LOGGED_IN)
        return True

    # ── poll and message process ───────────────────────────────────────

    def _poll_loop(self):
        consecutive_failures = 0

        while not self._stop_event.is_set():
            try:
                if not self.api:
                    self._stop_event.wait(RETRY_DELAY)
                    continue

                resp = self.api.get_updates(self._get_updates_buf)
                ret = resp.get("ret", 0)
                errcode = resp.get("errcode", 0)

                if ret != 0 or errcode != 0:
                    if errcode == SESSION_EXPIRED_ERRCODE or ret == SESSION_EXPIRED_ERRCODE:
                        logger.warning("[WeixinEngine] session expired, re-login...")
                        if self._relogin():
                            consecutive_failures = 0
                            self._get_updates_buf = ""
                            continue
                        self._stop_event.wait(BACKOFF_DELAY)
                        continue

                    consecutive_failures += 1
                    logger.error(
                        f"[WeixinEngine] get_updates error ret={ret} errcode={errcode} "
                        f"({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})"
                    )
                    if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                        consecutive_failures = 0
                        self._stop_event.wait(BACKOFF_DELAY)
                    else:
                        self._stop_event.wait(RETRY_DELAY)
                    continue

                consecutive_failures = 0
                new_buf = resp.get("get_updates_buf", "")
                if new_buf:
                    self._get_updates_buf = new_buf

                for raw_msg in resp.get("msgs", []):
                    self._process_message(raw_msg)

            except Exception as e:
                if self._stop_event.is_set():
                    break
                consecutive_failures += 1
                logger.error(
                    f"[WeixinEngine] poll loop exception: {e} "
                    f"({consecutive_failures}/{MAX_CONSECUTIVE_FAILURES})"
                )
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    consecutive_failures = 0
                    self._stop_event.wait(BACKOFF_DELAY)
                else:
                    self._stop_event.wait(RETRY_DELAY)

    def _process_message(self, raw_msg: dict):
        message_type = raw_msg.get("message_type", 0)
        if message_type != 1:
            return

        msg_id = str(raw_msg.get("message_id", raw_msg.get("seq", "")))
        if msg_id and msg_id in self._seen_msg_ids:
            return
        if msg_id:
            self._seen_msg_ids.add(msg_id)
            if len(self._seen_msg_ids) > 10000:
                # 简单截断，防止集合无限增长
                self._seen_msg_ids = set(list(self._seen_msg_ids)[-5000:])

        wx_msg = WeixinMessage.from_raw(raw_msg)

        from_user_id = wx_msg.from_user_id
        content = wx_msg.content
        context_token = wx_msg.context_token

        if context_token and from_user_id:
            self._context_tokens[from_user_id] = context_token

        # 仅转发有效纯文本
        if wx_msg.ctype != "TEXT" or not content:
            return

        # ==========================================
        # 核心修改：不再发送 HTTP 请求，而是存入内存队列
        # ==========================================
        if hasattr(self, 'message_queue'):
            print(f"\n{'='*40}")
            print(f"📥 [微信底层] 收到新消息！")
            print(f"   发送者: {from_user_id}")
            print(f"   内  容: {content}")
            print(f"{'='*40}\n")
            
            self.message_queue.append({
                "user_id": str(from_user_id),
                "content": str(content)
            })
        else:
            logger.warning(f"⚠️ 收到微信消息，但 message_queue 未挂载，消息丢失: {content}")

    # ── send api ────────────────────────────────────────────────────────

    def send_text(self, receiver_id: str, text: str):
        if not self.api:
            raise RuntimeError("Weixin API not ready")

        context_token = self._context_tokens.get(receiver_id, "")
        if not context_token:
            raise ValueError(f"No context_token found for receiver_id={receiver_id}")

        self.api.send_text(receiver_id, text, context_token)