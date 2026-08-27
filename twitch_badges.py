# -*- coding: utf-8 -*-
"""
TwitchのHelix APIを使って、バッジ(サブスク・モデレーター等の
実績アイコン)の画像URLを取得するモジュール。

【重要・Client-IDについて】
このAPIを呼ぶには、OAuthトークンに加えて、
「そのトークンを発行したのと同じアプリ登録のClient-ID」が必要。
twitchtokengenerator.com等でトークンだけ取得した場合、
別途(自分で)取得したClient-IDとは組み合わせが合わず、
認証エラーになることがある。
その場合でも、バッジ表示の機能だけが静かに諦められるように
なっており、アプリの他の機能(翻訳・読み上げ等)には
一切影響しない設計にしている。

【使い方】
from twitch_badges import load_badge_map
badge_map = load_badge_map(channel, oauth_token, client_id)
# badge_map: {(set_id, version): image_url, ...}
"""

import requests

_badge_cache = {}  # (channel, oauth_token, client_id) -> {(set_id, version): image_url}

API_BASE = "https://api.twitch.tv/helix"


def _headers(oauth_token, client_id):
    token = oauth_token[6:] if oauth_token.startswith("oauth:") else oauth_token
    return {
        "Authorization": f"Bearer {token}",
        "Client-Id": client_id,
    }


def _get_broadcaster_id(channel, oauth_token, client_id):
    resp = requests.get(
        f"{API_BASE}/users",
        headers=_headers(oauth_token, client_id),
        params={"login": channel},
        timeout=10,
    )
    resp.raise_for_status()
    data = resp.json().get("data", [])
    if not data:
        return None
    return data[0]["id"]


def _fetch_badge_set(url, oauth_token, client_id, params=None):
    resp = requests.get(url, headers=_headers(oauth_token, client_id), params=params, timeout=10)
    resp.raise_for_status()
    result = {}
    for badge_set in resp.json().get("data", []):
        set_id = badge_set.get("set_id")
        for version in badge_set.get("versions", []):
            image_url = version.get("image_url_2x") or version.get("image_url_1x")
            if set_id and image_url:
                result[(set_id, version.get("id"))] = image_url
    return result


def load_badge_map(channel, oauth_token, client_id):
    """
    グローバルバッジ + チャンネル固有バッジを取得し、
    {(set_id, version): image_url} の辞書として返す。

    取得に失敗した場合(Client-IDとトークンの組み合わせが違う、
    ネットワークエラー、channelが見つからない等)は、
    可能な範囲の結果(場合によっては空の辞書)を返す。
    例外は投げない(呼び出し元でtry/exceptを書かせない、
    「バッジが表示されないだけ」に留める設計)。

    同じ組み合わせに対しては、プロセス内でキャッシュして
    再利用する(Twitch接続のたびに毎回APIを叩き直さないため)。
    """
    cache_key = (channel, oauth_token, client_id)
    if cache_key in _badge_cache:
        return _badge_cache[cache_key]

    if not oauth_token or not client_id:
        # Client-IDが未設定の場合は、そもそも呼び出さない
        # (通常利用ではバッジ機能を使わないユーザーが大半のため、
        # 無駄なAPI呼び出し・エラーログを出さないようにする)
        _badge_cache[cache_key] = {}
        return {}

    badge_map = {}

    try:
        badge_map.update(_fetch_badge_set(
            f"{API_BASE}/chat/badges/global", oauth_token, client_id,
        ))
    except Exception as e:
        print(f"[twitch_badges] グローバルバッジの取得に失敗しました: {e}")
        print("[twitch_badges] Client-IDとOAuthトークンが同じアプリ登録から"
              "発行されたものか確認してください。")

    try:
        broadcaster_id = _get_broadcaster_id(channel, oauth_token, client_id)
        if broadcaster_id:
            badge_map.update(_fetch_badge_set(
                f"{API_BASE}/chat/badges", oauth_token, client_id,
                params={"broadcaster_id": broadcaster_id},
            ))
    except Exception as e:
        print(f"[twitch_badges] チャンネルバッジの取得に失敗しました: {e}")

    _badge_cache[cache_key] = badge_map
    return badge_map


def clear_cache():
    """トークン設定を変更した後などに、キャッシュを破棄したい場合に呼ぶ"""
    _badge_cache.clear()
