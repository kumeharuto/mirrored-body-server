import asyncio
import json
import os
import base64
import time
import requests 
from datetime import datetime

import websockets
from pythonosc import udp_client
from openai import OpenAI

# 秘密鍵の読み込み
import secret

# ==========================================
# 設定エリア
# ==========================================
# TouchDesignerへの送り先
OSC_IP = "127.0.0.1"
OSC_PORT = 9000

# サーバーのWebSocket URL (本番環境のURLに合わせてください)
# 例: "wss://karma-portrait.onrender.com/ws"
WEBSOCKET_URL = "wss://karmic-identity.onrender.com/ws" 
# ※もしローカルテスト中なら "ws://localhost:8000/ws"

# 保存フォルダ
IMAGE_DIR = "received_images"
VIDEO_DIR = "generated_videos"
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# AIへの命令（Karma Portrait用）
SYSTEM_PROMPT = """
あなたはインスタレーション作品『Karma Portrait (業報の自己像)』のシステムです。
入力されたユーザーの「5つのフェーズ（黄土・青春・朱夏・白冬・玄冬）」に関する回答から、
その人物の内面に潜む「業（カルマ）」を解析し、以下のJSON形式のみで出力してください。

【入力データの解釈】
- 黄土 (Odo): 原点。名前、特別な存在、匂い。
- 青春 (Seishun): 志向性。静寂(0)-喧騒(4)、都市(0)-田舎(4)、現実(0)-夢想(4)。
- 朱夏 (Shuka): 修羅。苦悩の時系列(0:過去/1:現在/2:未来)と、夢。
- 白冬 (Hakuto): 喪失。挫折と手放せないもの。
- 玄冬 (Gento): 帰結。還る場所(0:海/1:土/2:空)と向かう方角(0:北-4:南)。

【出力JSONフォーマット】
{
  "visual_impression": "ユーザーの回答から想起される抽象的な映像のプロンプト（英語）。例: A lonely figure walking in a snowy field, cinematic lighting...",
  "emotion_valance": -1.0〜1.0 (悲しみ/ネガティブ 〜 喜び/ポジティブ),
  "emotion_arousal": 0.0〜1.0 (静寂 〜 激しさ),
  "karma_color": "#RRGGBB" (その人の業を表す色),
  "keywords": ["日本語キーワード1", "日本語キーワード2", "日本語キーワード3"],
  "poetic_message": "回答全体を総括するような、30文字以内の抽象的で詩的な日本語のメッセージ"
}
"""

# ==========================================
# システム初期化
# ==========================================
print("Bridge System (Karma Portrait v2) Starting...")

client = OpenAI(api_key=secret.OPENAI_KEY)
osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

# ==========================================
# Stability AI 動画生成関数
# ==========================================
def generate_video(image_path):
    print(f"🎬 動画生成を開始します: {image_path}")
    api_key = secret.STABILITY_KEY
    
    try:
        # 生成リクエスト (POST)
        url = "https://api.stability.ai/v2beta/image-to-video"
        
        with open(image_path, "rb") as file:
            response = requests.post(
                url,
                headers={"authorization": f"Bearer {api_key}"},
                files={"image": file},
                data={
                    "seed": 0,
                    "cfg_scale": 1.8,
                    "motion_bucket_id": 127
                },
            )
            
        if response.status_code != 200:
            print(f"❌ 生成リクエスト失敗: {response.text}")
            return "none"
            
        generation_id = response.json().get('id')
        print(f"⏳ 生成中... ID: {generation_id}")
        
        # 完了待ちループ (Polling)
        for i in range(30): # 最大60秒待機
            time.sleep(2) 
            res = requests.get(
                f"{url}/result/{generation_id}",
                headers={
                    'authorization': f"Bearer {api_key}",
                    'accept': "video/*"
                },
            )
            
            if res.status_code == 202:
                print(".", end="", flush=True)
                continue
            
            elif res.status_code == 200:
                print("\n✨ 生成完了！")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = os.path.join(VIDEO_DIR, f"video_{timestamp}.mp4")
                
                with open(save_path, 'wb') as f:
                    f.write(res.content)
                
                return os.path.abspath(save_path)
            
            else:
                print(f"\n❌ エラー: {res.json()}")
                return "none"
                
        print("\n❌ タイムアウト")
        return "none"

    except Exception as e:
        print(f"❌ 動画生成例外: {e}")
        return "none"


