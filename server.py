import os
import json
import shutil
import base64
from typing import Optional, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# --- CORS設定 ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except:
                self.disconnect(connection)

manager = ConnectionManager()

# staticフォルダをマウント（upload.htmlなどを配信するため）
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
async def get():
    # タブレット用メイン画面
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

# --- [新規] スマホからの画像アップロード用 ---
@app.post("/upload-satellite")
async def upload_satellite(
    session_id: str = Form(...),
    image: UploadFile = File(...)
):
    print(f"Satellite Upload: {session_id}")
    
    # 画像をBase64に変換
    image_data_b64 = ""
    if image:
        content = await image.read()
        image_data_b64 = base64.b64encode(content).decode('utf-8')
    
    # WebSocketでタブレットに通知
    # 全員に送るが、タブレット側で session_id を見て自分宛か判断する
    message = {
        "type": "satellite_image",
        "session_id": session_id,
        "image_data": image_data_b64,
        "filename": image.filename
    }
    await manager.broadcast(json.dumps(message, ensure_ascii=False))
    
    return {"status": "success"}

# --- 既存のメイン送信フォーム ---
@app.post("/submit")
async def submit_data(
    codename: str = Form(...),
    age: str = Form("0"), 
    sense_sea_mt: int = Form(...),
    sense_quiet_noise: int = Form(...),
    sense_dark_light: int = Form(...),
    desc_imagery: str = Form(""),
    desc_memory: str = Form(""),
    desc_stream: str = Form(""),
    # 画像はBase64文字列として受け取る形に変更（タブレットが保持しているため）
    image_b64: str = Form("") 
):
    print(f"Received Data from: {codename}")

    try:
        safe_age = int(age)
    except:
        safe_age = 0

    payload = {
        "identity": {
            "name": codename,
            "age": safe_age
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
        "image_data": image_b64,
        "has_image": True if image_b64 else False
    }

    # Bridgeへ送信
    await manager.broadcast(json.dumps(payload, ensure_ascii=False))
    
    return {"status": "success"}