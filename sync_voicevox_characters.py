# -*- coding: utf-8 -*-
"""
VOICEVOXが起動している状態で一度だけ実行すると、
「キャラクター(親)→スタイル一覧(子)」という親子構造で、
選択用のデータを作る。

【今回の構造】
検索/絞り込みは、まずキャラクター単位(43体)で行う。
性別・ジャンルタグは、キャラクター1体につき1セットだけ持つ。
その後、1人のキャラを選んだ時にだけ、そのキャラが持つ
スタイル一覧(ノーマル/あまあま/ツンツン/ささやき等)が
サブ選択として表示される、という2段階の設計にするため。

こうすることで、「上品系×ツンデレ」のように絞り込んだ結果に、
同じキャラのスタイル違いが何件も並んでしまう(ごちゃつく)ことを防ぐ。

【前提】
VOICEVOXアプリ(エンジン)が起動していて、
http://127.0.0.1:50021 でAPIが待ち受けていること。

【使い方】
python sync_voicevox_characters.py

【出力】
- character_meta.json   : キャラクター単位(43件)の一覧
                           (display_name, gender, genre_tags(空欄),
                            icon_file, styles[サブ選択用の一覧])
- character_icons/       : 各キャラクターのアイコン画像(png)
"""

import base64
import json
import os

import requests

VOICEVOX_URL = "http://127.0.0.1:50021"
ICON_DIR = "character_icons"
META_PATH = "character_meta.json"


def save_icon(speaker_uuid):
    """そのキャラクターの代表アイコンを取得して保存する"""
    filename = f"{speaker_uuid}.png"
    path = os.path.join(ICON_DIR, filename)

    if os.path.exists(path):
        return filename

    resp = requests.get(
        f"{VOICEVOX_URL}/speaker_info",
        params={"speaker_uuid": speaker_uuid},
        timeout=30,
    )
    resp.raise_for_status()
    info = resp.json()

    icon_b64 = info["style_infos"][0]["icon"]
    icon_bytes = base64.b64decode(icon_b64)

    with open(path, "wb") as f:
        f.write(icon_bytes)

    return filename


def main():
    os.makedirs(ICON_DIR, exist_ok=True)

    print("VOICEVOXからキャラクター一覧を取得中...")
    resp = requests.get(f"{VOICEVOX_URL}/speakers", timeout=10)
    resp.raise_for_status()
    speakers = resp.json()
    print(f"合計 {len(speakers)} 体のキャラクターが見つかりました。")

    character_meta = {}
    total_styles = 0

    for i, sp in enumerate(speakers):
        display_name = sp["name"]
        speaker_uuid = sp["speaker_uuid"]

        print(f"[{i + 1}/{len(speakers)}] {display_name} のアイコンを取得中...")
        try:
            icon_filename = save_icon(speaker_uuid)
        except Exception as e:
            print(f"  警告: {display_name} のアイコン取得に失敗しました: {e}")
            icon_filename = None

        # このキャラが持つスタイル一覧を「サブ選択用のリスト」として、
        # キャラクター本体の中に子要素として持たせる
        styles = []
        for style in sp["styles"]:
            styles.append({
                "style_id": style["id"],
                "style_name": style["name"],
            })
            total_styles += 1

        character_meta[speaker_uuid] = {
            "display_name": display_name,
            "icon_file": icon_filename,
            "gender": "",       # 後で "男性" / "女性" / "中性" を埋める(キャラ単位で1つ)
            "genre_tags": [],   # 後で ["元気系","癒し系"] 等を埋める(キャラ単位で1つ)
            "is_favorite": False,
            "styles": styles,   # サブ選択用。ここから「ノーマル/あまあま/ささやき」等を選ぶ
        }

    with open(META_PATH, "w", encoding="utf-8") as f:
        json.dump(character_meta, f, ensure_ascii=False, indent=2)

    print("\n=== 完了 ===")
    print(f"キャラクター数: {len(speakers)} / 全スタイル数(参考): {total_styles}")
    print(f"キャラクター情報: {META_PATH}")
    print(f"アイコン画像フォルダ: {ICON_DIR}/")
    print("gender / genre_tags が空欄のままなので、fill_character_meta.py で埋めてください。")


if __name__ == "__main__":
    main()