# ==========================================
# メイン処理
# ==========================================
async def process_data(data):
    # ユーザー情報の取得
    identity = data.get('identity', {})
    seishun = data.get('seishun', {})
    shuka = data.get('shuka', {})
    hakuto = data.get('hakuto', {})
    gento = data.get('gento', {})

    print("\n-----------------------------------")
    print(f"Karma Entry Received: {identity.get('nickname')}")

    # 1. 画像保存
    saved_image_path = "none"
    if data.get("has_image") and data.get("image_data"):
        try:
            # Base64ヘッダがある場合は除去
            b64_str = data["image_data"]
            if "base64," in b64_str:
                b64_str = b64_str.split("base64,")[1]
            
            image_data = base64.b64decode(b64_str)
            filename = f"karma_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            saved_image_path = os.path.join(IMAGE_DIR, filename)
            
            with open(saved_image_path, "wb") as f:
                f.write(image_data)
            
            saved_image_path = os.path.abspath(saved_image_path)
            print(f"Image Saved: {saved_image_path}")
            
        except Exception as e:
            print(f"Image Save Error: {e}")

    # 2. GPT-4 テキスト解析
    print("AI Analysis (Karma Parsing)...")
    
    # プロンプトの構築
    user_input_text = f"""
    [黄土] Name: {identity.get('nickname')}, Special: {identity.get('special_existence')}, Smell: {identity.get('favorite_smell')}
    [青春] Noise(0)-Silence(4): {seishun.get('noise_silence')}, City(0)-Country(4): {seishun.get('city_country')}, Reality(0)-Fantasy(4): {seishun.get('reality_fantasy')}
    [朱夏] Hell Time (0:Past,1:Present,2:Future): {shuka.get('hell_time')}, Dream: {shuka.get('dream')}
    [白冬] Setback: {hakuto.get('setback')}, Lost/Release: {hakuto.get('lost_release')}
    [玄冬] Return (0:Sea,1:Soil,2:Sky): {gento.get('return_element')}, Go (0:North-4:South): {gento.get('go_north_south')}
    """
    
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_input_text}
    ]

    # 画像がある場合はGPT-4o Visionを使用
    if saved_image_path != "none":
        messages[1]["content"] = [
            {"type": "text", "text": user_input_text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data['image_data']}"}}
        ]

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            response_format={"type": "json_object"}
        )
        result_json = response.choices[0].message.content
        result_data = json.loads(result_json)
        
        # パス情報を追加
        result_data["original_image_path"] = saved_image_path
        
        # ★動画生成 (画像がある場合のみ)
        generated_video_path = "none"
        if saved_image_path != "none":
            generated_video_path = generate_video(saved_image_path)
        
        result_data["video_path"] = generated_video_path

        # 3. TouchDesignerへ送信 (OSC)
        final_json_str = json.dumps(result_data, ensure_ascii=False)
        osc_client.send_message("/karmic_data", final_json_str)
        
        print(">> Sent to TouchDesigner:")
        print(f"   Message: {result_data.get('poetic_message')}")
        print(f"   Video: {result_data.get('video_path')}")

    except Exception as e:
        print(f"AI Error: {e}")

# ==========================================
# WebSocket受信ループ
# ==========================================
async def listen():
    custom_headers = {"User-Agent": "Bridge/1.0"}
    
    while True:
        try:
            print(f">> 接続中: {WEBSOCKET_URL}")
            async with websockets.connect(WEBSOCKET_URL, additional_headers=custom_headers) as websocket:
                print("### 接続成功！データ待機中... ###")
                
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    
                    if data.get("type") == "satellite_image":
                        continue # スマホ画像転送イベントは無視
                        
                    if data.get("type") == "form_submission":
                        await process_data(data)

        except Exception as e:
            print(f"接続エラー: {e}")
            print("3秒後に再接続します...")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(listen())