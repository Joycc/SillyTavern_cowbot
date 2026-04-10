# System Patterns

## 架构模式
1. **双模块解耦模式**
   - Python 边车与 ST 插件进程分离，通过本地 HTTP 通信。
   - 目的：降低耦合、便于阶段化开发与独立调试。

2. **托管进程 + 状态镜像模式**
   - Python 通过 `subprocess.Popen` 托管官方 CLI。
   - 使用后台线程非阻塞读取 stdout/stderr，将外部进程状态镜像为可查询 API 状态。

3. **只读状态接口 + 异步发送队列模式**
   - `/api/status` 仅返回固定状态字段。
   - `/api/send` 将请求入队，后台线程尝试写入 CLI stdin（阶段一临时路径）。

## 并发与线程模式
- 一个共享状态对象 + `RLock` 保护并发读写。
- 线程职责拆分：
  - stdout 读取线程（解析状态）
  - stderr 读取线程（记录错误）
  - watchdog 线程（进程存活检测 + 发送队列处理）

## 生命周期模式
- FastAPI `startup` 启动 CLI。
- FastAPI `shutdown` 优雅停止 CLI，超时后强制回收。

## 新增模式（CoW 解耦阶段）
- **协议层与框架层分离模式**
  - `weixin_api.py` 保留协议细节（HTTP/重试/CDN/加解密），移除上层框架依赖。
- **轻量消息标准化模式**
  - `weixin_message.py` 只输出桥接核心字段，`ctype` 统一为字符串，避免跨项目枚举耦合。
- **引擎-接口桥接模式**
  - `WeixinEngine` 专注登录、轮询、转发、回发；`main.py` 只负责生命周期与 API 暴露。
- **反向回调改主动转发模式**
  - 接收消息后直接 `requests.post` 到 ST 扩展后端 `.../wechat_bridge/receive`，替代 CoW 内部消息总线。

---
[2026-04-10 14:53:44] - 初始化 systemPatterns，记录当前已落地的架构与并发模式
[2026-04-10 16:04:55] - 新增 CoW weixin 解耦模式：协议层独立、轻量消息标准化、引擎与 FastAPI 分层桥接