🥂 SillyTavern WeChat Bridge (酒馆微信桥接器)
一个为 SillyTavern (酒馆) 打造的强大扩展插件。它能够将你的微信与酒馆中的 AI 角色无缝连接，让 AI 角色直接在微信中与你的朋友（或你自己）进行实时互动！

本插件采用了创新的 “Python 侧车 (Sidecar) + 纯前端看门狗” 架构，彻底摆脱了传统 Node.js 后端的跨域与环境限制，运行极致稳定。

✨ 核心特性
📱 微信原生扫码接入：无需复杂的 Token 配置，直接在酒馆面板点击获取二维码，手机扫码即可无缝登录。

👁️ 看门狗 (Watchdog) 抓取机制：无视不同酒馆分支版本的事件触发差异，采用自研的流式状态监听算法，100% 精准抓取 AI 回复，绝不漏发或重发。

⚡ 极简架构防 404：Python 后端独立维护消息队列（内存级），酒馆前端直接轮询拉取。告别复杂的 Express 路由挂载和 CORS 跨域报错。

🎨 原生 UI 体验：完美融入 SillyTavern 的折叠抽屉 UI 规范，支持主题色自适应，界面干净优雅。

🔒 角色定向绑定：支持在界面上随时切换负责回复的 AI 角色，不影响你与其他角色的正常游玩。

🏗️ 架构说明
本项目由两部分组成，缺一不可：

Python 引擎 (main.py)：基于 FastAPI 运行在 8080 端口。负责与微信服务器保持长链接、处理二维码登录、接收微信消息并暂存在内存队列中，同时暴露 API 供酒馆前端调用。

SillyTavern 扩展 (index.js & index.html)：运行在酒馆前端。负责渲染设置面板、定时向 Python 引擎拉取新消息注入聊天框，并在 AI 生成完毕后将文本回传给 Python 发送至微信。

🚀 快速开始
第一步：启动 Python 微信引擎
确保你的电脑已安装 Python 3.8 或更高版本。

克隆本仓库到本地，并进入后端目录：

Bash
git clone <你的仓库地址>
cd st_extension_wechat_bridge/backend
安装所需的 Python 依赖：

Bash
pip install fastapi uvicorn pydantic requests

启动引擎：

Bash
python main.py
看到控制台输出 Weixin engine thread started 且运行在 127.0.0.1:8080 即表示成功。

第二步：安装 SillyTavern 前端扩展
打开你的 SillyTavern 根目录。

导航至扩展文件夹：public/scripts/extensions/third-party/。

在此目录下新建一个文件夹，必须命名为 st_extension_wechat_bridge。

将本仓库 frontend 目录下的 index.js 和 index.html 放入该文件夹中。

刷新 SillyTavern 网页（按 F5）。

🎮 使用指南
打开 SillyTavern 网页（建议酒馆、插件都跑在一台服务器上，并在这台机器上登陆），点击顶部导航栏的**“扩展 (Extensions)”**图标（拼图形状）。

下拉到最底部，找到 微信桥接器 (WeChat Bridge) 独立面板。

点击展开面板，从下拉菜单中选择一个你要绑定的 AI 角色。

点击 “获取登录二维码” 按钮。

界面上会出现一个蓝色链接，点击打开并在新窗口中使用手机微信扫码授权登录。

面板状态变为 <span style="color: green;">“微信已登录，开始监听消息”</span> 后，即可使用其他微信号向该登录微信发送测试消息。

享受 AI 接管微信的乐趣吧！

🛠️ 常见问题 (FAQ)
Q: 为什么获取不到二维码，控制台报 CORS/跨域 错误？
A: 请确保 Python 端的 main.py 已经成功运行在 8080 端口。如果你在局域网的另一台机器上访问酒馆（例如手机访问电脑 IP），请在 index.js 的 defaultSettings 中，将 pythonBase 修改为运行 Python 脚本那台电脑的实际局域网 IP（例如 http://192.168.x.x:8080/api）。

Q: 下拉框里显示“无可用角色”怎么办？
A: 扩展加载时可能角色数据还未准备好。只需将鼠标悬停或点击一下下拉框，列表就会瞬间自动刷新。

Q: 微信发了消息，酒馆没反应？
A: 请检查 Python 控制台是否打印了 [微信底层] 收到新消息！。如果 Python 收到了但酒馆没反应，请检查你当前酒馆的激活角色是否与下拉框中绑定的角色一致。为了防止消息错乱，非绑定状态下的消息会被自动拦截。

🤝 参与贡献
欢迎提交 Pull Request 或发起 Issue 来共同完善这个桥接器！不管是修复 Bug、优化协议底层，还是增加图片/语音的转发支持，社区都非常期待你的加入。

📄 许可证
本项目基于 MIT License 开源。请在遵守当地法律法规及腾讯微信相关服务协议的前提下使用本项目，仅供技术交流与学习，严禁用于任何非法或商业灰产用途。