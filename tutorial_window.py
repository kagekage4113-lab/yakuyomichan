# -*- coding: utf-8 -*-
"""
初回起動時に表示する、簡易チュートリアル。

以下の3箇所を、順番に軽くハイライトしながら案内する。
1. プラットフォーム選択(左上のTwitch/YouTube切り替え)
2. トークン設定(メニュー「配信」→「トークン設定」)
3. 自動起動設定(メニュー「ファイル」→「自動起動設定」)

「二度と表示しない」チェックボックスを持ち、チェックした状態で
閉じると、以降は表示されなくなる(app_settings.json に記録)。

【使い方】
from tutorial_window import TutorialWindow
TutorialWindow(main_window_instance)
"""

import tkinter as tk
from tkinter import ttk

from app_settings import load_app_settings, save_app_settings

TUTORIAL_STEPS = [
    {
        "title": "① プラットフォームを選ぶ",
        "text": "左上のプルダウンから、監視したい配信サービスを選びます。\n"
                "Twitch / YouTube / 両方、から選べます。",
        "target_attr": "platform_var_widget",
    },
    {
        "title": "② トークンを設定する",
        "text": "メニューの「配信」→「トークン設定」から、\n"
                "Twitch・YouTubeの認証情報を入力してください。\n"
                "詳しい取得方法は、ヘルプメニューのREADMEに記載があります。",
        "target_attr": None,  # メニュー項目自体はハイライト対象にしない(メニューが閉じているため)
    },
    {
        "title": "③ 自動起動設定を確認する",
        "text": "メニューの「ファイル」→「自動起動設定」から、\n"
                "VOICEVOX・LMStudioを自動で起動するかどうかを設定できます。\n"
                "インストーラーを使った場合は、既に設定済みのことが多いです。",
        "target_attr": None,
    },
]


class TutorialWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("はじめに")
        self.geometry("420x320")
        self.resizable(False, False)
        self.transient(master)

        self.current_step = 0
        self._highlight_widget = None
        self._original_relief = None

        self._build_ui()
        self._show_step(0)

    def _build_ui(self):
        self.title_var = tk.StringVar()
        ttk.Label(self, textvariable=self.title_var, font=("", 13, "bold")).pack(
            pady=(20, 8), padx=20, anchor="w",
        )

        self.text_var = tk.StringVar()
        ttk.Label(self, textvariable=self.text_var, wraplength=380, justify="left").pack(
            padx=20, anchor="w",
        )

        self.step_indicator_var = tk.StringVar()
        ttk.Label(self, textvariable=self.step_indicator_var, foreground="gray").pack(
            pady=(16, 0), padx=20, anchor="w",
        )

        footer = ttk.Frame(self, padding=20)
        footer.pack(fill="x", side="bottom")

        self.dont_show_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            footer, text="次回から表示しない", variable=self.dont_show_var,
        ).pack(side="left")

        self.next_btn = ttk.Button(footer, text="次へ", command=self._next_step)
        self.next_btn.pack(side="right")
        ttk.Button(footer, text="スキップ", command=self._close).pack(side="right", padx=(0, 8))

    def _show_step(self, index):
        self._clear_highlight()

        step = TUTORIAL_STEPS[index]
        self.title_var.set(step["title"])
        self.text_var.set(step["text"])
        self.step_indicator_var.set(f"{index + 1} / {len(TUTORIAL_STEPS)}")

        if index == len(TUTORIAL_STEPS) - 1:
            self.next_btn.config(text="完了")
        else:
            self.next_btn.config(text="次へ")

        # 対象ウィジェットがあれば、枠を黄色くハイライトする
        target_attr = step.get("target_attr")
        if target_attr and hasattr(self.master_app, target_attr):
            widget = getattr(self.master_app, target_attr)
            self._highlight_widget = widget
            try:
                self._original_relief = widget.cget("relief")
                widget.config(relief="solid", borderwidth=2)
            except tk.TclError:
                pass  # ハイライトできないウィジェット種別の場合は諦める(致命的ではない)

    def _clear_highlight(self):
        if self._highlight_widget is not None:
            try:
                self._highlight_widget.config(
                    relief=self._original_relief, borderwidth=1,
                )
            except tk.TclError:
                pass
            self._highlight_widget = None

    def _next_step(self):
        if self.current_step < len(TUTORIAL_STEPS) - 1:
            self.current_step += 1
            self._show_step(self.current_step)
        else:
            self._close()

    def _close(self):
        self._clear_highlight()

        if self.dont_show_var.get():
            # 【重要】以前は、この保存処理が失敗した場合(書き込み権限の
            # 問題等)、例外がそのまま外に伝播し、_close()自体が
            # 完了しないまま止まってしまい、結果として
            # self.destroy() に到達せず、ウィンドウが閉じない、
            # という不具合につながっていた。保存に失敗しても
            # ウィンドウは必ず閉じられるよう、try/exceptで
            # 保存処理だけを独立させている。
            try:
                settings = load_app_settings()
                settings["tutorial_shown"] = True
                save_app_settings(settings)
            except Exception as e:
                print(f"[tutorial_window] 設定の保存に失敗しました(次回もチュートリアルが表示されます): {e}")

        self.destroy()


def maybe_show_tutorial(master):
    """
    まだチュートリアルを見せていなければ、表示する。
    main_window.py の起動処理から呼ぶ想定。
    """
    settings = load_app_settings()
    if not settings.get("tutorial_shown", False):
        TutorialWindow(master)
