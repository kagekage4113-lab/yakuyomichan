# -*- coding: utf-8 -*-
"""
VOICEVOXの読み間違い補正辞書。

VOICEVOXが読み間違えやすい語(配信・ゲーム・ネットスラングや、
全部大文字の英字略語など)を、VOICEVOXのユーザー辞書へ登録する。

【設計】
・辞書データはこのファイルに直接持たせている。データファイルを別に
  同梱すると、PyInstallerやインストーラーの設定にも手を入れる必要が
  あるため、Pythonのコードの一部にして、配布を簡単にしている。
・登録先はVOICEVOX自身のユーザー辞書。VOICEVOXを使う他のアプリにも
  効くため、自動では登録せず、メニューから利用者が実行する
  (取り消しも同じメニューから行える)。
・既に同じ表記が登録されている場合は上書きしない
  (利用者が自分で登録した読みを壊さないため)。
・取り消しは、「表記」と「読み」の両方が、ここの辞書と一致する
  登録だけを削除する(利用者が自分で登録した別の読みは残る)。

辞書データの追加・修正は ENTRIES に行を足すだけでよい。
DICTIONARY_VERSION は、内容を変えたときに上げておく。
"""

import unicodedata

import requests

DICTIONARY_VERSION = 1

# (表記, 読み(カタカナ), アクセント型)
# アクセント型: 0=平板、N=N拍目の後で音が下がる。
ENTRIES = [
    # ---- 配信・ネットスラング ----
    ("激重", "ゲキオモ", 0),
    ("激熱", "ゲキアツ", 0),
    ("爆速", "バクソク", 0),
    ("爆勝ち", "バクガチ", 0),
    ("同接", "ドウセツ", 0),
    ("待機所", "タイキジョ", 0),
    ("尊死", "トウトシ", 0),
    ("垢BAN", "アカバン", 0),
    ("陰キャ", "インキャ", 0),
    ("陽キャ", "ヨウキャ", 0),
    ("微課金", "ビカキン", 0),
    ("有り難う", "アリガトウ", 0),
    ("度々", "タビタビ", 0),
    # ---- 英字略語・ゲーム用語 ----
    ("BAN", "バン", 0),
    ("LAG", "ラグ", 0),
    ("KILL", "キル", 0),
    ("EZ", "イージー", 0),
    ("GGEZ", "ジージーイージー", 0),
    ("RAM", "ラム", 0),
    ("PW", "パスワード", 0),
    ("Vtuber", "ブイチューバー", 0),
    ("Steam", "スチーム", 0),
    ("PS5", "ピーエスファイブ", 0),
    ("MOBA", "モバ", 0),
    ("PvP", "ピーブイピー", 0),
    ("PvE", "ピーブイイー", 0),
    ("MOD", "モッド", 0),
    ("TAS", "タス", 0),
    ("GOTY", "ゴーティー", 0),
    ("APEX", "エーペックス", 0),
    ("Apex", "エーペックス", 0),
    ("MAD", "マッド", 0),
    ("Live2D", "ライブツーディー", 0),
    ("2D", "ツーディー", 0),
    # ---- 全部大文字だと1文字ずつ読まれてしまう英単語 ----
    ("NICE", "ナイス", 0),
    ("LOSE", "ルーズ", 0),
    ("MISS", "ミス", 0),
    ("BEST", "ベスト", 0),
    ("HELLO", "ハロー", 0),
    ("WOW", "ワオ", 0),
    ("CUTE", "キュート", 0),
    # ---- 英単語(小文字)の読み崩れ ----
    ("thx", "サンクス", 0),
    ("hello", "ハロー", 0),
    ("great", "グレート", 0),
    ("Sorry", "ソーリー", 0),
]

# 「hi」「no」のような非常に短い英単語は、他の語の読みに副作用が出る
# 可能性があるため、検証が済むまでは意図的にここへ含めていない。


def _norm(s):
    return unicodedata.normalize("NFKC", s or "")


def is_engine_up(base_url="http://127.0.0.1:50021", timeout=2):
    """VOICEVOXエンジンに接続できるか(起動しているか)を返す"""
    try:
        requests.get(f"{base_url}/version", timeout=timeout).raise_for_status()
        return True
    except requests.RequestException:
        return False


def _get_user_dict(base_url):
    resp = requests.get(f"{base_url}/user_dict", timeout=10)
    resp.raise_for_status()
    return resp.json()


def apply_dictionary(base_url="http://127.0.0.1:50021"):
    """
    ENTRIESをVOICEVOXのユーザー辞書へ登録する。

    戻り値: {"added": 登録した数, "skipped": 登録済みのため飛ばした数,
             "failed": 失敗した数}
    VOICEVOXに接続できない場合は例外(requests.RequestException)を投げる
    (呼び出し側で、利用者向けのメッセージを出す)。
    """
    existing = {_norm(v.get("surface", "")) for v in _get_user_dict(base_url).values()}

    added = skipped = failed = 0
    for surface, yomi, accent in ENTRIES:
        if _norm(surface) in existing:
            skipped += 1
            continue
        try:
            r = requests.post(
                f"{base_url}/user_dict_word",
                params={
                    "surface": surface,
                    "pronunciation": yomi,
                    "accent_type": accent,
                    "word_type": "COMMON_NOUN",
                    "priority": 7,
                },
                timeout=10,
            )
            r.raise_for_status()
            added += 1
        except requests.RequestException as e:
            print(f"[reading_dictionary] 登録に失敗しました: {surface} ({e})")
            failed += 1
    return {"added": added, "skipped": skipped, "failed": failed}


def remove_dictionary(base_url="http://127.0.0.1:50021"):
    """
    ENTRIESと「表記」「読み」が両方一致する登録だけを削除する。

    戻り値: {"removed": 削除した数, "failed": 失敗した数}
    """
    wanted = {(_norm(s), y) for s, y, _ in ENTRIES}

    removed = failed = 0
    for uuid, v in _get_user_dict(base_url).items():
        key = (_norm(v.get("surface", "")), v.get("pronunciation", ""))
        if key not in wanted:
            continue
        try:
            r = requests.delete(f"{base_url}/user_dict_word/{uuid}", timeout=10)
            r.raise_for_status()
            removed += 1
        except requests.RequestException as e:
            print(f"[reading_dictionary] 削除に失敗しました: {key[0]} ({e})")
            failed += 1
    return {"removed": removed, "failed": failed}
