# 项目：SillyTavern-WeChat-ClawBot-Bridge (酒馆原生微信桥接器)

## 1. 项目概述
本项目旨在开发一个 SillyTavern (ST) 的原生扩展插件，结合轻量级的 Python 边车服务，实现将 **微信官方最新的 ClawBot (基于 OpenClaw 框架)** 接入 SillyTavern。
核心优势：弃用高风险的第三方 Hook/逆向协议，全面拥抱微信在 2026 年 3 月官方推出的长连接插件生态，实现零封号风险、高稳定性的角色扮演桥接。

## 2. 架构设计 (OpenClaw 网关伪装模式)

项目分为两个核心模块，独立运行但通过本地接口紧密通信：

* **模块 A: Python 桥接引擎 (OpenClaw Gateway Mock)**
    * **职责:** 1. 通过 `subprocess` 启动并托管微信官方的 `@tencent-weixin/openclaw-weixin-cli`。
      2. 实时解析 CLI 输出，提取登录/绑定用的配对信息或二维码状态。
      3. 启动一个伪装的本地服务，充当 OpenClaw Gateway 角色，接收微信 CLI 转发过来的消息，并将酒馆的回复按 OpenClaw 格式返回给 CLI。
    * **技术栈:** `Python 3.10+`, `FastAPI`, `subprocess`。
* **模块 B: SillyTavern Extension (ST 插件)**
    * **职责:** 提供用户操作界面 (UI)、展示绑定二维码/配对码、下拉选择绑定的酒馆角色、拦截微信消息触发 LLM 生成、捕获生成回复并推回给 Python。
    * **技术栈:** `HTML/CSS/JS` (ST 插件前端 UI), `Node.js / Express` (ST 插件后端 API 路由)。

---

## 3. 数据与业务流转 (Data Flow)

### 3.1 扫码绑定流 (基于官方流程)
1. 用户在 ST 打开插件面板，点击“启动 ClawBot 连接”。
2. ST 插件向 Python 发起请求。Python 使用 `subprocess.Popen` 启动命令：`npx -y @tencent-weixin/openclaw-weixin-cli@latest install`。
3. Python 持续读取该进程的标准输出 (stdout)。当识别到连接二维码数据或配对引导时，将其提取并通过 `/api/qrcode` 接口提供给 ST。
4. 用户在手机微信端进入「我-设置-插件-微信ClawBot」进行扫码确认绑定。

### 3.2 消息接收流 (微信 -> ST)
1. 微信端发送消息 -> 微信官方长连接服务器 -> 本地 `@tencent-weixin/openclaw-weixin-cli`。
2. CLI 工具将消息路由到本地的 Python 伪装网关 (拦截 OpenClaw 标准请求)。
3. Python 提取出纯文本和 `SenderID`，通过 HTTP POST 推送给 ST 后端扩展 API (`/api/extensions/wechat_clawbot/receive`)。
4. ST 后端根据当前 UI 绑定的角色配置，将消息注入上下文并触发 LLM。

### 3.3 消息回复流 (ST -> 微信)
1. LLM 生成完毕，ST 插件 (JS) 截获纯文本回复 (过滤掉如 `*动作*` 的 Markdown)。
2. ST 插件将回复推回给 Python 伪装网关。
3. Python 网关将该回复包装为 OpenClaw 兼容的响应格式，交还给官方 CLI 工具。
4. 官方 CLI 工具通过长连接将消息推送到用户的微信聊天框。

---

## 4. API 接口定义规范

### 4.1 Python 引擎提供的 API (供 ST 轮询与调用)
* **服务地址:** `http://127.0.0.1:8080`
* `GET /api/status`
    * 返回: `{ "status": "WAITING_CLI" | "WAITING_QR" | "LOGGED_IN", "qr_data": "...", "pairing_code": "..." }`
* `POST /api/send`
    * 载荷: `{ "user_id": "微信联系人标识", "content": "要发送的纯文本" }`
    * 逻辑: 接收 ST 的响应，并传递给底层 ClawBot CLI 进行发送。

### 4.2 ST 插件后端提供的 API
* **服务地址:** `http://127.0.0.1:8000/api/extensions/wechat_clawbot`
* `POST /receive`
    * 载荷: `{ "user_id": "发送者标识", "content": "接收到的文本" }`

---

## 5. 阶段开发任务 (For RooCode)

1. **阶段一：编写 Python 端的 CLI 托管服务 (Subprocess Manager)**
   * 编写 `main.py`，实现 `FastAPI` 服务。
   * 编写一个专用的线程类，使用 `subprocess.Popen` 执行 `npx -y @tencent-weixin/openclaw-weixin-cli@latest`（需要确保系统已安装 Node.js）。
   * 实现非阻塞读取终端输出，将获取到的登录指引状态暴露在 `/api/status`。
2. **阶段二：实现 OpenClaw 协议劫持与收发**
   * 研究 OpenClaw CLI 与本地网关的通信端口及载荷格式。在 `FastAPI` 中增加相应的路由（如 `/v1/messages` 等），骗过 CLI，使其认为正在与真实的 OpenClaw 通信。
   * 实现收到请求后打印到控制台，并准备向 ST 转发。
3. **阶段三：SillyTavern 插件 UI 与角色挂载**
   * 编写酒馆端的前后端代码，展示二维码并实现微信消息到具体角色的定向回复。