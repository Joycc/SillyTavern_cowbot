"""
Weixin message parser (framework-independent).

目标：
- 不依赖 CoW 的 ContextType / ChatMessage
- 仅提取桥接需要的核心字段：from_user_id / context_token / content / ctype
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

# MessageItemType constants from the Weixin protocol
ITEM_TEXT = 1
ITEM_IMAGE = 2
ITEM_VOICE = 3
ITEM_FILE = 4
ITEM_VIDEO = 5


@dataclass
class WeixinMessage:
    msg_id: str
    from_user_id: str
    to_user_id: str
    context_token: str
    content: str
    ctype: str

    @classmethod
    def from_raw(cls, msg: dict[str, Any]) -> "WeixinMessage":
        msg_id = str(msg.get("message_id", msg.get("seq", uuid.uuid4().hex[:8])))
        from_user_id = msg.get("from_user_id", "")
        to_user_id = msg.get("to_user_id", "")
        context_token = msg.get("context_token", "")

        item_list = msg.get("item_list", [])

        text_body = ""
        detected_type = "TEXT"

        for item in item_list:
            itype = item.get("type", 0)

            if itype == ITEM_TEXT:
                text_item = item.get("text_item", {})
                text_body = text_item.get("text", "")
                detected_type = "TEXT"

            elif itype == ITEM_IMAGE and detected_type == "TEXT":
                detected_type = "IMAGE"

            elif itype == ITEM_FILE and detected_type == "TEXT":
                detected_type = "FILE"

            elif itype == ITEM_VIDEO and detected_type == "TEXT":
                detected_type = "VIDEO"

            elif itype == ITEM_VOICE and detected_type == "TEXT":
                voice_text = item.get("voice_item", {}).get("text", "")
                if voice_text:
                    text_body = voice_text
                    detected_type = "TEXT"
                else:
                    detected_type = "VOICE"

        return cls(
            msg_id=msg_id,
            from_user_id=from_user_id,
            to_user_id=to_user_id,
            context_token=context_token,
            content=text_body,
            ctype=detected_type,
        )
