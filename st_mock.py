# mock_st.py (模拟 SillyTavern 接收端)
from fastapi import FastAPI, Request
import uvicorn

app = FastAPI()

# 这正是你的微信引擎尝试推送消息的地址
@app.post("/api/extensions/wechat_bridge/receive")
async def receive_from_wechat(request: Request):
    # 解析并打印接收到的 JSON 数据
    data = await request.json()
    print("\n" + "="*50)
    print("🎯 [假酒馆] 成功拦截到微信消息！")
    print(f"📩 发件人 ID (user_id): {data.get('user_id')}")
    print(f"💬 消息内容 (content): {data.get('content')}")
    print("="*50 + "\n")
    return {"status": "ok", "message": "SillyTavern simulated success"}

if __name__ == "__main__":
    print("🍺 假酒馆服务器启动，正在监听 8000 端口...")
    uvicorn.run(app, host="127.0.0.1", port=8000)