# Active Context

## Current Focus
- 基于 CoW `weixin` 目录进行独立 Sidecar 解耦。
- 以 `WeixinEngine + FastAPI` 作为当前可运行主线。

## Recent Changes
- 重构 `weixin/weixin_api.py`：移除 `common.log`，改为标准 `logging`。
- 重构 `weixin/weixin_message.py`：移除 `ContextType/ChatMessage` 依赖，输出字符串 `ctype`。
- 重构 `weixin/weixin_channel.py`：删除 CoW 框架依赖并改造成 `WeixinEngine`。
- 新增根目录 `main.py`：使用 `lifespan + threading.Thread` 拉起引擎，提供 `/api/qrcode` 与 `/api/send`。
- 已执行语法校验：`weixin/*.py` 与 `main.py` 均通过 `py_compile`。

## Open Questions / Issues
- `python_bridge/main.py` 与根目录 `main.py` 存在并行入口，需后续明确最终保留哪个启动路径。
- 目前二维码字段取自 `qrcode_img_content`，需结合真实返回确认是否始终为可直接展示的 base64。

## Next Steps
- 联调 ST 扩展端 `POST /api/extensions/wechat_bridge/receive`。
- 增加最小运行说明与健康检查/错误观测文档。

---
[2026-04-10 14:53:23] - 初始化 activeContext，记录当前工作焦点与下一步
[2026-04-10 16:04:16] - 更新为 CoW weixin 解耦主线，记录 WeixinEngine 改造与 FastAPI 新入口