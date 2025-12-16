import os
import json
import shutil
import base64  # 追加: 画像を文字にする機能
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# --- CORS設定（追加）---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべてのオリジンを許可
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 設定 ---
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# --- WebSocket管理 ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        print(">> Client Connected!")

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
        print(">> Client Disconnected")

    async def broadcast(self, message: str):
        # 接続されている全てのクライアント（中継サーバ）にデータを送信
        for connection in self.active_connections:
            await connection.send_text(message)

manager = ConnectionManager()

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get():
    with open("static/index.html", "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.post("/submit")
async def submit_data(
    codename: str = Form(...),
    age: int = Form(...),
    sense_sea_mt: int = Form(...),
    sense_quiet_noise: int = Form(...),
    sense_dark_light: int = Form(...),
    desc_imagery: str = Form(...),
    desc_memory: str = Form(...),
    desc_stream: str = Form(...),
    image: UploadFile = File(None)
):
    print(f"Received Data from: {codename}")

    # 1. 画像処理（Base64変換）
    image_data_b64 = ""
    if image:
        # 一旦保存（バックアップ用）
        file_location = f"{UPLOAD_DIR}/{image.filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(image.file, file_object)
        
        # もう一度開いて、Base64（文字データ）に変換して読み込む
        with open(file_location, "rb") as image_file:
            image_data_b64 = base64.b64encode(image_file.read()).decode('utf-8')

    # 2. データセット作成
    payload = {
        "identity": {
            "name": codename,
            "age": age
        },
        "sliders": {
            "sea_mt": sense_sea_mt,
            "quiet_noise": sense_quiet_noise,
            "dark_light": sense_dark_light
        },
        "text": {
            "imagery": desc_imagery,
            "memory": desc_memory,
            "stream": desc_stream
        },
        "image_data": image_data_b64, # 画像の実体（文字）を送る
        "has_image": True if image_data_b64 else False
    }

    # 3. 中継サーバへ送信
    await manager.broadcast(json.dumps(payload, ensure_ascii=False))
    
    return {"status": "success"}