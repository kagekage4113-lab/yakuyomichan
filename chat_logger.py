# -*- coding: utf-8 -*-
"""
チャットのやり取りを、日付ごとのテキストファイルとして
自動保存するモジュール。

【保存先】
logs/2026-08-07.txt のように、日付ごとに1ファイル。
同じ日に何度もアプリを起動・終了しても、同じファイルに追記される。

【使い方】
from chat_logger import log_comment, get_log_dir
log_comment(platform="twitch", user="user_92",
            original="Hello!", translated="こんにちは")
"""

import datetime
import os

LOG_DIR = "logs"


def get_log_dir() -> str:
    """ログフォルダの絶対パスを返す(フォルダが無ければ作成する)"""
    os.makedirs(LOG_DIR, exist_ok=True)
    return os.path.abspath(LOG_DIR)


def _today_log_path() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    today = datetime.date.today().isoformat()
    return os.path.join(LOG_DIR, f"{today}.txt")


def log_comment(platform: str, user: str, original: str, translated: str):
    """
    1件のコメント処理結果を、本日分のログファイルに追記する。
    original が空文字(日本語コメントの場合)なら、その旨を分かりやすく記録する。
    """
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    original_part = original if original else "(日本語のためそのまま)"

    line = f"[{timestamp}] ({platform}) {user}: {original_part} → {translated}\n"

    path = _today_log_path()
    with open(path, "a", encoding="utf-8") as f:
        f.write(line)


def open_log_folder():
    """
    ログフォルダを、OS標準のファイルマネージャーで開く。
    Windows/Mac/Linuxそれぞれの開き方に対応する。
    """
    path = get_log_dir()

    try:
        if os.name == "nt":  # Windows
            os.startfile(path)
        elif os.uname().sysname == "Darwin":  # Mac
            os.system(f'open "{path}"')
        else:  # Linux
            os.system(f'xdg-open "{path}"')
    except Exception as e:
        print(f"[chat_logger] ログフォルダを開けませんでした: {e}")


if __name__ == "__main__":
    # 動作確認用
    log_comment("twitch", "test_user", "Hello!", "こんにちは")
    log_comment("youtube", "たろう", "", "今日のご飯なに食べたの?")
    print(f"ログを {_today_log_path()} に書き込みました。")
