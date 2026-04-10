# Product Context

## 项目名称
SillyTavern-WeChat-ClawBot-Bridge（酒馆原生微信桥接器）

## 项目目标
构建一个 SillyTavern 微信桥接 Sidecar 服务，基于 CoW 的 `weixin` 目录进行“去框架化”解耦，形成可独立运行的 FastAPI + WeixinEngine。

## 核心价值
- 从 CoW 单体框架中抽离可复用微信长轮询能力，降低耦合。
- 通过本地 HTTP 与 ST 扩展后端通信，形成稳定可控的桥接边车。
- 保留 Weixin API 核心协议逻辑（轮询、发送、CDN 媒体能力），仅替换外层框架依赖。

## 当前范围（已确认）
- 已放弃 OpenClaw / npx / subprocess 路线。
- 当前主线为 `weixin_api.py`、`weixin_message.py`、`weixin_channel.py` 深度解耦。
- 新增根目录 `main.py` 作为 Sidecar 启动入口，提供 `/api/qrcode` 与 `/api/send`。

## 当前架构摘要
- `weixin/weixin_api.py`：协议 API 客户端，保留 HTTP、重试、加解密、CDN 逻辑。
- `weixin/weixin_message.py`：轻量消息解析，输出 `from_user_id/context_token/content/ctype`。
- `weixin/weixin_channel.py`：已改造成 `WeixinEngine`，负责 QR 登录、长轮询、消息转发、回发。
- `main.py`：FastAPI 生命周期拉起后台引擎线程，对外提供桥接接口。

---
[2026-04-10 14:52:57] - 初始化 Memory Bank，并记录当前产品上下文与阶段一范围
[2026-04-10 16:03:18] - 产品方向从 OpenClaw 切换为 CoW weixin 解耦 Sidecar，更新目标与架构摘要