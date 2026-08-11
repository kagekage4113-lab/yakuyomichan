# -*- coding: utf-8 -*-
"""
Twitchのチャットを監視し、コメントが来るたびに
判定→(必要なら翻訳)→読み上げのパイプラインに流すモジュール。

【前提】
pip install twitchio

Twitchの以下の情報が必要:
- OAuthトークン(https://twitchtokengenerator.com 等で取得。
  "chat:read" 権限があればよい)
- 監視したいチャンネル名

これらは token_config.json に保存する想定
(トークンをコード直書きしないため。GUIのトークン設定画面から
書き込む形にする)。

【使い方】
python twitch_watcher.py
(単体では動作確認用。実際はGUIのメイン画面から起動/停止される)
"""

import json
import os

try:
    import twitchio
    TWITCHIO_AVAILABLE = True
except ImportError:
    TWITCHIO_AVAILABLE = False

TOKEN_CONFIG_PATH = "token_config.json"

_running_bots = []  # 停止処理のために、起動中のBotインスタンスを覚えておく
_is_stopped = {"value": False}  # bot.close()が効かない場合の保険用フラグ


def load_token_config():
    """
    token_config.json からTwitchの接続情報を読み込む。
    無い場合はNoneを返す(GUI側でトークン未設定の案内を出す想定)。
    """
    if not os.path.exists(TOKEN_CONFIG_PATH):
        return None
    with open(TOKEN_CONFIG_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    twitch_conf = data.get("twitch", {})
    if not twitch_conf.get("oauth_token") or not twitch_conf.get("channel"):
        return None
    return twitch_conf


class TwitchWatcher(twitchio.Client if TWITCHIO_AVAILABLE else object):
    """
    Twitchチャットを監視するClient。

    【重要】以前は twitchio.ext.commands.Bot を継承していたが、
    commands.Bot はコマンド解析の仕組みを内部に持っており、
    それが原因で同じメッセージが2回処理される不具合が発生した。
    今回はコマンド機能(!から始まる命令)を使わないため、
    より単純な twitchio.Client を直接継承する形に変更している。

    on_comment: コメントを受け取るたびに呼ばれるコールバック。
      on_comment(username: str, message: str) の形で呼ばれる。
    """

    def __init__(self, oauth_token, channel, on_comment):
        if not TWITCHIO_AVAILABLE:
            raise RuntimeError(
                "twitchioがインストールされていません。"
                "pip install twitchio を実行してください。"
            )
        super().__init__(token=oauth_token, initial_channels=[channel])
        self.on_comment = on_comment

    async def event_ready(self):
        print(f"[TwitchWatcher] 接続しました: {self.nick}")

    async def event_message(self, message):
        # Bot自身の発言は無視する(無限ループ防止)
        if message.echo:
            return

        # 【重要】twitchio.Clientのclose()が呼ばれても、環境によっては
        # 内部のWebSocket接続がすぐには切断されず、その間に来た
        # コメントでevent_messageが引き続き発火してしまうことがある。
        # 「停止」ボタンを押した後もコメントが拾われ続けるバグは
        # これが原因だったため、明示的な停止フラグでも二重にガードする。
        if _is_stopped["value"]:
            return

        username = message.author.name if message.author else "不明"
        content = message.content

        if self.on_comment:
            self.on_comment(username, content)


def start_watching(on_comment):
    """
    設定ファイルの情報を使って、Twitch監視を開始する。
    on_comment(username, message) が、コメントを受け取るたびに呼ばれる。

    戻り値: 起動できたかどうか(bool)。
      設定が無い・twitchioが無い場合はFalseを返す。
    """
    config = load_token_config()
    if config is None:
        print("[TwitchWatcher] トークンが設定されていません。配信メニューから設定してください。")
        return False

    if not TWITCHIO_AVAILABLE:
        print("[TwitchWatcher] twitchioがインストールされていません。")
        return False

    _is_stopped["value"] = False  # 新たに起動するので、停止フラグを解除しておく

    bot = TwitchWatcher(
        oauth_token=config["oauth_token"],
        channel=config["channel"],
        on_comment=on_comment,
    )
    _running_bots.append(bot)
    bot.run()  # ブロッキングするので、呼び出し元は別スレッドで実行すること
    return True


def stop_watching():
    """
    現在起動している全てのTwitch監視を停止する。
    twitchio.Clientはコルーチンベースなので、bot自身のイベントループに
    close()の実行を安全に依頼する形で停止する。

    【重要】close()自体が環境によっては即座に効かないことがあるため、
    _is_stopped フラグを立てることで、event_message側でも
    確実にコメントの処理を止められるようにしている
    (close()が本当に接続を切るまでのタイムラグをカバーする保険)。
    """
    import asyncio

    _is_stopped["value"] = True

    for bot in list(_running_bots):
        try:
            loop = bot.loop
            asyncio.run_coroutine_threadsafe(bot.close(), loop)
        except Exception as e:
            print(f"[TwitchWatcher] 停止処理中にエラーが発生しました: {e}")
        _running_bots.remove(bot)


if __name__ == "__main__":
    def print_comment(username, message):
        print(f"[{username}] {message}")

    start_watching(print_comment)
