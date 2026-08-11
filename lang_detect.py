# -*- coding: utf-8 -*-
"""
コメントが「翻訳不要かどうか」を、LLMを使わずに
プログラム側で簡易判定するモジュール。

【判定ロジック】
以下のいずれかに当てはまれば「翻訳不要」と判定し、そのまま読み上げる:
  1. ひらがな・カタカナ・漢字を含む(=日本語コメント)
  2. 記号・数字・アルファベットの短い繰り返し
     (例: "www", "GG", "888", "lol" のような、ネットスラング的な短文)

上記に当てはまらない場合のみ「翻訳が必要」と判定し、LLMに回す。

このモジュール単体はLLMを一切呼び出さないため、非常に高速。
大多数の日本語コメントは、この時点でLLM推論を経由せず
即座に読み上げに回せる。

【使い方】
from lang_detect import needs_translation
if needs_translation("Hello there"):
    ...(翻訳処理へ)
else:
    ...(そのまま読み上げ)
"""

import re

# ひらがな・カタカナが含まれるかの判定パターン。
# 【重要】漢字(\u4E00-\u9FFF)は、中国語とほぼ同じUnicode範囲を
# 共有しているため、判定基準に含めない。漢字だけで「日本語」と
# 断定すると、中国語コメントを誤って「翻訳不要」にしてしまう。
# 日本語の文章にはほぼ必ずひらがなが混ざるため、ひらがな・カタカナの
# 有無だけで判定する方が、中国語との誤判定を避けられる。
JAPANESE_PATTERN = re.compile(
    r"[\u3040-\u309F"   # ひらがな
    r"\u30A0-\u30FF]"   # カタカナ
)

# 「翻訳せず、そのまま読んで問題ない」短い記号・スラング的な表現。
# 完全一致、または英数字記号のみで構成された短い文字列を対象にする。
SHORT_SLANG_PATTERN = re.compile(
    r"^[wWｗＷ]{2,}$"          # www, WWWW 等(笑いの表現)
    r"|^[a-zA-Z0-9!?！？.,、。\s]{1,6}$"  # GG, lol, 888, nice! のような短い文字列
)

# 漢字のみで構成された短いコメント。
# 【注意】この判定だけでは中国語の短文("謝謝"等)と区別できない。
# ただし、それらは多くの場合「翻訳しなくても意味が近く実害が小さい」
# 短さであるため、割り切って「そのまま読み上げてよい」側に含める。
# 長い中国語の文章は、この短さの条件に当てはまらないため、
# 引き続き正しく翻訳ルートに回る。
KANJI_ONLY_SHORT_PATTERN = re.compile(r"^[\u4E00-\u9FFF]{1,4}$")


def needs_translation(text: str) -> bool:
    """
    このテキストをLLMで翻訳する必要があるかどうかを判定する。

    True  : 翻訳が必要(LLMに回す)
    False : 翻訳不要(そのまま読み上げてよい)
    """
    text = text.strip()
    if not text:
        return False

    # 日本語の文字(ひらがな/カタカナ/漢字)を含むなら、翻訳不要
    if JAPANESE_PATTERN.search(text):
        return False

    # 短い記号・スラング的な表現も、翻訳不要
    if SHORT_SLANG_PATTERN.match(text):
        return False

    # 漢字のみの短いコメント(乙、草、大丈夫 等)も、翻訳不要
    if KANJI_ONLY_SHORT_PATTERN.match(text):
        return False

    # それ以外(ある程度の長さがあり、日本語の文字を含まない)は、
    # 外国語の文章である可能性が高いので、翻訳が必要と判定する
    return True


if __name__ == "__main__":
    # 簡単な動作確認
    test_cases = [
        ("こんにちは", False),
        ("www", False),
        ("GG", False),
        ("888", False),
        ("lol", False),
        ("Hello! nice stream today", True),
        ("Bonjour tout le monde", True),
        ("이 게임 재밌어 보이네요", True),
        ("这个操作太厉害了", True),
        ("OMG that was insane lol", True),
    ]

    for text, expected in test_cases:
        result = needs_translation(text)
        status = "OK" if result == expected else "NG"
        print(f"[{status}] needs_translation({text!r}) = {result} (期待値: {expected})")
