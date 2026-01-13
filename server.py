import os
import json
import base64
import asyncio
from typing import List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Form, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS設定
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# === WebSocket管理 ===
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(f"🔌 Client connected. Total: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(f"🔌 Client disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except Exception as e:
                print(f"Broadcast error: {e}")

manager = ConnectionManager()

# === ルーティング ===

@app.get("/")
async def get_index():
    if os.path.exists("static/index.html"):
        return FileResponse("static/index.html")
    return FileResponse("index.html")

# 静的ファイルマウント
if os.path.exists("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")
else:
    app.mount("/static", StaticFiles(directory="."), name="static")
    app.mount("/", StaticFiles(directory="."), name="root")

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# === ★ここを修正しました (Q1-Q20に対応) ===
@app.post("/submit")
async def handle_form(
    q1: str = Form(""),  # Nickname
    q2: str = Form(""),  # Age (文字として受け取る)
    q3: str = Form(""),  # Color
    q4_1: int = Form(0), # 過ごすなら(時間)
    q4_2: int = Form(0), # 過ごすなら(天気)
    q4_3: int = Form(0), # 過ごすなら(季節)
    q5: int = Form(0),   # 行動
    q6_1: int = Form(0), # 住処(場所)
    q6_2: int = Form(0), # 住処(音)
    q6_3: int = Form(0), # 住処(感覚)
    q7: int = Form(0),   # 香り
    q8: str = Form(""),  # 旅行
    q9: int = Form(0),   # 願い
    q10: int = Form(0),  # エネルギー
    q11: int = Form(0),  # 因果
    q12: int = Form(0),  # 慈悲
    q13: int = Form(0),  # 無常
    q14: int = Form(0),  # 死生
    q15: int = Form(0),  # 向かう
    q16: int = Form(0),  # 還る
    q17: str = Form(""), # 残すもの
    q18: str = Form(""), # 好きなもの
    q19: str = Form(""), # 嫌いなもの
    image_b64: str = Form("") # 画像データ
):
    print(f"📩 受信: {q1} ({q2})")
    
    # TouchDesignerなどが扱いやすいJSON形式にまとめる
    data = {
        "type": "form_submission",
        "identity": {
            "nickname": q1,
            "age": q2,
            "color": q3
        },
        "conditions": {
            "time": q4_1,
            "weather": q4_2,
            "season": q4_3
        },
        "adolescence": {
            "approach": q5,
            "environment_place": q6_1,
            "environment_sound": q6_2,
            "environment_sense": q6_3,
            "scent": q7
        },
        "adulthood": {
            "destination": q8,
            "wish_direction": q9,
            "drive": q10
        },
        "philosophy": {
            "causality": q11,
            "compassion": q12,
            "impermanence": q13,
            "life_death": q14
        },
        "afterlife": {
            "heading": q15,
            "returning": q16
        },
        "legacy": {
            "keep": q17,
            "likes": q18,
            "avoids": q19
        },
        "has_image": bool(image_b64),
        "image_data": image_b64
    }
    
    await manager.broadcast(data)
    return {"message": "Success"}

# スマホ画像アップロード用
@app.post("/upload-satellite")
async def upload_satellite(session_id: str = Form(...), image: UploadFile = File(...)):
    content = await image.read()
    b64_img = base64.b64encode(content).decode("utf-8")
    message = {
        "type": "satellite_image",
        "session_id": session_id,
        "image_data": b64_img
    }
    await manager.broadcast(message)
    return {"status": "success"}

if __name__ == "__main__":
    import uvicorn
    # Renderでは環境変数PORTが使われるため、それに対応
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)