# -*- coding: utf-8 -*-
"""
アプリ全体に関わる、軽量な設定値をまとめて管理するモジュール。

main_window.py と auto_launch_settings_window.py の両方から
参照されるため、circular import を避ける目的で独立したファイルに
分離している。

【保存先】
app_settings.json (exeがあるフォルダ。writable_path()経由)

【使い方】
from app_settings import load_app_settings, save_app_settings
settings = load_app_settings()
settings["max_chat_log_rows"] = 200
save_app_settings(settings)
"""

import json
import os

from resource_path import writable_path

APP_SETTINGS_PATH = "app_settings.json"

DEFAULT_APP_SETTINGS = {
    "max_chat_log_rows": 100,  # チャットログ欄に保持する最大行数
    "translation_enabled": True,  # LLM翻訳機能を使うかどうか(OFFならVOICEVOXの読み上げ専用ツールとして動く)
    "tutorial_shown": False,  # 初回起動チュートリアルを、既に見せたかどうか
}


def load_app_settings() -> dict:
    """
    【重要】以前は相対パス("app_settings.json")のまま open() していたため、
    PyInstallerでビルドしたexeを、書き込み権限が制限された場所
    (Program Files配下等)にインストールした場合、正しい場所を
    読み書きできず、設定(チュートリアル既読フラグ等)が保存されない
    不具合があった。writable_path() を使い、常に「exeがあるフォルダ」
    を基準にすることで解消している。
    """
    path = writable_path(APP_SETTINGS_PATH)
    if not os.path.exists(path):
        return dict(DEFAULT_APP_SETTINGS)
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        settings = dict(DEFAULT_APP_SETTINGS)
        settings.update(saved)
        return settings
    except Exception:
        return dict(DEFAULT_APP_SETTINGS)


def save_app_settings(settings: dict):
    with open(writable_path(APP_SETTINGS_PATH), "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
