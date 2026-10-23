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

import twitch_badges
from resource_path import writable_path

try:
    import twitchio
    TWITCHIO_AVAILABLE = True
except ImportError:
    TWITCHIO_AVAILABLE = False

TOKEN_CONFIG_PATH = "token_config.json"

_running_bots = []  # 停止処理のために、起動中のBotインスタンスを覚えておく
_is_stopped = {"value": False}  # bot.close()が効かない場合の保険用フラグ


def _parse_badges_tag(badges_tag):
    """
    Twitch IRCの badges タグを解析する。

    タグの形式(例): "subscriber/12,premium/1"
    → "subscriber" バッジのバージョン "12"(=12ヶ月継続、等)、
       "premium" バッジのバージョン "1"、を装着している

    戻り値: [("subscriber", "12"), ("premium", "1")] のような
    (set_id, version) のタプルのリスト。バッジが無ければ空リスト。
    """
    if not badges_tag:
        return []

    badges = []
    for part in badges_tag.split(","):
        if "/" not in part:
            continue
        set_id, version = part.split("/", 1)
        badges.append((set_id, version))
    return badges


def _parse_emotes_tag(emotes_tag, message_text):
    """
    Twitch IRCの emotes タグを解析する。

    タグの形式(例): "25:0-4,12-16/1902:6-10"
    → エモートID "25" が 0〜4文字目と12〜16文字目に、
       エモートID "1902" が 6〜10文字目に、それぞれ出現する
      (開始・終了とも0始まり、終了位置も含む)

    戻り値: [{"id": "25", "start": 0, "end": 4, "text": "Kappa"}, ...] の
    ような、出現位置順に並んだリスト。エモートが無ければ空リスト。

    このオーバーレイ側での実際の画像表示(<img>タグへの差し替え)は
    main_window.py → overlay_server.py の流れで行われる。
    """
    if not emotes_tag:
        return []

    emotes = []
    for part in emotes_tag.split("/"):
        if ":" not in part:
            continue
        emote_id, ranges_str = part.split(":", 1)
        for rng in ranges_str.split(","):
            if "-" not in rng:
                continue
            start_str, end_str = rng.split("-", 1)
            try:
                start, end = int(start_str), int(end_str)
            except ValueError:
                continue
            emotes.append({
                "id": emote_id,
                "start": start,
                "end": end,
                "text": message_text[start:end + 1],
            })

    emotes.sort(key=lambda e: e["start"])
    return emotes


