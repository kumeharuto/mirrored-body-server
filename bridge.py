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
# サーバーURL (RenderのURL)
WEBSOCKET_URL = "wss://karmic-identity.onrender.com/ws"

# ★保存先をデスクトップに設定
desktop_path = os.path.expanduser("~/Desktop")
IMAGE_DIR = os.path.join(desktop_path, "Karma_Images")
VIDEO_DIR = os.path.join(desktop_path, "Karma_Videos")

# フォルダがなければ作る
os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)

# TD設定 (一旦無視してOKですがエラー防止のため残します)
OSC_IP = "127.0.0.1"
OSC_PORT = 9000

# ==========================================
# 画風・プロンプト設定 (ここを後でいじります)
# ==========================================
SYSTEM_PROMPT = """
あなたはインスタレーション作品『Karma Portrait』のシステムです。
入力された回答から「業（カルマ）」を解析し、JSONで出力してください。

【画風の指定 (Stability AI用)】
"visual_impression" には、以下のスタイルを含めた英語プロンプトを作成してください：
"Cinematic, Abstract, Spiritual atmosphere, High detail, 8k, Moving light particles, Deep emotional tone."
（具体的な物体よりも、光や霧、粒子などの抽象表現を重視すること）

【出力JSON】
{
  "visual_impression": "映像生成プロンプト(英語)",
  "emotion_valance": -1.0〜1.0,
  "emotion_arousal": 0.0〜1.0,
  "karma_color": "#RRGGBB",
  "poetic_message": "30文字以内の詩的な日本語メッセージ"
}
"""

print(f"Bridge System Starting...")
print(f"📂 画像保存先: {IMAGE_DIR}")
print(f"📂 動画保存先: {VIDEO_DIR}")

client = OpenAI(api_key=secret.OPENAI_KEY)
osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

# ==========================================
# 1. DALL-E 3 画像生成 (Text-to-Image)
# ==========================================
def generate_base_image(prompt):
    print(f"🎨 [1/2] ベース画像を生成中 (DALL-E 3)...")
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        
        img_data = requests.get(image_url).content
        filename = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
        save_path = os.path.join(IMAGE_DIR, filename)
        
        with open(save_path, 'wb') as f:
            f.write(img_data)
            
        print(f"✅ 画像保存完了: {filename}")
        return os.path.abspath(save_path)
        
    except Exception as e:
        print(f"❌ DALL-E エラー: {e}")
        return "none"

# ==========================================
# 2. Stability AI 動画生成 (Image-to-Video)
# ==========================================
def generate_video(image_path):
    print(f"🎬 [2/2] 動画生成を開始します (Stability AI)...")
    api_key = secret.STABILITY_KEY
    
    try:
        url = "https://api.stability.ai/v2beta/image-to-video"
        
        with open(image_path, "rb") as file:
            data_payload = {
                "seed": 0,
                "cfg_scale": 1.8,
                "motion_bucket_id": 127
            }
            response = requests.post(
                url,
                headers={"authorization": f"Bearer {api_key}"},
                files={"image": file},
                data=data_payload,
            )
            
        if response.status_code != 200:
            print(f"❌ 生成リクエスト失敗: {response.text}")
            return "none"
            
        generation_id = response.json().get('id')
        print(f"⏳ 生成中... (ID: {generation_id})")
        
        # 完了待ち
        for i in range(40): # 最大80秒
            time.sleep(2) 
            res = requests.get(
                f"{url}/result/{generation_id}",
                headers={'authorization': f"Bearer {api_key}", 'accept': "video/*"},
            )
            
            if res.status_code == 202:
                print(".", end="", flush=True)
                continue
            elif res.status_code == 200:
                print("\n✨ 動画生成完了！")
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                save_path = os.path.join(VIDEO_DIR, f"video_{timestamp}.mp4")
                with open(save_path, 'wb') as f:
                    f.write(res.content)
                print(f"✅ 動画をデスクトップに保存しました: {os.path.basename(save_path)}")
                return os.path.abspath(save_path)
            else:
                print(f"\n❌ エラー: {res.json()}")
                return "none"
                
        return "none"

    except Exception as e:
        print(f"❌ 動画生成例外: {e}")
        return "none"

