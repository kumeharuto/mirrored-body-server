from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Form, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import List, Optional
import json
import asyncio
import base64

app = FastAPI()

# 静的ファイルの配信
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="static")

# WebSocket接続管理
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast(self, message: str):
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except:
                pass

manager = ConnectionManager()

@app.get("/")
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

# WebSocketエンドポイント
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)

# 画像アップロード (スマホ -> サーバー -> タブレット)
@app.post("/upload-satellite")
async def upload_satellite(session_id: str = Form(...), image: UploadFile = File(...)):
    contents = await image.read()
    b64_image = base64.b64encode(contents).decode('utf-8')
    
    # タブレット(index.html)へ通知
    msg = json.dumps({
        "type": "satellite_image",
        "session_id": session_id,
        "image_data": b64_image
    })
    await manager.broadcast(msg)
    return JSONResponse({"status": "ok"})

# ★修正: 新しい設問フォームの受付定義
@app.post("/submit")
async def submit(
    nickname: str = Form(...),
    special_existence: str = Form(""),
    favorite_smell: str = Form(""),
    
    slider_noise_silence: int = Form(2),
    slider_city_country: int = Form(2),
    slider_reality_fantasy: int = Form(2),
    
    slider_hell_time: int = Form(1),
    text_dream: str = Form(""),
    text_setback: str = Form(""),
    text_lost_release: str = Form(""),
    
    slider_return_element: int = Form(1),
    slider_go_north_south: int = Form(2),
    
    image_b64: str = Form("")
):
    # データ構築（Bridgeへ送るJSONを作成）
    data = {
        "type": "form_submission",
        "identity": {
            "nickname": nickname,
            "special_existence": special_existence,
            "favorite_smell": favorite_smell
        },
        "seishun": {
            "noise_silence": slider_noise_silence,
            "city_country": slider_city_country,
            "reality_fantasy": slider_reality_fantasy
        },
        "shuka": {
            "hell_time": slider_hell_time, # 0:Past, 1:Present, 2:Future
            "dream": text_dream
        },
        "hakuto": {
            "setback": text_setback,
            "lost_release": text_lost_release
        },
        "gento": {
            "return_element": slider_return_element, # 0:Sea, 1:Soil, 2:Sky
            "go_north_south": slider_go_north_south
        },
        "image_data": image_b64,
        "has_image": bool(image_b64)
    }

    # Bridge(AI)へ送信
    await manager.broadcast(json.dumps(data))
    return JSONResponse({"status": "ok"})