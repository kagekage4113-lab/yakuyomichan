# -*- coding: utf-8 -*-
"""
VOICEVOX / LM Studio を、このアプリの起動と同時に
自動で立ち上げるための管理モジュール。

「オールインワン」を目指すための機能。既に起動済みであれば
二重起動せず、未起動の場合だけ実行ファイルを起動する。

【設定の保存先】
auto_launch_config.json
{
  "voicevox": {"enabled": true, "exe_path": "C:\\...\\VOICEVOX.exe"},
  "lm_studio": {"enabled": true, "exe_path": "C:\\...\\LM Studio.exe"}
}

【使い方】
from auto_launch import auto_launch_all
auto_launch_all()   # main_window.py の起動時に呼ぶ想定
"""

import json
import os
import subprocess
import time

import requests

CONFIG_PATH = "auto_launch_config.json"

VOICEVOX_CHECK_URL = "http://127.0.0.1:50021/version"
LM_STUDIO_CHECK_URL = "http://127.0.0.1:1234/v1/models"


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return {
            "voicevox": {"enabled": False, "exe_path": ""},
            "lm_studio": {"enabled": False, "exe_path": ""},
            "unload_llm_on_exit": False,
        }
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = json.load(f)
        config.setdefault("unload_llm_on_exit", False)
        return config
    except Exception:
        return {
            "voicevox": {"enabled": False, "exe_path": ""},
            "lm_studio": {"enabled": False, "exe_path": ""},
            "unload_llm_on_exit": False,
        }


def save_config(config: dict):
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def _is_running(check_url: str, timeout: float = 1.5) -> bool:
    """指定URLに接続できれば、そのアプリは既に起動していると判断する"""
    try:
        requests.get(check_url, timeout=timeout)
        return True
    except Exception:
        return False


def _launch_exe(exe_path: str) -> bool:
    if not exe_path or not os.path.exists(exe_path):
        return False
    try:
        subprocess.Popen([exe_path], shell=False)
        return True
    except Exception as e:
        print(f"[auto_launch] 起動に失敗しました({exe_path}): {e}")
        return False


def auto_launch_voicevox(log_func=print) -> str:
    """
    VOICEVOXを自動起動する。
    戻り値は状態を表す文字列("already_running" / "launched" / "disabled" / "no_path" / "failed")
    """
    config = load_config()
    vv_config = config.get("voicevox", {})

    if not vv_config.get("enabled"):
        return "disabled"

    if _is_running(VOICEVOX_CHECK_URL):
        log_func("VOICEVOXは既に起動しています。")
        return "already_running"

    exe_path = vv_config.get("exe_path", "")
    if not exe_path:
        log_func("VOICEVOXの実行ファイルパスが設定されていません。")
        return "no_path"

    if _launch_exe(exe_path):
        log_func("VOICEVOXを起動しました。エンジンの立ち上がりを待っています...")
        return "launched"
    return "failed"


def auto_launch_lm_studio(log_func=print) -> str:
    """
    LM Studioを自動起動する。
    【注意】LM Studioは起動しただけではAPIサーバーが自動で立ち上がらない
    場合がある(モデルのロード・Local Serverの手動起動が必要なことがある)。
    このため、ここでは「アプリの起動」までを行い、サーバーの立ち上げは
    ユーザー自身の操作、またはLM Studio側の自動起動設定に委ねる。
    """
    config = load_config()
    lm_config = config.get("lm_studio", {})

    if not lm_config.get("enabled"):
        return "disabled"

    if _is_running(LM_STUDIO_CHECK_URL):
        log_func("LM Studioのサーバーは既に起動しています。")
        return "already_running"

    exe_path = lm_config.get("exe_path", "")
    if not exe_path:
        log_func("LM Studioの実行ファイルパスが設定されていません。")
        return "no_path"

    if _launch_exe(exe_path):
        log_func(
            "LM Studioを起動しました。モデルのロードとサーバー起動は、"
            "LM Studio側で手動または自動起動設定を行ってください。"
        )
        return "launched"
    return "failed"


def auto_launch_all(log_func=print):
    """アプリ起動時に、有効化されているものだけまとめて自動起動する"""
    auto_launch_voicevox(log_func=log_func)
    auto_launch_lm_studio(log_func=log_func)


if __name__ == "__main__":
    auto_launch_all()