# ==========================================
# メイン処理
# ==========================================
async def process_data(data):
    identity = data.get('identity', {})
    
    print("\n===================================")
    print(f"👤 受信: {identity.get('nickname')} さんのデータ")

    # 画像チェック
    saved_image_path = "none"
    has_user_image = False
    
    if data.get("has_image") and data.get("image_data"):
        try:
            b64_str = data["image_data"]
            if "base64," in b64_str: b64_str = b64_str.split("base64,")[1]
            image_data = base64.b64decode(b64_str)
            filename = f"user_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            saved_image_path = os.path.join(IMAGE_DIR, filename)
            with open(saved_image_path, "wb") as f:
                f.write(image_data)
            saved_image_path = os.path.abspath(saved_image_path)
            has_user_image = True
            print(f"📷 スマホ画像を保存しました")
        except Exception as e:
            print(f"画像保存エラー: {e}")

    # AI解析
    print("🧠 GPT-4o 解析中...")
    
    # プロンプト作成（前回と同じ）
    seishun = data.get('seishun', {})
    shuka = data.get('shuka', {})
    hakuto = data.get('hakuto', {})
    gento = data.get('gento', {})
    
    user_input_text = f"""
    [黄土] Name:{identity.get('nickname')}, Special:{identity.get('special_existence')}, Smell:{identity.get('favorite_smell')}
    [青春] Noise(0)-Silence(4):{seishun.get('noise_silence')}, City(0)-Country(4):{seishun.get('city_country')}, Reality(0)-Fantasy(4):{seishun.get('reality_fantasy')}
    [朱夏] Hell(0:Past,1:Pres,2:Fut):{shuka.get('hell_time')}, Dream:{shuka.get('dream')}
    [白冬] Setback:{hakuto.get('setback')}, Lost/Release:{hakuto.get('lost_release')}
    [玄冬] Return(0:Sea,1:Soil,2:Sky):{gento.get('return_element')}, Go(0:N-4:S):{gento.get('go_north_south')}
    """
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_input_text}]
    
    if has_user_image:
        messages[1]["content"] = [
            {"type": "text", "text": user_input_text},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{data['image_data']}"}}
        ]

    try:
        response = client.chat.completions.create(model="gpt-4o", messages=messages, response_format={"type": "json_object"})
        result_json = json.loads(response.choices[0].message.content)
        
        print(f"💬 メッセージ: {result_json.get('poetic_message')}")
        print(f"🎨 イメージ: {result_json.get('visual_impression')[:50]}...")

        # 画像がないならDALL-Eで作る
        if not has_user_image:
            print("🎨 画像がないため、AIが描画します...")
            prompt = result_json.get("visual_impression", "Abstract spiritual landscape")
            saved_image_path = generate_base_image(prompt)
        
        # 動画生成
        if saved_image_path != "none":
            video_path = generate_video(saved_image_path)
            
            # TDにも一応通知しておく（将来用）
            result_json["video_path"] = video_path
            osc_client.send_message("/karmic_data", json.dumps(result_json, ensure_ascii=False))

    except Exception as e:
        print(f"エラー: {e}")

# ==========================================
# 待機ループ
# ==========================================
async def listen():
    custom_headers = {"User-Agent": "Bridge/1.0"}
    while True:
        try:
            print(f">> サーバー接続中: {WEBSOCKET_URL}")
            async with websockets.connect(WEBSOCKET_URL, additional_headers=custom_headers) as websocket:
                print("### 接続成功！タブレットからの入力を待っています... ###")
                while True:
                    message = await websocket.recv()
                    data = json.loads(message)
                    if data.get("type") == "form_submission":
                        await process_data(data)
        except Exception as e:
            print(f"接続エラー（3秒後に再試行）: {e}")
            await asyncio.sleep(3)

if __name__ == "__main__":
    asyncio.run(listen())