# -*- coding: utf-8 -*-
"""
チャットのやり取りを、日付ごとのテキストファイルとして
自動保存するモジュール。

【保存先】
logs/2026-08-07.txt のように、日付ごとに1ファイル。
同じ日に何度もアプリを起動・終了しても、同じファイルに追記される。
(exeがあるフォルダを基準にする。writable_path()経由)

【使い方】
from chat_logger import log_comment, get_log_dir
log_comment(platform="twitch", user="user_92",
            original="Hello!", translated="こんにちは")
"""

import datetime
import os

from resource_path import writable_path

LOG_DIR = "logs"


def _log_dir_path() -> str:
    """
    【重要】以前は相対パス("logs")のまま os.makedirs / パス組み立てを
    行っていたため、PyInstallerでビルドしたexeを、書き込み権限が
    制限された場所(Program Files配下等)にインストールした場合、
    正しい場所にログフォルダを作成できない(あるいは作成に失敗して
    ログ保存自体が機能しない)不具合があった。
    writable_path() 経由で、常に「exeがあるフォルダ」を基準にする
    ことで解消している。
    """
    return writable_path(LOG_DIR)


def get_log_dir() -> str:
    """ログフォルダの絶対パスを返す(フォルダが無ければ作成する)"""
    path = _log_dir_path()
    os.makedirs(path, exist_ok=True)
    return os.path.abspath(path)


def _today_log_path() -> str:
    log_dir = _log_dir_path()
    os.makedirs(log_dir, exist_ok=True)
    today = datetime.date.today().isoformat()
    return os.path.join(log_dir, f"{today}.txt")


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
