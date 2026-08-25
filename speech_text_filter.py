# -*- coding: utf-8 -*-
"""
読み上げ「前」のテキストを加工するためのフィルター処理。

【対象】
- URL(http://, https://, www. から始まるもの)
- 絵文字(Unicodeの絵文字ブロック)
- 顔文字(かっこの中に記号が並ぶタイプの、いわゆる「(^_^)」系)

【重要】ここでの加工は、あくまで「読み上げに渡す直前のテキスト」だけに
適用する。チャット欄・オーバーレイの表示や、翻訳処理そのものには
一切影響しない(ユーザーが実際に読んだコメントの内容は、画面上は
そのまま全文が見える)。

【使い方】
from speech_text_filter import prepare_text_for_speech
speech_text = prepare_text_for_speech(
    translated_text,
    filter_urls=True,
    filter_emoji=True,
    max_chars=200,
)
"""

import re

# http(s)://... および www.... 形式のURLにマッチ
URL_PATTERN = re.compile(r"(?:https?://|www\.)\S+", re.IGNORECASE)

# Unicodeの主な絵文字ブロックにマッチ(顔・記号・乗り物・国旗等、代表的な範囲)
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F300-\U0001FAFF"  # 各種絵文字(顔、動物、食べ物、乗り物 等)
    "\U00002600-\U000026FF"  # その他の記号(☀,☂ 等)
    "\U00002700-\U000027BF"  # 装飾記号(✂,✈ 等)
    "\U0001F1E6-\U0001F1FF"  # 国旗用の地域表示文字
    "\U00002B00-\U00002BFF"  # 矢印・記号の一部
    "\U0000FE0F"              # 異体字セレクタ(絵文字表示指定)
    "]+",
    flags=re.UNICODE,
)

# 「(^_^)」「(´・ω・`)」のような、かっこの中身がほぼ記号・かな・カナだけの
# 顔文字を検出する。日本語の通常の文章(漢字・英数字)がかっこ内に
# 含まれる場合は誤って消さないよう、漢字・英数字を含む場合は対象外にする。
KAOMOJI_PATTERN = re.compile(
    r"[\(（][^\)）]{1,20}[\)）]"
)
KAOMOJI_EXCLUDE_PATTERN = re.compile(
    r"[a-zA-Z0-9\u4E00-\u9FFF]"  # 半角英数字・漢字を含む場合は顔文字とみなさない
)

TRUNCATION_SUFFIX = "(以下略)"  # 文字数上限で切り詰めた際に付け足す接尾辞


def _is_kaomoji_like(inner_text: str) -> bool:
    """かっこの中身が、漢字・英数字を含まない(=顔文字らしい)かどうかを判定する"""
    if not inner_text.strip():
        return False
    return not KAOMOJI_EXCLUDE_PATTERN.search(inner_text)


def _strip_kaomoji(text: str) -> str:
    def _replace(match: "re.Match[str]") -> str:
        full = match.group(0)
        inner = full[1:-1]
        return "" if _is_kaomoji_like(inner) else full

    return KAOMOJI_PATTERN.sub(_replace, text)


def prepare_text_for_speech(text: str, filter_urls: bool = True,
                             filter_emoji: bool = True, max_chars: int = 0) -> str:
    """
    読み上げ直前のテキストを加工して返す。

    text: 読み上げ対象の文字列(翻訳後のテキストを想定)
    filter_urls: TrueならURLを読み上げから除外する
    filter_emoji: Trueなら絵文字・顔文字を読み上げから除外する
    max_chars: 読み上げる文字数の上限。0以下なら無制限。
               上限を超えた場合は、その時点で切り詰める(末尾は省略される)。
    """
    if not text:
        return text

    result = text

    if filter_urls:
        result = URL_PATTERN.sub("", result)

    if filter_emoji:
        result = EMOJI_PATTERN.sub("", result)
        result = _strip_kaomoji(result)

    # フィルターで文字を削った結果、余分な空白が連続することがあるため整える
    result = re.sub(r"[ \u3000]{2,}", " ", result).strip()

    if max_chars and max_chars > 0 and len(result) > max_chars:
        result = result[:max_chars] + TRUNCATION_SUFFIX

    return result
