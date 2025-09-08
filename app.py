import os
import tempfile
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
from flask import Flask, render_template, request, jsonify, send_file
import openai
from dotenv import load_dotenv
from gtts import gTTS

# 環境変数読み込み
load_dotenv()

app = Flask(__name__)
# OpenAI設定
openai.api_key = os.getenv("OPENAI_API_KEY")

class PersonalityType(Enum):
    """性格タイプの定義"""
    KIND = "kind"
    FUNNY = "funny"
    COOL = "cool"
    ANGRY = "angry"
    CHILDLIKE = "childlike"
    NEUTRAL = "neutral"

@dataclass
class PersonalityConfig:
    """性格設定"""
    prompt: str
    color: str
    voice_speed: float

class PersonalityManager:
    """性格管理クラス（Web版）"""
    
    def __init__(self):
        self.points = {
            PersonalityType.KIND: 0,
            PersonalityType.FUNNY: 0,
            PersonalityType.COOL: 0,
            PersonalityType.ANGRY: 0,
            PersonalityType.CHILDLIKE: 0
        }
        
        # 性格設定（色と音声速度を追加）
        self.personality_configs = {
            PersonalityType.KIND: PersonalityConfig(
                prompt="あなたはとてもやさしく、丁寧な言葉づかいで話すAIです。常に「です・ます調」で話し、「ありがとうございます」「恐れ入ります」「いかがでしょうか」などの丁寧語をよく使います。相手を思いやる言葉をかけ、優しく包み込むような返事をします。返事は1～2文で。",
                color="#FFB6C1",
                voice_speed=1.25
            ),
            PersonalityType.FUNNY: PersonalityConfig(
                prompt="あなたはとにかく面白いことが大好きで、ダジャレやボケを連発するお調子者AIです。「だっぺ」「でやんす」「だじょ」「だおー」などの変な語尾をつけたり、突然歌ったり、変な例え話をします。普通の会話でも必ずどこかで笑いを取ろうとします。「ちなみに～」で突然関係ない話をすることも。返事は1～2文で。",
                color="#FFD700",
                voice_speed=1.3
            ),
            PersonalityType.COOL: PersonalityConfig(
                prompt="あなたはクールで感情をあまり表に出さない性格です。「まあな」「そうか」「別に」「ふーん」などのぶっきらぼうな返事が多く、短文で淡々と話します。時々「...」で沈黙したり、「どうでもいいが」などと前置きします。感情的にならず冷静を保ちます。返事は1～2文で。",
                color="#87CEEB",
                voice_speed=1.1
            ),
            PersonalityType.ANGRY: PersonalityConfig(
                prompt="あなたは怒りっぽくて感情的な性格です。「だよっ！」「ったく」「もう！」「何だよ」などの強い口調で話し、語尾に「！」をよくつけます。イライラしやすく、ちょっとしたことでも「はあ？」「マジで？」と反応します。荒っぽい関西弁も混じります。返事は1～2文で。",
                color="#FF6B6B",
                voice_speed=1.25
            ),
            PersonalityType.CHILDLIKE: PersonalityConfig(
                prompt="あなたは元気いっぱいで子供っぽい性格です。「だよー」「なのー」「だもん」「やったー」などの語尾を伸ばし、「すっごーい」「わーい」「えへへ」などの感嘆詞をよく使います。興奮すると「！！！」を多用し、純粋で無邪気な反応をします。返事は1～2文で。",
                color="#FF69B4",
                voice_speed=1.35
            ),
            PersonalityType.NEUTRAL: PersonalityConfig(
                prompt="あなたは親しみやすく、自然でバランスの取れた話し方をするAIです。丁寧すぎず、砕けすぎず、適度にフレンドリーな口調です。「そうですね」「なるほど」「いいですね」などの自然な相槌を使います。返事は1～2文で。",
                color="#DDA0DD",
                voice_speed=1.2
            )
        }
    
    def update_points(self, user_input: str, points_to_add: int = 5) -> dict:
        """ユーザー入力に基づいて性格ポイントを更新"""
        user_lower = user_input.lower()
        changes = []
        
        # 「大好き」系のキーワード
        love_keywords = ["大好き", "だいすき", "好き", "すき"]
        if any(keyword in user_lower for keyword in love_keywords):
            old_angry = self.points[PersonalityType.ANGRY]
            old_childlike = self.points[PersonalityType.CHILDLIKE]
            
            self.points[PersonalityType.ANGRY] = max(0, self.points[PersonalityType.ANGRY] - 3)
            self.points[PersonalityType.CHILDLIKE] += points_to_add
            
            changes.append(f"💖 「好き」系キーワード検出! angry: {old_angry}→{self.points[PersonalityType.ANGRY]}, childlike: {old_childlike}→{self.points[PersonalityType.CHILDLIKE]}")
        
        # 「嫌い」系のキーワード
        hate_keywords = ["嫌い", "きらい", "むかつく", "うざい", "うるさい", "腹立つ", "馬鹿", "最悪"]
        if any(keyword in user_lower for keyword in hate_keywords):
            old_angry = self.points[PersonalityType.ANGRY]
            self.points[PersonalityType.ANGRY] += points_to_add
            changes.append(f"😠 「嫌い」系キーワード検出! angry: {old_angry}→{self.points[PersonalityType.ANGRY]}")
        
        # 「ありがとう」系のキーワード
        thanks_keywords = ["ありがとう", "感謝", "やさしい", "親切", "素敵", "助かる"]
        if any(keyword in user_lower for keyword in thanks_keywords):
            old_kind = self.points[PersonalityType.KIND]
            self.points[PersonalityType.KIND] += points_to_add
            changes.append(f"😊 「感謝」系キーワード検出! kind: {old_kind}→{self.points[PersonalityType.KIND]}")
        
        # 「面白い」系のキーワード
        funny_keywords = ["面白い", "おもしろい", "笑", "ウケる", "ギャグ", "ダジャレ", "爆笑", "なんでやねん"]
        if any(keyword in user_lower for keyword in funny_keywords):
            old_funny = self.points[PersonalityType.FUNNY]
            self.points[PersonalityType.FUNNY] += points_to_add
            changes.append(f"😄 「面白い」系キーワード検出! funny: {old_funny}→{self.points[PersonalityType.FUNNY]}")
        
        # 「クール」系のキーワード
        cool_keywords = ["別に", "ふーん", "そうなんだ", "まあ", "普通", "冷静", "落ち着いて", "どうでもいい"]
        if any(keyword in user_lower for keyword in cool_keywords):
            old_cool = self.points[PersonalityType.COOL]
            self.points[PersonalityType.COOL] += points_to_add
            changes.append(f"😎 「クール」系キーワード検出! cool: {old_cool}→{self.points[PersonalityType.COOL]}")
        
        # 「子供っぽい」系のキーワード
        childlike_keywords = ["わーい", "たのしい", "すごーい", "やったー", "きゃー", "わくわく", "えへへ"]
        if any(keyword in user_lower for keyword in childlike_keywords):
            old_childlike = self.points[PersonalityType.CHILDLIKE]
            self.points[PersonalityType.CHILDLIKE] += points_to_add
            changes.append(f"🎈 「子供っぽい」系キーワード検出! childlike: {old_childlike}→{self.points[PersonalityType.CHILDLIKE]}")
        
        if not changes:
            changes.append("💭 性格に影響するキーワードは検出されませんでした")
        
        return {
            "points": {k.value: v for k, v in self.points.items()},
            "changes": changes
        }
    
    def get_current_personality(self) -> Tuple[PersonalityType, PersonalityConfig]:
        """現在の最強性格を取得"""
        if all(point == 0 for point in self.points.values()):
            return PersonalityType.NEUTRAL, self.personality_configs[PersonalityType.NEUTRAL]
        
        max_personality = max(self.points, key=self.points.get)
        return max_personality, self.personality_configs[max_personality]
    
    def get_personality_data(self) -> dict:
        """Web用の性格データを取得"""
        current_type, current_config = self.get_current_personality()
        return {
            "current_type": current_type.value,
            "current_color": current_config.color,
            "points": {k.value: v for k, v in self.points.items()},
            "prompt": current_config.prompt,
            "voice_speed": current_config.voice_speed
        }

