# -*- coding: utf-8 -*-
"""
配信プラットフォームのトークン設定画面(別ウィンドウ)。

メイン画面には表示させず、独立したウィンドウとして開く
(配信画面をキャプチャした時にトークンが映り込まないようにするため)。

入力内容は token_config.json に保存する。

【使い方】
from token_settings_window import TokenSettingsWindow
TokenSettingsWindow(master)
"""

import json
import os
import threading
import tkinter as tk
from tkinter import ttk, messagebox

import requests

from resource_path import writable_path

TOKEN_CONFIG_PATH = "token_config.json"


class TokenSettingsWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("配信トークン設定")
        self.geometry("520x560")
        self.resizable(False, False)

        self.vars = {
            "twitch_oauth": tk.StringVar(),
            "twitch_client_id": tk.StringVar(),
            "twitch_channel": tk.StringVar(),
            "youtube_api_key": tk.StringVar(),
            "youtube_video_id": tk.StringVar(),
        }

        self._load_existing()
        self._build_twitch_section()
        self._build_youtube_section()
        self._build_footer()

    # ---------- 既存設定の読み込み ----------

    def _load_existing(self):
        """
        【重要】以前は相対パス("token_config.json")のまま
        open()していたため、PyInstallerでビルドした exe を、
        書き込み権限が制限された場所(Program Files配下等)に
        インストールした場合、カレントディレクトリが予測できず、
        正しい場所を読み書きできていなかった。
        writable_path() を使い、常に「exeがあるフォルダ」を
        基準にすることで、この問題を解消している。
        """
        path = writable_path(TOKEN_CONFIG_PATH)
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception:
            return

        twitch = data.get("twitch", {})
        self.vars["twitch_oauth"].set(twitch.get("oauth_token", ""))
        self.vars["twitch_client_id"].set(twitch.get("client_id", ""))
        self.vars["twitch_channel"].set(twitch.get("channel", ""))

        youtube = data.get("youtube", {})
        self.vars["youtube_api_key"].set(youtube.get("api_key", ""))
        self.vars["youtube_video_id"].set(youtube.get("video_id", ""))

    # ---------- UI構築 ----------

    def _build_twitch_section(self):
        frame = ttk.LabelFrame(self, text="Twitch", padding=12)
        frame.pack(fill="x", padx=14, pady=(14, 8))

        ttk.Label(frame, text="OAuthトークン").grid(row=0, column=0, sticky="w", pady=4)
        entry = ttk.Entry(frame, textvariable=self.vars["twitch_oauth"], show="*", width=40)
        entry.grid(row=0, column=1, sticky="ew", pady=4)

        show_var = tk.BooleanVar(value=False)
        show_cb = ttk.Checkbutton(
            frame, text="表示", variable=show_var,
            command=lambda: entry.config(show="" if show_var.get() else "*"),
        )
        show_cb.grid(row=0, column=2, padx=(6, 0))

        ttk.Label(
            frame, text="oauth: から始まるトークン。twitchtokengenerator.com 等で取得できます。",
            foreground="gray", font=("", 8), wraplength=440, justify="left",
        ).grid(row=1, column=0, columnspan=3, sticky="w")

        ttk.Label(frame, text="Client ID (任意)").grid(row=2, column=0, sticky="w", pady=(10, 4))
        client_id_entry = ttk.Entry(frame, textvariable=self.vars["twitch_client_id"], show="*", width=40)
        client_id_entry.grid(row=2, column=1, sticky="ew", pady=(10, 4))

        client_id_show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            frame, text="表示", variable=client_id_show_var,
            command=lambda: client_id_entry.config(show="" if client_id_show_var.get() else "*"),
        ).grid(row=2, column=2, padx=(6, 0))

        ttk.Label(
            frame,
            text="通常は空欄で問題ありません。配信者のサブスク・実績バッジ(アイコン)を"
                 "オーバーレイにも表示したい場合のみ入力してください。"
                 "OAuthトークンと同じ場所(twitchtokengenerator.com等)で一緒に取得できます。"
                 "トークンとClient IDは、同じアプリ登録から発行されたものである必要があります。",
            foreground="gray", font=("", 8), wraplength=440, justify="left",
        ).grid(row=3, column=0, columnspan=3, sticky="w")

        ttk.Label(frame, text="チャンネル名").grid(row=4, column=0, sticky="w", pady=(10, 4))
        ttk.Entry(frame, textvariable=self.vars["twitch_channel"], width=40).grid(
            row=4, column=1, columnspan=2, sticky="ew", pady=(10, 4)
        )

        self.twitch_check_result = tk.StringVar(value="")
        check_row = ttk.Frame(frame)
        check_row.grid(row=5, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(check_row, text="接続確認", command=self._check_twitch).pack(side="left")
        ttk.Label(check_row, textvariable=self.twitch_check_result).pack(side="left", padx=8)

        frame.columnconfigure(1, weight=1)

    def _build_youtube_section(self):
        frame = ttk.LabelFrame(self, text="YouTube", padding=12)
        frame.pack(fill="x", padx=14, pady=8)

        ttk.Label(frame, text="APIキー").grid(row=0, column=0, sticky="w", pady=4)
        entry = ttk.Entry(frame, textvariable=self.vars["youtube_api_key"], show="*", width=40)
        entry.grid(row=0, column=1, sticky="ew", pady=4)

        show_var = tk.BooleanVar(value=False)
        show_cb = ttk.Checkbutton(
            frame, text="表示", variable=show_var,
            command=lambda: entry.config(show="" if show_var.get() else "*"),
        )
        show_cb.grid(row=0, column=2, padx=(6, 0))

        ttk.Label(frame, text="配信のVIDEO_ID").grid(row=1, column=0, sticky="w", pady=(10, 4))
        ttk.Entry(frame, textvariable=self.vars["youtube_video_id"], width=40).grid(
            row=1, column=1, columnspan=2, sticky="ew", pady=(10, 4)
        )

        self.youtube_check_result = tk.StringVar(value="")
        check_row = ttk.Frame(frame)
        check_row.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))
        ttk.Button(check_row, text="接続確認", command=self._check_youtube).pack(side="left")
        ttk.Label(check_row, textvariable=self.youtube_check_result).pack(side="left", padx=8)

        frame.columnconfigure(1, weight=1)

    def _build_footer(self):
        frame = ttk.Frame(self, padding=14)
        frame.pack(fill="x", side="bottom")

        ttk.Label(
            frame,
            text="この画面は配信のキャプチャに映さないよう、\nメイン画面とは別ウィンドウにしています。",
            foreground="gray", font=("", 8), justify="left",
        ).pack(side="left")

        ttk.Button(frame, text="保存", command=self._save).pack(side="right")
        ttk.Button(frame, text="閉じる", command=self.destroy).pack(side="right", padx=(0, 8))

    # ---------- 接続確認 ----------

    def _check_twitch(self):
        """
        Twitchの検証専用エンドポイントにトークンを投げて、
        有効かどうかを確認する。実際にチャットへ接続するわけではないので、
        軽量かつ安全に「トークンが生きているか」だけを確かめられる。
        """
        oauth_token = self.vars["twitch_oauth"].get().strip()
        if not oauth_token:
            self.twitch_check_result.set("トークンが入力されていません")
            return

        self.twitch_check_result.set("確認中...")

        def task():
            try:
                # oauth: プレフィックスは検証APIには不要なので取り除く
                token = oauth_token[6:] if oauth_token.startswith("oauth:") else oauth_token
                resp = requests.get(
                    "https://id.twitch.tv/oauth2/validate",
                    headers={"Authorization": f"OAuth {token}"},
                    timeout=10,
                )
                if resp.status_code == 200:
                    login = resp.json().get("login", "不明")
                    result = f"OK(ログイン名: {login})"
                else:
                    result = "NG(トークンが無効か期限切れの可能性があります)"
            except Exception as e:
                result = f"確認に失敗しました: {e}"

            self.after(0, lambda: self.twitch_check_result.set(result))

        threading.Thread(target=task, daemon=True).start()

    def _check_youtube(self):
        """
        YouTube Data APIに軽いリクエストを送り、APIキーが有効かどうかを
        確認する。VIDEO_IDが入力されていればその配信情報の取得を試み、
        無ければAPIキー自体の有効性だけを確認する簡易チェックにする。
        """
        api_key = self.vars["youtube_api_key"].get().strip()
        video_id = self.vars["youtube_video_id"].get().strip()

        if not api_key:
            self.youtube_check_result.set("APIキーが入力されていません")
            return

        self.youtube_check_result.set("確認中...")

        def task():
            try:
                params = {"part": "snippet", "key": api_key}
                if video_id:
                    params["id"] = video_id
                    resp = requests.get(
                        "https://www.googleapis.com/youtube/v3/videos", params=params, timeout=10,
                    )
                else:
                    # VIDEO_ID未入力でも、APIキー自体の有効性は
                    # 適当な検索クエリで確認できる
                    params["q"] = "test"
                    params["type"] = "video"
                    params["maxResults"] = 1
                    resp = requests.get(
                        "https://www.googleapis.com/youtube/v3/search", params=params, timeout=10,
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    if video_id and not data.get("items"):
                        result = "APIキーは有効ですが、この配信情報は見つかりませんでした"
                    else:
                        result = "OK"
                elif resp.status_code == 403:
                    result = "NG(APIキーが無効、または利用制限に達しています)"
                else:
                    result = f"NG(HTTP {resp.status_code})"
            except Exception as e:
                result = f"確認に失敗しました: {e}"

            self.after(0, lambda: self.youtube_check_result.set(result))

        threading.Thread(target=task, daemon=True).start()

    # ---------- 保存 ----------

    def _save(self):
        data = {
            "twitch": {
                "oauth_token": self.vars["twitch_oauth"].get().strip(),
                "client_id": self.vars["twitch_client_id"].get().strip(),
                "channel": self.vars["twitch_channel"].get().strip(),
            },
            "youtube": {
                "api_key": self.vars["youtube_api_key"].get().strip(),
                "video_id": self.vars["youtube_video_id"].get().strip(),
            },
        }

        try:
            with open(writable_path(TOKEN_CONFIG_PATH), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            # 【重要】以前は保存の失敗が握りつぶされ、「保存しました」の
            # ポップアップすら出ないまま、無反応に見えていた。
            # 書き込み権限が無い等の理由で失敗した場合は、
            # 必ずユーザーにエラーとして伝える。
            messagebox.showerror(
                "保存に失敗しました",
                f"設定を保存できませんでした。\n\n{e}\n\n"
                "インストール先のフォルダに書き込み権限があるか確認してください。",
                parent=self,
            )
            return

        messagebox.showinfo("保存しました", "トークン設定を保存しました。", parent=self)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    win = TokenSettingsWindow(root)
    win.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
