import asyncio
import websockets
import json
import base64
import os
import time
from pythonosc import udp_client
from openai import AsyncOpenAI  # AIを使うためのライブラリ
# ★追加: 別ファイルからキーを読み込む
from secret import OPENAI_KEY 

# ==========================================
# ★設定エリア
# ==========================================
WEBSOCKET_URL = "wss://karmic-identity.onrender.com/ws"

# ★変更: 直書きをやめて変数を使う
OPENAI_API_KEY = OPENAI_KEY 

# ... (以下同じ)
# 3. AIの性格設定（プロンプト）
# TouchDesignerが使いやすいJSON形式で返事をするように命令します
SYSTEM_PROMPT = """
あなたは人間の深層心理を解析するシステムです。
入力された「心象風景」「記憶」「意識の流れ」から、以下のパラメータをJSON形式のみで出力してください。
余計な解説は不要です。

{
  "emotion_valance": -1.0〜1.0 (ネガティブ〜ポジティブ),
  "emotion_arousal": 0.0〜1.0 (静けさ〜激しさ),
  "color_hex": "#RRGGBB" (感情を表す色),
  "keywords": ["単語1", "単語2", "単語3"] (印象的なキーワード3つ),
  "poetic_message": "入力された要素を統合した、短く抽象的な詩（30文字以内）"
}
"""

# TouchDesignerへの送信設定
OSC_IP = "127.0.0.1"
OSC_PORT = 9000
DOWNLOAD_DIR = "downloaded_images"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# クライアント初期化
osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)
ai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

async def analyze_text_with_ai(text_data):
    """ChatGPTにテキストを投げて解析結果をもらう関数"""
    print(">> AI解析を開始します...")
    try:
        # 入力テキストをまとめる
        user_content = f"""
        心象風景: {text_data.get('imagery', '')}
        記憶: {text_data.get('memory', '')}
        意識の流れ: {text_data.get('stream', '')}
        """

        response = await ai_client.chat.completions.create(
            model="gpt-3.5-turbo", # 節約のため3.5。精度重視なら "gpt-4o" に変更
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content}
            ],
            temperature=0.7,
            response_format={"type": "json_object"} # 確実にJSONで返させる
        )

        result_json = response.choices[0].message.content
        print(f">> AI回答: {result_json}")
        return json.loads(result_json)

    except Exception as e:
        print(f"!! AI解析エラー: {e}")
        # エラー時はデフォルト値を返す（止まらないように）
        return {
            "emotion_valance": 0,
            "emotion_arousal": 0,
            "color_hex": "#FFFFFF",
            "keywords": ["Error"],
            "poetic_message": "静寂の中に答えがある"
        }

async def listen():
    print(f"Bridge System (AI Powered) Starting...")
    
    # ヘッダー設定
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

                        # --- 1. 画像処理 ---
                        if data.get("has_image") and data.get("image_data"):
                            print(">> 画像保存中...")
                            try:
                                image_bytes = base64.b64decode(data["image_data"])
                                filename = f"image_{int(time.time())}.jpg"
                                filepath = os.path.abspath(os.path.join(DOWNLOAD_DIR, filename))
                                with open(filepath, "wb") as f:
                                    f.write(image_bytes)
                                data["image_path"] = filepath
                                del data["image_data"]
                            except:
                                data["image_path"] = "error"
                        else:
                            data["image_path"] = "none"

                        # --- 2. AI解析 (ここが追加箇所！) ---
                        # テキストが少しでもあればAIにかける
                        text_info = data.get("text", {})
                        if any(text_info.values()):
                            ai_result = await analyze_text_with_ai(text_info)
                            # 元データにAIの結果を合体させる
                            data["ai_analysis"] = ai_result
                        else:
                            print(">> テキスト入力なしのためAIスキップ")
                            data["ai_analysis"] = {}

                        # --- 3. TouchDesignerへ送信 ---
                        json_str = json.dumps(data, ensure_ascii=False)
                        osc_client.send_message("/json", json_str)
                        print(f"[転送] TouchDesignerへ送信完了")

                    except json.JSONDecodeError:
                        print("JSONデコードエラー")
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