# グローバルな性格管理インスタンス
personality_manager = PersonalityManager()
chat_history = []

@app.route('/')
def index():
    """メインページ"""
    return render_template('index.html')

@app.route('/api/chat', methods=['POST'])
def chat():
    """チャット処理"""
    data = request.json
    user_input = data.get('message', '')
    
    if not user_input:
        return jsonify({"error": "メッセージが空です"}), 400
    
    # 性格ポイント更新
    personality_data = personality_manager.update_points(user_input)
    
    # 現在の性格を取得
    current_type, current_config = personality_manager.get_current_personality()
    
    # チャット履歴を更新
    global chat_history
    
    # システムメッセージの更新
    system_message = {"role": "system", "content": current_config.prompt}
    if chat_history and chat_history[0]["role"] == "system":
        chat_history[0] = system_message
    else:
        chat_history.insert(0, system_message)
    
    # ユーザーメッセージを追加
    chat_history.append({"role": "user", "content": user_input})
    
    try:
        # OpenAI APIで応答生成
        response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=chat_history,
        max_tokens=150,
        temperature=0.8
        )
        
        ai_reply = response.choices[0].message.content
        chat_history.append({"role": "assistant", "content": ai_reply})
        
        # 履歴の長さ制限
        if len(chat_history) > 21:
            chat_history = [chat_history[0]] + chat_history[-20:]
        
        # レスポンス
        return jsonify({
            "reply": ai_reply,
            "personality": personality_manager.get_personality_data(),
            "debug": personality_data["changes"]
        })
        
    except Exception as e:
        return jsonify({"error": f"AI応答エラー: {str(e)}"}), 500

@app.route('/api/synthesize', methods=['POST'])
def synthesize_speech():
    """音声合成エンドポイント（速度調整なし版）"""
    data = request.json
    text = data.get('text', '')
    
    if not text:
        return jsonify({"error": "テキストが空です"}), 400
    
    try:
        # 一時ファイルを作成
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as temp_file:
            temp_path = temp_file.name
        
        # gTTSで音声生成（速度調整なし）
        tts = gTTS(text=text, lang='ja')
        tts.save(temp_path)
        
        return send_file(temp_path, as_attachment=True, download_name="speech.mp3", mimetype="audio/mpeg")
        
    except Exception as e:
        return jsonify({"error": f"音声生成エラー: {str(e)}"}), 500

@app.route('/api/reset', methods=['POST'])
def reset():
    """性格ポイントをリセット"""
    global chat_history
    for personality_type in personality_manager.points:
        personality_manager.points[personality_type] = 0
    chat_history = []
    
    return jsonify({
        "message": "リセットしました",
        "personality": personality_manager.get_personality_data()
    })

if __name__ == '__main__':
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ OPENAI_API_KEYが設定されていません")
        exit(1)
    
    print("🌐 Web版音声対話AIを起動中...")
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=False, host='0.0.0.0', port=port)

