import asyncio
import json
import os
import base64
import time
import requests 
import shutil
import subprocess
from datetime import datetime
import traceback

import websockets
from pythonosc import udp_client
from openai import OpenAI
import fal_client

# 秘密鍵の読み込み
import secret

# ==========================================
# 設定エリア
# ==========================================
WEBSOCKET_URL = os.getenv("KARMA_URL", "wss://karmic-identity.onrender.com/ws")  # 本番
# WEBSOCKET_URL = "ws://localhost:8765"                      # ★ローカル

# (フォルダがなければ自動生成されます)
base_path = os.path.join(os.path.expanduser("~"), "Ryoshian", "System", "renderData")
print(f"📌 base_path: {base_path}")
IMAGE_DIR = os.path.join(base_path, "Karma_Images")
VIDEO_DIR = os.path.join(base_path, "Karma_Videos")
TEXT_DIR = os.path.join(base_path, "Karma_Texts")

os.makedirs(IMAGE_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
os.makedirs(TEXT_DIR, exist_ok=True)

# TouchDesigner設定
OSC_IP = "127.0.0.1"
OSC_PORT = 9000

# ==========================================
# システムプロンプト (美大指定仕様)
# ==========================================
SYSTEM_PROMPT = """
あなたはインスタレーション作品『Karma Portrait』のブリッジシステムです。
入力された回答から「業（カルマ）」を解析し、TouchDesignerへ渡すためのJSONを出力してください。

【最重要ルール】
- 文字は絶対に生成しない：英語プロンプト内に "no text" を必ず入れ、看板・字幕・ロゴ・透かし・文字要素を一切含めない。
- 人間は極力生成しない：人物・顔・身体表現を避ける。どうしても必要な場合のみ、個性のない集団として描写する（例：スーツの群衆、後ろ姿、シルエット、顔は映さず曖昧、個体識別不可）。
- 【最優先】カメラが動く：ドリーイン/アウト、トラッキング、緩いハンドヘルドの漂い、強いパララックス（前景/中景/遠景のレイヤー）を必ず含める。被写体の動きよりカメラ移動を優先。
- 動きは「画角移動が主役」：被写体の派手な動き（激しい波・大人数の激しい動き）が強すぎてカメラが止まって見える場合は、被写体側の動きを抑え、前景の流れ＋奥行きレイヤーでパララックスを作る。
- 画像生成段階で奥行きを作る：極端な前景（カメラに近い枝/葦/石/柵/提灯のボケ）、中景、遠景を必ず用意し、広角寄りでレイヤー差を強調する。
- 架空の南国/北国/都市/田舎は禁止：必ず「現実に存在する具体的スポット（地名+国/都市名）」を選び、プロンプトに明記する。
- 浄土らしい質感を重視：清澄・発光・霧・金箔/白磁/乳白のような光、静謐だが強い生命感（清らかな粒子・柔らかな光芒）を表現。

【テイスト選択（回答から自動で選ぶ）】
- approach (旧reality_fantasy相当) が現実寄り（0〜1）→ `Hyper-realistic photography`（写実/高精細）
- 中間（2）→ `Cinematic CG`（写実寄りCG）
- 空想寄り（3〜4）→ `Abstract generative`（抽象ベース）

【ロケーション選択（具体スポットを必ず1つ）】
- 架空の南国/北国/都市/田舎は禁止：必ず「現実に存在する具体的スポット（地名 + 都市/県/国）」を選び、プロンプトに明記する。
- 同じ回答の中で2本生成する場合は、Variant A / Variant B でロケーションを絶対に被らせない（国/都道府県レベルでも別にする）。

▼都市寄り（environment_place が 0〜1）
- 例（日本）: Shibuya Scramble Crossing, Tokyo / Ginza, Tokyo / Yokohama Minato Mirai, Kanagawa / Dotonbori, Osaka / Susukino, Sapporo, Hokkaido
- 例（東アジア）: Central, Hong Kong / Shinjuku Kabukicho, Tokyo / Taipei Ximending, Taipei / Gangnam, Seoul
- 例（世界）: Times Square, New York / Piccadilly Circus, London / Place de la République, Paris / Marina Bay, Singapore

▼田舎・自然寄り（environment_place が 3〜4）
- 例（日本・北）: Otaru Canal, Hokkaido / Lake Towada, Aomori / Shiretoko Peninsula, Hokkaido / Daisetsuzan National Park, Hokkaido
- 例（日本・中部）: Shirakawa-go, Gifu / Kamikochi, Nagano / Kurobe Gorge, Toyama / Nakasendo (Magome–Tsumago), Nagano–Gifu
- 例（日本・西）: Naoshima Island, Kagawa / Itsukushima Shrine (Miyajima), Hiroshima / Amanohashidate, Kyoto / Tottori Sand Dunes, Tottori

▼仏教思想・巡礼/霊場の気配（日本に合う要素）
- 例: Koyasan (Mount Koya), Wakayama / Kumano Kodo (Nakahechi Route), Wakayama / Eiheiji Temple, Fukui / Zenkoji Temple, Nagano
- 例: Nachi Falls, Wakayama / Mount Hiei (Enryakuji), Shiga / Dewa Sanzan (Mount Haguro), Yamagata / Osorezan, Aomori
- 例: Senso-ji, Asakusa, Tokyo / Ryoan-ji, Kyoto / Tofuku-ji, Kyoto / Todai-ji, Nara

▼沖縄（南国だが“現実の場所”で、過度にリゾート化しない）
- 例: Shurijo Castle, Naha, Okinawa / Cape Manzamo, Onna, Okinawa / Taketomi Island, Okinawa / Iriomote Island mangrove forests, Okinawa / Ishigaki Kabira Bay, Okinawa

▼東南アジア（湿度/香/祈りのディテールに強い）
- 例: Angkor Wat, Siem Reap, Cambodia / Borobudur Temple, Central Java, Indonesia / Bagan Archaeological Zone, Myanmar
- 例: Luang Prabang temples, Laos / Chiang Mai Old City temples, Thailand / Ha Long Bay, Vietnam

▼北欧（北の光・雪・静けさ、ミニマルな構図）
- 例: Tromsø, Norway / Lofoten Islands, Norway / Reykjavik, Iceland / Thingvellir National Park, Iceland / Bergen Bryggen, Norway
- 例: Stockholm Gamla Stan, Sweden / Copenhagen Nyhavn, Denmark

▼要素（Return）との整合
- Return(0:Sea) なら海・運河・湾・潮のある場所を優先（ただし動きは水面ではなく「カメラ移動（パララックス）」を主役にする）
- Return(1:Soil) なら森・山・寺社の参道・石畳・土の匂いのある場所を優先
- Return(2:Sky) なら高所・広い空・雲・光芒・極光/朝焼け/薄明などを優先

▼北/南（heading）による方向づけ（ただし架空は禁止）
- 北寄り（0〜1）: 北海道/東北/北欧/高緯度（雪・薄明・冷気）
- 南寄り（3〜4）: 沖縄/東南アジア（湿度・濃い影・水面の反射）

※同じ入力から2本生成する場合は、次の「被り禁止」を必ず守る:
- ロケーション（都道府県/国レベルで別）
- 季節/天候（例: 雪 vs 雨上がり、霧 vs 強い日差し）
- 時刻（例: 夜明け vs 夜、夕景 vs 曇天）
- 主素材（例: 白磁/石/木/水面/金箔のどれを強調するか）
- カメラの動き（ドリー主体 vs トラッキング主体、前景の流れ方を変える）

【出力】
- visual_impression には、DALL·E 3 に渡す「英語プロンプト」を生成する。
- 英語プロンプトには必ず次を含める：
  - Vertical composition / Cinematic lighting
  - 【最優先】`Dynamic camera movement`（slow dolly-in/out, tracking shot, subtle handheld drift, strong parallax, foreground elements passing very close to camera, clear horizon shift / background parallax）
  - 「被写体の派手な動き」に頼らない：波・群衆・粒子などのローカル運動は控えめにし、画角移動（カメラ）で動きを作る
  - no text, no letters, no typography, no logo, no watermark, no subtitles
  - `no people`（人物が必要なら `anonymous crowd silhouettes, no faces, no identifiable features`）
  - 具体スポット名（地名 + 都市/国）
  - 天候・気候・時間帯を入力語彙に合わせて変える：clear / overcast / rain / snow / fog / humid haze / storm、時間帯は dawn / morning / daytime / sunset / night / midnight のいずれかを必ず明記する
  - `Leica-like filmic color science`（subtle film grain, gentle highlight roll-off, rich blacks, micro-contrast, natural yet cinematic tones; avoid oversaturated look）
  
【出力JSON】
{
  "variants": [
    {
      "variant_id": "A",
      "visual_impression": "English image prompt",
      "emotion_valance": -1.0〜1.0,
      "emotion_arousal": 0.0〜1.0,
      "karma_color": "#RRGGBB",
      "poetic_message": "30文字以内の詩的な日本語メッセージ",
      "location": "Selected real-world spot name",
      "style_mode": "Hyper-realistic photography | Cinematic CG | Abstract generative"
    },
    {
      "variant_id": "B",
      "visual_impression": "English image prompt (must be clearly different from A)",
      "emotion_valance": -1.0〜1.0,
      "emotion_arousal": 0.0〜1.0,
      "karma_color": "#RRGGBB",
      "poetic_message": "30文字以内の詩的な日本語メッセージ",
      "location": "Selected real-world spot name (must be different from A)",
      "style_mode": "Hyper-realistic photography | Cinematic CG | Abstract generative"
    }
  ]
}
"""

print(f"Bridge System Starting (v9.0 - Ryoshian New Form Edition)...")
print(f"📂 画像保存先: {IMAGE_DIR}")
print(f"📂 動画保存先: {VIDEO_DIR}")
print(f"📂 テキスト保存先: {TEXT_DIR}")

# クライアント初期化
client = OpenAI(api_key=secret.OPENAI_KEY)
os.environ["FAL_KEY"] = secret.FAL_KEY
osc_client = udp_client.SimpleUDPClient(OSC_IP, OSC_PORT)

# ==========================================
# 1. DALL-E 3 画像生成
# ==========================================
def generate_base_image(prompt):
    print(f"🎨 [1/2] ベース画像を生成中 (DALL-E 3)...")
    # プロンプトに追加の安全策を結合
    safety_suffix = ", vertical composition, cinematic lighting, strong depth layers (foreground very close to lens, midground subject, distant background), wide-angle perspective (24mm), strong parallax, dynamic camera movement (slow dolly-in/out, tracking shot, subtle handheld drift), camera movement is the main motion (avoid relying only on subject motion), Leica-like filmic color science (subtle film grain, gentle highlight roll-off, rich blacks, micro-contrast, natural cinematic tones, avoid oversaturation), no text, no letters, no typography, no logo, no watermark, no subtitles, no people (or anonymous crowd silhouettes with no faces and no identifiable features only if absolutely necessary)"
    
    try:
        response = client.images.generate(
            model="dall-e-3",
            prompt=prompt + safety_suffix,
            size="1024x1792", 
            quality="standard",
            n=1,
        )
        image_url = response.data[0].url
        
        img_data = requests.get(image_url).content
        filename = f"gen_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        save_path = os.path.join(IMAGE_DIR, filename)
        with open(save_path, 'wb') as f:
            f.write(img_data)
            
        print(f"✅ 画像保存完了: {filename}")
        return os.path.abspath(save_path)
    except Exception as e:
        print(f"❌ DALL-E エラー: {e}")
        return "none"

# ==========================================
# SVD用: 入力画像を 576x1024 に正規化（必要に応じて）
# SVDは 576x1024 前提で学習されているため、ここで揃えるとクロップ/伸びが減りやすい
# ==========================================
def prepare_svd_frame(image_path: str) -> str:
    try:
        # 入力が既に 576x1024 ならそのまま
        try:
            from PIL import Image  # type: ignore
            with Image.open(image_path) as im:
                w, h = im.size
                if (w, h) == (576, 1024):
                    return image_path
        except Exception:
            # Pillow が無い/読めない場合は ffmpeg で試す
            pass

        out_path = os.path.join(IMAGE_DIR, f"svd_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg")

        # ffmpeg が使えるならそれでスケール（一番安定）
        if shutil.which("ffmpeg"):
            # 9:16維持で 576x1024 へ（不足分はセンターで軽くトリムされる）
            cmd = [
                "ffmpeg", "-y", "-i", image_path,
                "-vf", "scale=576:1024:force_original_aspect_ratio=increase,crop=576:1024",
                "-q:v", "2",
                out_path,
            ]
            subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
            return os.path.abspath(out_path)

        # Pillow が使えるならそれでリサイズ
        try:
            from PIL import Image  # type: ignore
            with Image.open(image_path) as im:
                im = im.convert("RGB")
                # まず高さを1024に合わせ、余った幅を中央トリム
                scale = 1024 / im.size[1]
                new_w = int(round(im.size[0] * scale))
                im2 = im.resize((new_w, 1024))
                if new_w > 576:
                    left = (new_w - 576) // 2
                    im2 = im2.crop((left, 0, left + 576, 1024))
                elif new_w < 576:
                    # 足りない分は左右に黒パッド（稀）
                    pad = (576 - new_w) // 2
                    canvas = Image.new("RGB", (576, 1024), (0, 0, 0))
                    canvas.paste(im2, (pad, 0))
                    im2 = canvas
                im2.save(out_path, quality=95)
                return os.path.abspath(out_path)
        except Exception:
            return image_path

    except Exception:
        return image_path

# ==========================================
# 静止画っぽい動画の簡易検出（ffmpeg がある場合のみ）
# fps=2でフレームのmd5を取り、ユニーク数が少なければ「ほぼ静止」とみなす
# ==========================================
def looks_static_video(video_path: str) -> bool:
    try:
        if not shutil.which("ffmpeg"):
            return False

        cmd = [
            "ffmpeg", "-v", "error",
            "-i", video_path,
            "-vf", "fps=2",
            "-f", "framemd5",
            "-"
        ]
        p = subprocess.run(cmd, capture_output=True, text=True, check=True)
        hashes = []
        for line in p.stdout.splitlines():
            if not line or line.startswith("#"):
                continue
            parts = line.strip().split(",")
            if len(parts) >= 6:
                md5 = parts[-1].strip()
                if md5:
                    hashes.append(md5)
        if len(hashes) < 4:
            return False
        uniq = len(set(hashes))
        # ほぼ全部同じなら静止画の可能性が高い
        return uniq <= 2
    except Exception:
        return False

# ==========================================
# 2. Fal.ai 動画生成 (SVD)
# ==========================================
def generate_video(image_path, motion_bucket_id: int = 170, cond_aug: float = 0.05):
    print(f"🎬 [2/2] 動画生成を開始します (Fal.ai)...")
    
    try:
        # SVDが得意な解像度(576x1024)に揃えると、上下/左右クロップのブレが減りやすい
        image_path = prepare_svd_frame(image_path)
        # 画像アップロード
        print("   - 画像をアップロード中...")
        url = fal_client.upload_file(image_path)
        
        # 生成リクエスト
        print("   - 生成リクエスト送信...")
        handler = fal_client.submit(
            "fal-ai/fast-svd",
            arguments={
                "image_url": url,
                "motion_bucket_id": motion_bucket_id,
                "cond_aug": cond_aug,
            }
        )

        result = handler.get()
        print(f"   - SVD params: motion_bucket_id={motion_bucket_id}, cond_aug={cond_aug}")
        
        if "video" in result and "url" in result["video"]:
            video_url = result["video"]["url"]
            print("✨ 生成完了！ ダウンロードします...")
            
            vid_data = requests.get(video_url).content
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            save_path = os.path.join(VIDEO_DIR, f"video_{timestamp}.mp4")
            
            with open(save_path, 'wb') as f:
                f.write(vid_data)
                
            print(f"✅ 保存完了: {os.path.basename(save_path)}")
            saved = os.path.abspath(save_path)

            # たまに静止画っぽい動画が出るので、カメラ移動を強めて1回だけ自動リトライ
            if looks_static_video(saved):
                print("⚠️ 静止画っぽい動画を検出。カメラ移動を強めて再生成します...")
                try:
                    # 少し強めの設定（被写体運動ではなく画角移動を狙う）
                    return generate_video(image_path, motion_bucket_id=220, cond_aug=min(cond_aug + 0.02, 0.08))
                except Exception:
                    return saved

            return saved
        else:
            print(f"❌ エラー: 結果異常 {result}")
            return "none"

    except Exception as e:
        print(f"❌ 動画生成例外: {e}")
        return "none"

# ==========================================
# メイン処理フロー
# ==========================================
async def process_data(data):
    # 新しいデータ構造に合わせて展開
    identity = data.get('identity', {})
    conditions = data.get('conditions', {})
    adolescence = data.get('adolescence', {})
    adulthood = data.get('adulthood', {})
    philosophy = data.get('philosophy', {})
    afterlife = data.get('afterlife', {})
    legacy = data.get('legacy', {})

    print("\n===================================")
    print(f"👤 受信: {identity.get('nickname')} さんのデータ")

    # --- 入力パラメータをテキストとして保存 ---
    try:
        nickname = identity.get('nickname') or "anonymous"
        # ファイル名に使えるよう簡易サニタイズ
        nickname_safe = "".join(c for c in str(nickname) if c.isalnum() or c in "-_" )
        if not nickname_safe:
            nickname_safe = "anonymous"

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        text_filename = f"input_{timestamp}_{nickname_safe}.txt"
        text_save_path = os.path.join(TEXT_DIR, text_filename)

        # 画像データが巨大なのでログではサイズ情報に置換
        data_for_log = dict(data)
        if "image_data" in data_for_log and data_for_log["image_data"]:
            data_for_log["image_data"] = f"<base64 image_data: {len(str(data_for_log['image_data']))} chars>"

        summary_text = f"""Karma Portrait / Input Log
Timestamp: {timestamp}
Nickname: {nickname}

[Identity]
- nickname: {identity.get('nickname')}
- age: {identity.get('age')}
- color: {identity.get('color')}

[Conditions]
- time: {conditions.get('time')}
- weather: {conditions.get('weather')}
- season: {conditions.get('season')}

[Adolescence]
- approach: {adolescence.get('approach')}
- place: {adolescence.get('environment_place')}
- sound: {adolescence.get('environment_sound')}
- sense: {adolescence.get('environment_sense')}
- scent: {adolescence.get('scent')}

[Adulthood]
- destination: {adulthood.get('destination')}
- wish: {adulthood.get('wish_direction')}
- drive: {adulthood.get('drive')}

[Philosophy]
- causality: {philosophy.get('causality')}
- compassion: {philosophy.get('compassion')}
- impermanence: {philosophy.get('impermanence')}
- life_death: {philosophy.get('life_death')}

[Afterlife]
- heading: {afterlife.get('heading')}
- returning: {afterlife.get('returning')}

[Legacy]
- keep: {legacy.get('keep')}
- likes: {legacy.get('likes')}
- avoids: {legacy.get('avoids')}

[Raw JSON (image_data omitted / summarized)]
{json.dumps(data_for_log, ensure_ascii=False, indent=2)}
"""

        with open(text_save_path, "w", encoding="utf-8") as f:
            f.write(summary_text)

        print(f"📝 入力テキストを保存しました: {os.path.basename(text_save_path)}")
    except Exception as e:
        print(f"⚠️ 入力テキスト保存エラー: {e}")
    # --- 保存ここまで ---

    saved_image_path = "none"
    has_user_image = False
    user_image_path = "none"
    
    # スマホ画像処理（保存はするが、動画生成には直接使わずGPTのヒントにする）
    if data.get("has_image") and data.get("image_data"):
        try:
            b64_str = data["image_data"]
            if "base64," in b64_str: b64_str = b64_str.split("base64,")[1]
            image_data = base64.b64decode(b64_str)
            filename = f"user_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
            saved_image_path = os.path.join(IMAGE_DIR, filename)
            with open(saved_image_path, "wb") as f:
                f.write(image_data)
            saved_image_path = os.path.abspath(saved_image_path)
            user_image_path = saved_image_path
            has_user_image = True
            print(f"📷 スマホ画像を保存しました (解析用)")
        except Exception as e:
            print(f"画像保存エラー: {e}")

    print("🧠 GPT-4o 解析中...")
    
    # 新しいデータ構造でプロンプト作成
    user_input_text = f"""
    [Identity] Name:{identity.get('nickname')}, Age:{identity.get('age')}, Color:{identity.get('color')}
    [Conditions] Time(0-3):{conditions.get('time')}, Weather(0-4):{conditions.get('weather')}, Season(0-3):{conditions.get('season')}
    [Adolescence] Approach(0-4):{adolescence.get('approach')}, Place(0-4):{adolescence.get('environment_place')}, Sound(0-4):{adolescence.get('environment_sound')}, Sense(0-4):{adolescence.get('environment_sense')}, Scent(0-4):{adolescence.get('scent')}
    [Adulthood] Dest:{adulthood.get('destination')}, Wish(0-2):{adulthood.get('wish_direction')}, Drive(0-4):{adulthood.get('drive')}
    [Philosophy] Causal(0-4):{philosophy.get('causality')}, Compassion(0-4):{philosophy.get('compassion')}, Impermanence(0-4):{philosophy.get('impermanence')}, LifeDeath(0-1):{philosophy.get('life_death')}
    [Afterlife] Heading(0-4):{afterlife.get('heading')}, Returning(0-2):{afterlife.get('returning')}
    [Legacy] Keep:{legacy.get('keep')}, Likes:{legacy.get('likes')}, Avoids:{legacy.get('avoids')}
    """
    
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_input_text}]
    
    # 画像がある場合、GPTに視覚情報として渡す
    if has_user_image:
        image_b64 = data.get("image_data", "")
        if "base64," in image_b64: image_b64 = image_b64.split("base64,", 1)[1]
        
        # Base64が極端に長くないか確認（エラー回避）
        if len(image_b64) < 2000000:
            messages[1]["content"] = [
                {"type": "text", "text": user_input_text},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}}
            ]
        else:
            print("⚠️ 画像サイズ過大のため、テキストのみで解析します")

    try:
        response = await asyncio.to_thread(
            lambda: client.chat.completions.create(
                model="gpt-4o",
                messages=messages,
                response_format={"type": "json_object"}
            )
        )

        msg = response.choices[0].message
        content = getattr(msg, "content", None)
        
        if not content:
            raise ValueError("GPT returned empty content")

        result_json = json.loads(content)

        variants = []
        if isinstance(result_json, dict) and isinstance(result_json.get("variants"), list):
            variants = result_json["variants"]
        else:
            # 旧形式（単発）にも互換
            variants = [result_json]

        # 必ず最大2本にする
        variants = variants[:2]

        # ログ表示
        for i, v in enumerate(variants):
            vid = v.get("variant_id") or str(i)
            print(f"💬 ({vid}) メッセージ: {v.get('poetic_message')}")
            print(f"📍 ({vid}) ロケーション: {v.get('location')}")

    except Exception as e:
        print(f"⚠️ GPT解析エラー(フォールバックを使用): {e}")
        # エラー時の安全策（止まらないようにデフォルト値をセット）
        result_json = {
            "variants": [
                {
                    "variant_id": "A",
                    "visual_impression": "Vertical abstract spiritual seascape, milky haze, soft light particles, strong parallax, slow dolly-in, no text, no people",
                    "emotion_valance": 0.0,
                    "emotion_arousal": 0.5,
                    "karma_color": "#EAF2FF",
                    "poetic_message": "光の粒子が、静かに降り注ぐ",
                    "location": "Naoshima Island, Kagawa, Japan",
                    "style_mode": "Abstract generative"
                },
                {
                    "variant_id": "B",
                    "visual_impression": "Vertical hyper-realistic photography of a quiet temple approach with wet stone path after rain, gentle mist, sacred god rays, strong parallax, tracking shot, Leica-like filmic color science, no text, no people",
                    "emotion_valance": 0.1,
                    "emotion_arousal": 0.45,
                    "karma_color": "#FFF3E6",
                    "poetic_message": "雨の名残りが、道を磨く",
                    "location": "Koyasan (Mount Koya), Wakayama, Japan",
                    "style_mode": "Hyper-realistic photography"
                }
            ]
        }
        variants = result_json["variants"]

    # === 画像/動画生成フェーズ（2本） ===
    outputs = []
    for i, v in enumerate(variants):
        vid = v.get("variant_id") or str(i)
        prompt = v.get("visual_impression", "Vertical abstract spiritual landscape")
        print(f"🎨 ({vid}) プロンプトからAI画像を生成します...")

        video_input_path = await asyncio.to_thread(generate_base_image, prompt)

        # 万が一AI画像生成に失敗し、スマホ画像がある場合のみバックアップとして使用
        if video_input_path == "none" and has_user_image:
            print(f"⚠️ ({vid}) AI生成失敗。バックアップとしてスマホ画像を使用します。")
            video_input_path = user_image_path

        if video_input_path != "none":
            video_path = await asyncio.to_thread(generate_video, video_input_path)
            v["video_path"] = video_path
            v["variant_index"] = i
            outputs.append(v)
        else:
            print(f"❌ ({vid}) 画像生成に失敗したため、このVariantの処理をスキップします")

    # TouchDesignerへ送信（互換: 旧 /karmic_data はAを送る）
    if outputs:
        # 旧互換: 最初の1本を /karmic_data
        osc_client.send_message("/karmic_data", json.dumps(outputs[0], ensure_ascii=False))

        # 新: 2本を個別アドレスで送る
        for out in outputs:
            idx = out.get("variant_index", 0)
            osc_client.send_message(f"/karmic_data/{idx}", json.dumps(out, ensure_ascii=False))

        # 新: まとめて送る（必要ならTD側で利用）
        osc_client.send_message("/karmic_data_bundle", json.dumps({"variants": outputs}, ensure_ascii=False))

        print("📡 TouchDesignerへデータを送信しました（/karmic_data, /karmic_data/0.., /karmic_data_bundle）")
    else:
        print("❌ すべてのVariantで生成に失敗したため、送信をスキップします")

