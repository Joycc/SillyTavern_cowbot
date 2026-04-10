# Decision Log

## Decisions

[2026-04-10 14:46:55] - 阶段一范围决策：严格按 `plan.md` 执行，仅实现 OpenClaw CLI 托管，不引入 itchat
- 背景：用户最初提到 FastAPI + itchat，但随后明确“先按 plan.md 严格执行”。
- 决策：阶段一仅包含 `subprocess` 托管官方 CLI、状态解析、基础 API。
- 影响：避免偏离计划，降低首阶段复杂度；itchat 相关逻辑延后且当前不进入代码。

[2026-04-10 14:51:34] - `/api/status` 字段口径固定为 `status/qr_data/pairing_code`
- 背景：用户要求接口字段先对齐 plan。
- 决策：`/api/status` 固定字段恒存在，未解析到内容时返回空字符串。
- 影响：便于前端轮询稳定解析，减少空键判断。

[2026-04-10 14:54:07] - 初始化 Memory Bank 标准文件集
- 背景：用户发起“初始化memory bank”。
- 决策：创建 `memory-bank/` 及五个核心文件，记录当前项目状态。
- 影响：后续跨会话可基于统一上下文继续推进。

[2026-04-10 16:05:25] - 架构决策：放弃 OpenClaw 主线，切换为 CoW weixin 目录深度解耦
- 背景：用户明确要求回滚 openclaw/npx/subprocess 相关实现，转向 `itchat-uos` 与 CoW `weixin` 方案。
- 决策：以 `weixin_api.py`、`weixin_message.py`、`weixin_channel.py` 为核心进行去框架化，构建 `WeixinEngine`，并使用根目录 `main.py` 作为 FastAPI 启动入口。
- 影响：项目从“CLI 托管型桥接器”转为“长轮询 Sidecar 引擎”，后续联调重点变为 ST 扩展接收端与 context_token 映射稳定性。