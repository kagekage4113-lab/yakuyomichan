# -*- coding: utf-8 -*-
"""
「判定→(必要なら翻訳)→読み上げ」の一連の流れを、
実際のチャット監視より先に、手動でテストするためのスクリプト。

コンソールにテキストを打ち込むと、
lang_detect → translator → voicevox_speak の順に処理され、
選択中のVOICEVOXキャラが実際に読み上げる。

【前提】
- LM Studio(Gemma4 2B等)が起動していること
- VOICEVOXエンジンが起動していること
- selected_voice.json があれば、そのボイスを使う
  (無ければずんだもん ノーマル で代用)

【使い方】
python test_pipeline.py
(終了するには何も入力せずEnter、または Ctrl+C)
"""

import json
import os

from lang_detect import needs_translation
from translator import translate_to_japanese
from voicevox_speak import speak


def load_selected_style_id():
    if os.path.exists("selected_voice.json"):
        with open("selected_voice.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("style_id", 3), data.get("full_label", "(不明)")
    return 3, "ずんだもん(ノーマル) ※デフォルト"


def process_comment(text: str, style_id: int):
    """1件のコメントを、判定→翻訳→読み上げの順に処理する"""
    if needs_translation(text):
        print(f"  [判定] 翻訳が必要 → Gemma4に送信中...")
        translated = translate_to_japanese(text)
        print(f"  [翻訳結果] {translated}")
        speak(translated, style_id=style_id, blocking=True)
    else:
        print(f"  [判定] 翻訳不要 → そのまま読み上げ")
        speak(text, style_id=style_id, blocking=True)


def main():
    style_id, label = load_selected_style_id()
    print(f"読み上げボイス: {label} (style_id={style_id})")
    print("テキストを入力してEnterを押してください。(何も入力せずEnterで終了)")
    print("-" * 50)

    while True:
        text = input("コメント> ").strip()
        if not text:
            print("終了します。")
            break
        process_comment(text, style_id)
        print()


if __name__ == "__main__":
    main()
