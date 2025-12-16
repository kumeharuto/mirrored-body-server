import asyncio
import websockets
import json
import base64
import os
import time
from pythonosc import udp_client
from openai import AsyncOpenAI
# 鍵ファイルから読み込み
from secret import OPENAI_KEY

# ==========================================
# ★設定エリア
# ==========================================
WEBSOCKET_URL = "wss://karmic-identity.onrender.com/ws"
OPENAI_API_KEY = OPENAI_KEY

# AIへの命令
SYSTEM_PROMPT = """
あなたは深層心理解析システムです。
入力された情報から、以下のパラメータをJSONのみで出力してください。
画像がある場合は、その視覚的印象も解析に含めてください。

{
  "visual_impression": "画像に何が映っているか、または画像の雰囲気（画像がない場合は『なし』）",
  "emotion_valance": -1.0〜1.0 (ネガティブ〜ポジティブ),
  "emotion_arousal": 0.0〜1.0 (静けさ〜激しさ),
  "color_hex": "#RRGGBB" (感情色),
  "keywords": ["単語1", "単語2", "単語3"],
  "poetic_message": "30文字以内の抽象的な詩"
}
"""

OSC_IP = "127.0.0.1"
OSC_PORT = 9000
DOWNLOAD_DIR = "downloaded_images"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

# 画像をBase64テキストに変換する関数
def encode_image(image_path):
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')

# ★ここがハイブリッド解析の心臓部
async def analyze_with_hybrid_ai(text_data, image_path):
    print(">> AI解析を開始します...")
    
    # ユーザーの入力テキスト
    text_content = f"""
    心象風景: {text_data.get('imagery', 'なし')}
    記憶: {text_data.get('memory', 'なし')}
    意識の流れ: {text_data.get('stream', 'なし')}
    """

    try:
        # A. 画像がある場合 -> GPT-4o (Vision) を使用
        if image_path and image_path != "none" and image_path != "error":
            print(">> [モード] GPT-4o (Vision対応) で解析中...")
            
            base64_image = encode_image(image_path)
            
            response = await ai_client.chat.completions.create(
                model="gpt-4o", # 高性能モデル
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": text_content},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}",
                                    "detail": "low" # lowにするとさらに節約になります(85トークン固定)
                                }
                            }
                        ]
                    }
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )

        # B. 画像がない場合 -> GPT-3.5 Turbo (節約モード) を使用
        else:
            print(">> [モード] GPT-3.5 Turbo (テキストのみ) で解析中...")
            
            response = await ai_client.chat.completions.create(
                model="gpt-3.5-turbo", # 節約モデル
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": text_content}
                ],
                temperature=0.7,
                response_format={"type": "json_object"}
            )

        result_json = response.choices[0].message.content
        print(f">> AI回答: {result_json}")
        return json.loads(result_json)

    except Exception as e:
        print(f"!! AI解析エラー: {e}")
        return {
            "emotion_valance": 0, "emotion_arousal": 0,
            "color_hex": "#000000", "keywords": ["Error"],
            "poetic_message": "解析不能の闇"
        }

async def listen():
    print(f"Bridge System (Hybrid AI) Starting...")
    
    origin = WEBSOCKET_URL.replace("wss://", "https://").replace("/ws", "")
    custom_headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
        "Origin": origin
    }

    while True:
        try:
            print(f">> 接続中: {WEBSOCKET_URL}")
            async with websockets.connect(WEBSOCKET_URL, extra_headers=custom_headers) as websocket:
                print("### 接続成功！データ待機中... ###")
                
                while True:
                    message = await websocket.recv()
                    print("\n[受信] データを受け取りました")
                    
                    try:
                        data = json.loads(message)

                        # 1. 画像保存処理
                        saved_path = "none"
                        if data.get("has_image") and data.get("image_data"):
                            try:
                                print(">> 画像保存中...")
                                image_bytes = base64.b64decode(data["image_data"])
                                filename = f"image_{int(time.time())}.jpg"
                                filepath = os.path.abspath(os.path.join(DOWNLOAD_DIR, filename))
                                with open(filepath, "wb") as f:
                                    f.write(image_bytes)
                                saved_path = filepath
                            except:
                                saved_path = "error"
                        data["image_path"] = saved_path
                        if "image_data" in data: del data["image_data"]

                        # 2. ハイブリッドAI解析
                        # 画像パスを渡して、AI関数側で判断させる
                        ai_result = await analyze_with_hybrid_ai(data.get("text", {}), saved_path)
                        data["ai_analysis"] = ai_result

                        # 3. TouchDesignerへ送信
                        json_str = json.dumps(data, ensure_ascii=False)
                        osc_client.send_message("/json", json_str)
                        print(f"[転送] TouchDesignerへ送信完了")

                    except json.JSONDecodeError:
                        pass
                    except Exception as e:
                        print(f"処理エラー: {e}")

        except websockets.exceptions.ConnectionClosed:
            print("### サーバーから切断 ###")
        except Exception as e:
            print(f"接続エラー: {e}")
        
        await asyncio.sleep(5)

if __name__ == "__main__":
    try:
        asyncio.run(listen())
    except KeyboardInterrupt:
        print("\n終了します")