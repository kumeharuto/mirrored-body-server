import os
import json
import shutil
import base64
from typing import List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware  # ★追加 1

app = FastAPI()

# ==========================================
# ★追加 2: CORS（通信許可）設定
# これがないと外部（bridge.py）からの接続が 403 で弾かれます
# ==========================================
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # すべての接続元を許可
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
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        print(">> Client Disconnected")

    async def broadcast(self, message: str):
        # 切断されたクライアントが混ざっていないか確認しながら送信
        for connection in self.active_connections[:]:
            try:
                await connection.send_text(message)
            except:
                self.disconnect(connection)

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
    except Exception as e:
        print(f"WS Error: {e}")
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
        # 一旦保存
        file_location = f"{UPLOAD_DIR}/{image.filename}"
        with open(file_location, "wb+") as file_object:
            shutil.copyfileobj(image.file, file_object)
        
        # Base64変換
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
        "image_data": image_data_b64,
        "has_image": True if image_data_b64 else False
    }

    # 3. 中継サーバへ送信
    await manager.broadcast(json.dumps(payload, ensure_ascii=False))
    
    return {"status": "success"}