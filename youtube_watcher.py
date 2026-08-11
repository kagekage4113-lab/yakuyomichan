# -*- coding: utf-8 -*-
"""
YouTube Live Chatを監視し、コメントが来るたびに
判定→(必要なら翻訳)→読み上げのパイプラインに流すモジュール。

【Twitchとの違い】
Twitchはイベントがリアルタイムでプッシュされてくる方式だが、
YouTube Data APIには同様の仕組みが無いため、
「一定間隔でこちらから取得しにいく(ポーリング)」方式になる。
そのため、コメントの反映にはTwitchよりわずかに遅延が出る
(pollingIntervalMillisで指定された間隔、通常数秒程度)。

【前提】
token_config.json に以下が設定されていること:
{
  "youtube": {
    "api_key": "AIzaSy...",
    "video_id": "配信のVIDEO_ID"
  }
}

【使い方】
python youtube_watcher.py (単体動作確認用)
"""

import json
import os
import time

import requests

TOKEN_CONFIG_PATH = "token_config.json"
API_BASE = "https://www.googleapis.com/youtube/v3"

_stop_flag = {"stop": False}


def load_youtube_config():
    if not os.path.exists(TOKEN_CONFIG_PATH):
        return None
    with open(TOKEN_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    yt_conf = data.get("youtube", {})
    if not yt_conf.get("api_key") or not yt_conf.get("video_id"):
        return None
    return yt_conf


def _get_live_chat_id(api_key: str, video_id: str) -> str:
    """VIDEO_IDから、そのライブ配信のliveChatIdを取得する"""
    resp = requests.get(
        f"{API_BASE}/videos",
        params={
            "part": "liveStreamingDetails",
            "id": video_id,
            "key": api_key,
        },
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()

    items = data.get("items", [])
    if not items:
        raise RuntimeError(
            "配信情報が見つかりませんでした。VIDEO_IDが正しいか、"
            "配信が実際に開始されているか確認してください。"
        )

    details = items[0].get("liveStreamingDetails", {})
    live_chat_id = details.get("activeLiveChatId")
    if not live_chat_id:
        raise RuntimeError(
            "ライブチャットIDが取得できませんでした。"
            "配信がまだ開始されていない、またはチャットが無効になっている可能性があります。"
        )
    return live_chat_id


def _poll_messages(api_key: str, live_chat_id: str, on_comment, page_token=None):
    """1回分のポーリングを行い、新しいメッセージがあればon_commentを呼ぶ"""
    params = {
        "liveChatId": live_chat_id,
        "part": "snippet,authorDetails",
        "key": api_key,
    }
    if page_token:
        params["pageToken"] = page_token

    resp = requests.get(f"{API_BASE}/liveChat/messages", params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    for item in data.get("items", []):
        username = item["authorDetails"]["displayName"]
        message = item["snippet"].get("displayMessage", "")
        if message and on_comment:
            on_comment(username, message)

    next_page_token = data.get("nextPageToken")
    polling_interval = data.get("pollingIntervalMillis", 5000) / 1000.0
    return next_page_token, polling_interval


def start_watching(on_comment):
    """
    設定ファイルの情報を使って、YouTube Live Chatの監視を開始する。
    on_comment(username, message) が、コメントを受け取るたびに呼ばれる。
    ブロッキングするので、呼び出し元は別スレッドで実行すること。

    戻り値: 起動できたかどうか(bool)。
    """
    config = load_youtube_config()
    if config is None:
        print("[YoutubeWatcher] APIキーまたはVIDEO_IDが設定されていません。配信メニューから設定してください。")
        return False

    api_key = config["api_key"]
    video_id = config["video_id"]

    try:
        live_chat_id = _get_live_chat_id(api_key, video_id)
    except Exception as e:
        print(f"[YoutubeWatcher] ライブチャットの取得に失敗しました: {e}")
        return False

    print("[YoutubeWatcher] 接続しました。ポーリングを開始します。")
    page_token = None
    _stop_flag["stop"] = False

    # 【重要】YouTube Data APIは、pageTokenを指定しない最初の
    # リクエストで「配信開始からこれまでの全チャット履歴」を
    # 返してくる。これをそのまま読み上げると、起動した瞬間に
    # 過去ログが一気に読み上げられてしまうため、最初の1回だけは
    # on_commentを呼ばず、ページトークンの取得だけを行う。
    try:
        page_token, interval = _poll_messages(api_key, live_chat_id, on_comment=None, page_token=page_token)
    except Exception as e:
        print(f"[YoutubeWatcher] 初回のメッセージ取得中にエラーが発生しました: {e}")
        interval = 5.0

    while not _stop_flag["stop"]:
        time.sleep(interval)
        try:
            page_token, interval = _poll_messages(api_key, live_chat_id, on_comment, page_token)
        except Exception as e:
            print(f"[YoutubeWatcher] メッセージ取得中にエラーが発生しました: {e}")
            interval = 5.0  # エラー時は少し待ってからリトライする

    return True


def stop_watching():
    """監視ループを止める(次のポーリング間隔のタイミングで停止する)"""
    _stop_flag["stop"] = True


if __name__ == "__main__":
    def print_comment(username, message):
        print(f"[{username}] {message}")

    start_watching(print_comment)