# ==========================================
# 待機ループ (修正版: 接続強化)
# ==========================================
async def listen():
    custom_headers = {"User-Agent": "Bridge/1.0"}
    print(f"🚀 サーバー({WEBSOCKET_URL})に接続を開始します...")
    
    while True:
        try:
            async with websockets.connect(
                WEBSOCKET_URL, 
                additional_headers=custom_headers, 
                ping_interval=None, 
                ping_timeout=None,
                close_timeout=100
            ) as websocket:
                print("✅ 接続成功！待機中... (Ctrl+Cで停止)")
                
                while True:
                    try:
                        message = await websocket.recv()
                        data = json.loads(message)
                        if data.get("type") == "form_submission":
                            await process_data(data)
                    except websockets.exceptions.ConnectionClosed:
                        print("⚠️ 切断されました。再接続します...")
                        break
                    except Exception as e:
                        print(f"⚠️ 受信エラー: {e}")
                        
        except Exception as e:
            print(f"❌ 接続失敗（5秒後に再試行）: {e}")
            await asyncio.sleep(5)

# ==========================================
# 実行エントリーポイント (エラー時待機機能付き)
# ==========================================
if __name__ == "__main__":
    try:
        # この行がないとループに入りません
        asyncio.run(listen())
    except KeyboardInterrupt:
        print("\n🛑 システムを停止しました")
    except Exception as e:
        print(f"\n❌ システムクラッシュ: {e}")
        traceback.print_exc()
        print("\nENTERキーを押すと終了します...")
        input()