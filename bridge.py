import asyncio
import websockets
import json
import base64
import os
import time
from pythonosc import udp_client

# ==========================================
# ★ここをあなたのRenderのURLに書き換える！
# ==========================================
WEBSOCKET_URL = "wss://karmic-identity.onrender.com/ws"

# TouchDesignerへの送信設定
OSC_IP = "127.0.0.1"
OSC_PORT = 9000

# 画像保存フォルダ
DOWNLOAD_DIR = "downloaded_images"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# OSCクライアント
osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

async def listen():
    print(f"Bridge System Starting...")
    print(f"Target: {WEBSOCKET_URL}")


    # ヘッダー設定（ブラウザのふりをする + Originを追加）
    custom_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Origin": "https://karmic-identity.onrender.com" 
    }

    while True:
        try:
            print(">> Cloud Server (Render) に接続中...")
            async with websockets.connect(WEBSOCKET_URL, extra_headers=custom_headers) as websocket:
                print("### 接続成功！待機中... ###")
                
                while True:
                    # メッセージ待機
                    message = await websocket.recv()
                    print("\n[受信] データを受け取りました")
                    
                    try:
                        data = json.loads(message)

                        # 画像処理
                        if data.get("has_image") and data.get("image_data"):
                            print(">> 画像データを検出... 保存中...")
                            image_bytes = base64.b64decode(data["image_data"])
                            filename = f"image_{int(time.time())}.jpg"
                            filepath = os.path.abspath(os.path.join(DOWNLOAD_DIR, filename))
                            
                            with open(filepath, "wb") as f:
                                f.write(image_bytes)
                            
                            print(f">> 画像保存完了: {filepath}")
                            data["image_path"] = filepath
                            del data["image_data"]
                        else:
                            print(">> 画像なし")
                            data["image_path"] = "none"

                        # OSC送信
                        json_str = json.dumps(data, ensure_ascii=False)
                        osc_client.send_message("/json", json_str)
                        print(f"[転送] TouchDesignerへ送信完了 (Port: {OSC_PORT})")

                    except json.JSONDecodeError:
                        print("JSONデコードエラー")
                    except Exception as e:
                        print(f"処理エラー: {e}")

        except websockets.exceptions.ConnectionClosed:
            print("### サーバーから切断されました ###")
        except Exception as e:
            print(f"接続エラー: {e}")
        
        print("5秒後に再接続します...")
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(listen())
    except KeyboardInterrupt:
        print("\n終了します")