def load_token_config():
    """
    token_config.json からTwitchの接続情報を読み込む。
    無い場合はNoneを返す(GUI側でトークン未設定の案内を出す想定)。

    client_id は任意項目(バッジ表示機能を使う場合のみ必要)。
    未設定でも監視自体は問題なく開始できる(空文字列になるだけ)。

    【重要・不具合修正】以前はここで素の相対パス("token_config.json")の
    まま open() していたため、PyInstallerでビルドしたexeを実行した際に、
    実際の作業フォルダ(カレントディレクトリ)がexeのあるフォルダと
    一致しない場合(スタートメニューのショートカット経由での起動等)、
    token_settings_window.py が writable_path() 経由で保存した場所と
    ズレてしまい、「トークンを保存したのに見つからない」という不具合に
    つながっていた(ソースコードから python で直接実行した場合は、
    作業フォルダがたまたま一致するため、この不具合が表面化しなかった)。
    他の設定ファイルと同様、writable_path() を使うように統一する。
    """
    path = writable_path(TOKEN_CONFIG_PATH)
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    twitch_conf = data.get("twitch", {})
    if not twitch_conf.get("oauth_token") or not twitch_conf.get("channel"):
        return None
    twitch_conf.setdefault("client_id", "")
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
      on_comment(username: str, message: str, has_emote: bool, emotes: list,
                 badges: list) の形で呼ばれる。
      has_emote は、メッセージ内にTwitchエモート(スタンプ)が
      1つでも含まれていれば True になる。
      emotes は _parse_emotes_tag() が返す、位置情報つきのリスト
      (オーバーレイ側で実際の画像に差し替えるために使う)。
      badges は [{"set_id":..., "version":..., "image_url":...}, ...] の
      リスト(image_urlは、Client-IDが未設定/取得失敗時はNoneになる)。
    """

    def __init__(self, oauth_token, channel, on_comment, client_id=""):
        if not TWITCHIO_AVAILABLE:
            raise RuntimeError(
                "twitchioがインストールされていません。"
                "pip install twitchio を実行してください。"
            )
        super().__init__(token=oauth_token, initial_channels=[channel])
        self.on_comment = on_comment
        self.oauth_token = oauth_token
        self.channel = channel
        self.client_id = client_id
        self.badge_map = {}  # (set_id, version) -> image_url

    async def event_ready(self):
        print(f"[TwitchWatcher] 接続しました: {self.nick}")

        # 【重要】バッジ画像の取得はネットワークAPI呼び出しを伴うため、
        # メッセージが来るたびではなく、接続完了時に1回だけ行い、
        # 結果をメモリ上に保持しておく(twitch_badges.py側でも
        # プロセス内キャッシュしているため、実質的な二重キャッシュだが、
        # 毎コメントごとの辞書アクセスを避ける意味でここにも持たせている)。
        # Client-IDが未設定、または取得に失敗した場合は、
        # 空の辞書のまま(=バッジ画像なし)で動作を継続する。
        if self.client_id:
            try:
                self.badge_map = twitch_badges.load_badge_map(
                    self.channel, self.oauth_token, self.client_id,
                )
                print(f"[TwitchWatcher] バッジ情報を{len(self.badge_map)}件取得しました。")
            except Exception as e:
                print(f"[TwitchWatcher] バッジ情報の取得に失敗しました(表示のみ諦めます): {e}")

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

        # 【重要】Twitchのスタンプ(エモート)は、実際のメッセージ本文には
        # "HeyGuys" や "granclFaiar" のような、普通の英単語と見分けが
        # つかない文字列としてそのまま入っている。VOICEVOXやテキスト側の
        # フィルターだけでは「これがエモートかどうか」を判定できないため、
        # Twitch IRCが別途付与してくれる "emotes" タグ(メッセージ中の
        # どの位置がエモートかを示す位置情報。エモートが無ければ空文字列)を
        # 直接参照して判定する。
        tags = getattr(message, "tags", None) or {}
        emotes_tag = tags.get("emotes", "") if isinstance(tags, dict) else ""
        emotes = _parse_emotes_tag(emotes_tag, content)
        has_emote = bool(emotes)

        # バッジ(サブスク・モデレーター等の実績アイコン)も、
        # emotesと同様にIRCタグから取得する。画像URLへの解決は
        # 接続時に読み込んだ self.badge_map を使う(Client-ID未設定/
        # 取得失敗時は空のままなので、image_urlは常にNoneになり、
        # オーバーレイ側は「画像なし」として静かに無視する)。
        badges_tag = tags.get("badges", "") if isinstance(tags, dict) else ""
        badges = [
            {"set_id": set_id, "version": version, "image_url": self.badge_map.get((set_id, version))}
            for set_id, version in _parse_badges_tag(badges_tag)
        ]

        if self.on_comment:
            self.on_comment(username, content, has_emote, emotes, badges)


def start_watching(on_comment):
    """
    設定ファイルの情報を使って、Twitch監視を開始する。
    on_comment(username, message, has_emote, emotes, badges) が、
    コメントを受け取るたびに呼ばれる。

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
        client_id=config.get("client_id", ""),
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
    def print_comment(username, message, has_emote, emotes, badges):
        emote_mark = f"[エモート{len(emotes)}個]" if has_emote else ""
        badge_mark = f"[バッジ{len(badges)}個]" if badges else ""
        print(f"[{username}] {message} {emote_mark}{badge_mark}")

    start_watching(print_comment)
