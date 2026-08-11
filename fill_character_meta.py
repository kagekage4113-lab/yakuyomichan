# -*- coding: utf-8 -*-
"""
character_meta.json(キャラクター単位、speaker_uuidをキーにしたもの)に、
gender / genre_tags を一括で反映する。

【使い方】
1. 先に sync_voicevox_characters.py を実行して character_meta.json を作る
2. このスクリプトを同じフォルダで実行する
   python fill_character_meta.py
"""

import json

META_PATH = "character_meta.json"

# display_name をキーにした、性別とジャンルタグのデータ
# (実際に試聴しながら調整済みの内容)
CHARACTER_INFO = {
    "四国めたん":       {"gender": "女性", "genre_tags": ["上品系", "ツンデレ"]},
    "ずんだもん":       {"gender": "中性", "genre_tags": ["元気系", "幼い系"]},
    "春日部つむぎ":     {"gender": "女性", "genre_tags": ["元気系", "明るい"]},
    "波音リツ":         {"gender": "中性", "genre_tags": ["クール", "低音"]},
    "雨晴はう":         {"gender": "女性", "genre_tags": ["癒し系"]},
    "玄野武宏":         {"gender": "男性", "genre_tags": ["爽やか系"]},
    "白上虎太郎":       {"gender": "男性", "genre_tags": ["幼い系", "明るい"]},
    "青山龍星":         {"gender": "男性", "genre_tags": ["低音", "クール"]},
    "冥鳴ひまり":       {"gender": "女性", "genre_tags": ["癒し系", "幼い系"]},
    "九州そら":         {"gender": "女性", "genre_tags": ["お姉さん系", "上品系"]},
    "もち子さん":       {"gender": "女性", "genre_tags": ["癒し系"]},
    "剣崎雌雄":         {"gender": "男性", "genre_tags": ["渋め系", "癒し系"]},
    "WhiteCUL":         {"gender": "女性", "genre_tags": ["クール"]},
    "後鬼":             {"gender": "女性", "genre_tags": ["お姉さん系"]},
    "No.7":             {"gender": "女性", "genre_tags": ["クール", "上品系"]},
    "ちび式じい":       {"gender": "男性", "genre_tags": ["渋め系", "癒し系"]},
    "ナースロボ＿タイプＴ": {"gender": "女性", "genre_tags": ["幼い系", "クール"]},
    "櫻歌ミコ":         {"gender": "女性", "genre_tags": ["幼い系"]},
    "小夜/SAYO":        {"gender": "女性", "genre_tags": ["癒し系", "ハキハキ"]},
    "†聖騎士 紅桜†":     {"gender": "男性", "genre_tags": ["爽やか系", "ハキハキ"]},
    "雀松朱司":         {"gender": "男性", "genre_tags": ["爽やか系", "渋め系"]},
    "麒ヶ島宗麟":       {"gender": "男性", "genre_tags": ["渋め系", "低音"]},
    "春歌ナナ":         {"gender": "女性", "genre_tags": ["元気系", "幼い系"]},
    "猫使アル":         {"gender": "男性", "genre_tags": ["幼い系"]},
    "猫使ビィ":         {"gender": "女性", "genre_tags": ["幼い系", "明るい"]},
    "中国うさぎ":       {"gender": "女性", "genre_tags": ["幼い系", "上品系"]},
    "栗田まろん":       {"gender": "男性", "genre_tags": ["低音"]},
    "あいえるたん":     {"gender": "女性", "genre_tags": ["ハキハキ", "癒し系"]},
    "満別花丸":         {"gender": "中性", "genre_tags": ["幼い系"]},
    "琴詠ニア":         {"gender": "女性", "genre_tags": ["明るい", "上品系"]},
    "Voidoll":          {"gender": "女性", "genre_tags": ["ロボット系"]},
    "ぞん子":           {"gender": "女性", "genre_tags": ["ハキハキ", "元気系"]},
    "中部つるぎ":       {"gender": "女性", "genre_tags": ["クール"]},
    "離途":             {"gender": "男性", "genre_tags": ["渋め系", "低音"]},
    "黒沢冴白":         {"gender": "男性", "genre_tags": ["クール"]},
    "ユーレイちゃん":   {"gender": "女性", "genre_tags": ["癒し系"]},
    "東北ずん子":       {"gender": "女性", "genre_tags": ["癒し系"]},
    "東北きりたん":     {"gender": "女性", "genre_tags": ["元気系", "幼い系"]},
    "東北イタコ":       {"gender": "女性", "genre_tags": ["お姉さん系"]},
    "あんこもん":       {"gender": "女性", "genre_tags": ["上品系"]},
    "里石ユカ":         {"gender": "女性", "genre_tags": ["お姉さん系"]},
    "夜語トバリ":       {"gender": "女性", "genre_tags": ["お姉さん系"]},
    "暁記ミタマ":       {"gender": "女性", "genre_tags": ["クール", "低音"]},
}


def main():
    with open(META_PATH, "r", encoding="utf-8") as f:
        character_meta = json.load(f)

    updated = 0
    not_found = set()

    # キーが speaker_uuid になっているので、中の display_name を見て
    # CHARACTER_INFO と突き合わせる
    for speaker_uuid, entry in character_meta.items():
        name = entry["display_name"]
        info = CHARACTER_INFO.get(name)
        if info is None:
            not_found.add(name)
            continue
        entry["gender"] = info["gender"]
        entry["genre_tags"] = list(info["genre_tags"])
        updated += 1

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(character_meta, f, ensure_ascii=False, indent=2)

    print(f"更新したキャラクター数: {updated}")
    if not_found:
        print("\n情報が見つからず、未更新のままのキャラ:")
        for name in sorted(not_found):
            print(f"  - {name}")
        print("(これらは character_meta.json を開いて手動で埋めてください)")


if __name__ == "__main__":
    main()
