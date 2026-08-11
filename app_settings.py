# -*- coding: utf-8 -*-
"""
アプリ全体に関わる、軽量な設定値をまとめて管理するモジュール。

main_window.py と auto_launch_settings_window.py の両方から
参照されるため、circular import を避ける目的で独立したファイルに
分離している。

【保存先】
app_settings.json

【使い方】
from app_settings import load_app_settings, save_app_settings
settings = load_app_settings()
settings["max_chat_log_rows"] = 200
save_app_settings(settings)
"""

import json
import os

APP_SETTINGS_PATH = "app_settings.json"

DEFAULT_APP_SETTINGS = {
    "max_chat_log_rows": 100,  # チャットログ欄に保持する最大行数
    "translation_enabled": True,  # LLM翻訳機能を使うかどうか(OFFならVOICEVOXの読み上げ専用ツールとして動く)
    "tutorial_shown": False,  # 初回起動チュートリアルを、既に見せたかどうか
}


def load_app_settings() -> dict:
    if not os.path.exists(APP_SETTINGS_PATH):
        return dict(DEFAULT_APP_SETTINGS)
    try:
        with open(APP_SETTINGS_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        settings = dict(DEFAULT_APP_SETTINGS)
        settings.update(saved)
        return settings
    except Exception:
        return dict(DEFAULT_APP_SETTINGS)


def save_app_settings(settings: dict):
    with open(APP_SETTINGS_PATH, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=2)
