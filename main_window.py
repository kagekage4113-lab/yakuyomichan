# -*- coding: utf-8 -*-
"""
多言語チャット翻訳読み上げボット - メイン画面

【構成】
- メニューバー(ファイル / 配信 / VOICEVOX / 表示 / ヘルプ)
- 上部: プラットフォーム切り替え、起動/停止ボタン
- 中央: チャットログ(プラットフォーム / ユーザー名 / 原文 / 読み上げ内容)
- 下部: 音量スライダー、選択中ボイスの表示、ボイス選択ボタン
- 最下部: 3行コンソール(右クリックで全画面表示に切り替え)

【前提】
同じフォルダに voice_select_window.py, play_sample.py,
character_meta.json, character_icons/ があること。

【使い方】
python main_window.py
"""

import json
import os
import threading

import requests
import tkinter as tk
from tkinter import ttk

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import sv_ttk
    SV_TTK_AVAILABLE = True
except ImportError:
    SV_TTK_AVAILABLE = False

from voice_select_window import VoiceSelectWindow
from voice_settings_window import VoiceSettingsWindow, load_hotkey_config, load_voice_params
from token_settings_window import TokenSettingsWindow
from overlay_design_window import OverlayDesignWindow
from lang_detect import needs_translation
from translator import translate_to_japanese, load_model, unload_model
from voicevox_speak import speak_with_params
import twitch_watcher
import youtube_watcher
import overlay_server
import chat_logger
from resource_path import resource_path, writable_path
from auto_launch_settings_window import AutoLaunchSettingsWindow
from app_settings import load_app_settings, save_app_settings
from tutorial_window import maybe_show_tutorial
import auto_launch

ICON_DIR = "character_icons"
SELECTED_VOICE_PATH = "selected_voice.json"  # 選んだボイスをアプリ再起動後も覚えておくための保存先

APP_NAME = "やく読みちゃん"
APP_VERSION = "1.1.2"
README_PATH = "README_ja.txt"

# アップデート確認先のGitHubリポジトリ("ユーザー名/リポジトリ名")
GITHUB_REPO = "kagekage4113-lab/multilingual-chat-tts-bot"


def _parse_version(tag: str):
    """
    "v1.1.0" や "1.1.0" のようなタグ文字列を (1, 1, 0) のような
    整数タプルに変換する。比較(新しいかどうかの判定)をしやすくするため。
    想定外の形式(数字以外が混ざっている等)の場合は None を返す。
    """
    if not tag:
        return None
    cleaned = tag.lstrip("vV").strip()
    parts = cleaned.split(".")
    try:
        return tuple(int(p) for p in parts)
    except ValueError:
        return None


class ConsolePanel(ttk.Frame):
    """
    下部の3行コンソール。
    通常時は直近3行だけを表示し、右クリックで全画面ログ表示に
    切り替わる(左上に×ボタンで元に戻る)。
    """

    MAX_HISTORY = 500  # 保持しておくログの最大行数

    def __init__(self, master):
        super().__init__(master)
        self.history = []
        self.expanded = False

        self.text = tk.Text(
            self, height=3, bg="#1e1e1e", fg="#cccccc",
            font=("Consolas", 9), state="disabled", wrap="none",
        )
        self.text.pack(fill="both", expand=True)
        self.text.bind("<Button-3>", self._toggle_expand)  # 右クリック

        self.close_btn = ttk.Button(self, text="✕ 閉じる", command=self._collapse)
        # 展開時だけ表示するので、初期状態ではpackしない

        self.text.tag_config("error", foreground="#ff6b6b")
        self.text.tag_config("normal", foreground="#cccccc")

    def log(self, message, level="normal"):
        self.history.append((message, level))
        if len(self.history) > self.MAX_HISTORY:
            self.history.pop(0)
        self._render()

    def _render(self):
        self.text.config(state="normal")
        self.text.delete("1.0", "end")

        lines_to_show = self.history if self.expanded else self.history[-3:]
        for message, level in lines_to_show:
            self.text.insert("end", message + "\n", level)

        self.text.see("end")
        self.text.config(state="disabled")

    def _toggle_expand(self, event=None):
        if not self.expanded:
            self._expand()

    def _expand(self):
        self.expanded = True
        self.text.config(height=20)
        self.close_btn.pack(anchor="ne")
        self._render()

    def _collapse(self):
        self.expanded = False
        self.text.config(height=3)
        self.close_btn.pack_forget()
        self._render()


class MainWindow(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_NAME)
        self.geometry("900x600")
        self.minsize(700, 480)

        # モダンな見た目のテーマ(sv-ttk)が利用可能なら適用する。
        # 標準のTkinterの見た目(いわゆる「作った感」)から、
        # ダークモード基調のすっきりした印象に変わる。
        # ライブラリが無い環境でも、アプリ自体は標準の見た目のまま
        # 問題なく動作する(必須の依存にはしない)。
        if SV_TTK_AVAILABLE:
            sv_ttk.set_theme("dark")

        # タイトルバーのアイコン。app_icon.ico が同じフォルダにあれば
        # それを使う(ダーク背景に合わせて用意したもの)。
        # 無い場合はOS標準のデフォルトアイコンのままになる。
        if os.name == "nt" and os.path.exists("app_icon.ico"):
            try:
                self.iconbitmap("app_icon.ico")
            except tk.TclError:
                pass  # アイコンファイルが壊れている等の場合は無視して続行

        self.selected_style_id = None
        self.selected_label = tk.StringVar(value="(未選択)")
        self.selected_icon_photo = None  # 参照保持用(GC対策)

        # 音量ゲージも、前回起動時の値を app_settings.json から復元する。
        # 【重要】以前は毎回 70 固定で起動していたため、
        # 前回100に上げていても、再起動のたびに毎回上げ直す必要があった。
        saved_volume = load_app_settings().get("volume", 70)
        self.volume_var = tk.DoubleVar(value=saved_volume)

        # プラットフォーム選択(Twitch / YouTube / Twitch + YouTube)は、
        # 前回起動時に選んでいたものを app_settings.json から復元する。
        # 【重要】以前は毎回 "Twitch" 固定で起動していたため、
        # 前回YouTubeを選んでいた場合でも、再起動のたびに
        # 手動で選び直す必要があり地味に不便だった。
        # 万一、保存されている値が選択肢に無い(設定ファイルの手動編集や
        # 過去バージョンとの互換性の都合等)場合は "Twitch" にフォールバックする。
        PLATFORM_CHOICES = ("Twitch", "YouTube", "Twitch + YouTube")
        saved_platform = load_app_settings().get("selected_platform", "Twitch")
        if saved_platform not in PLATFORM_CHOICES:
            saved_platform = "Twitch"
        self.platform_var = tk.StringVar(value=saved_platform)

        self.is_running = False

        self._build_menu()
        self._build_platform_bar()
        self._build_chat_area()
        self._build_control_bar()
        self._build_console()

        self._load_selected_voice()
        self._register_hotkeys()
        self._start_overlay_server()
        self._run_auto_launch()
        self.protocol("WM_DELETE_WINDOW", self._on_exit)
        self.console.log("アプリを起動しました。")

        # 初回起動時だけ、簡易チュートリアルを表示する。
        # GUIが完全に描画されてから出したいので、少し遅延させる。
        self.after(300, lambda: maybe_show_tutorial(self))

    def _run_auto_launch(self):
        """
        設定で有効化されていれば、VOICEVOX/LM Studioを自動起動する。
        別スレッドで行い、起動待ちでメイン画面がフリーズしないようにする。
        """
        def task():
            auto_launch.auto_launch_all(log_func=lambda msg: self._safe_after(lambda: self.console.log(msg)))

        threading.Thread(target=task, daemon=True).start()

    def _on_exit(self):
        """
        アプリ終了時の処理。
        チャット監視中(is_running)にアプリを閉じた場合は、
        起動中と同じ理屈でLM StudioのモデルをVRAMから解放してから
        GUIを閉じる。監視していない状態で閉じる場合は、既に
        停止時のアンロード処理が済んでいるはずなので、
        設定(unload_llm_on_exit)を見て、念のためもう一度実行するかを決める。
        """
        config = auto_launch.load_config()

        if self.is_running or config.get("unload_llm_on_exit"):
            self.console.log("LM Studioのモデルを解放しています...")
            unload_model()

        self.destroy()

    def _register_hotkeys(self):
        """
        詳細設定画面で保存されたホットキー(例: "Ctrl+Shift+M")を登録する。

        【重要】Tkinterのbind_all()は「このアプリのウィンドウに
        フォーカスがある時」しか反応しないため、配信中にOBSや
        ゲーム画面にフォーカスがある状態では機能しない。
        そのため、OS全体で有効なグローバルホットキーを扱える
        keyboardライブラリを使う。(pip install keyboard が必要)

        アプリ起動時に加えて、詳細設定画面を閉じた後に再度呼べば、
        変更後のホットキーにすぐ反映できる。
        """
        config = load_hotkey_config()
        hotkey_str = config.get("mute_toggle", "")
        if not hotkey_str:
            return

        try:
            import keyboard
        except ImportError:
            self.console.log(
                "ホットキー機能には keyboard ライブラリが必要です。"
                "pip install keyboard を実行してください。",
                level="error",
            )
            return

        # keyboardライブラリは "ctrl+shift+m" のような小文字連結表記を使う
        keyboard_format = "+".join(part.lower() for part in hotkey_str.split("+"))

        try:
            # 既存の登録が残っていれば、一旦解除してから登録し直す
            if hasattr(self, "_current_hotkey_format"):
                keyboard.remove_hotkey(self._current_hotkey_format)

            # keyboardのコールバックは別スレッドから呼ばれるため、
            # Tkinterの操作はself.afterでメインスレッドに戻す
            keyboard.add_hotkey(
                keyboard_format,
                lambda: self._safe_after(self._toggle_mute),
            )
            self._current_hotkey_format = keyboard_format
            self.console.log(f"ホットキーを登録しました: {hotkey_str}")
        except Exception as e:
            self.console.log(f"ホットキーの登録に失敗しました({hotkey_str}): {e}", level="error")

    def _start_overlay_server(self):
        """
        OBS用のオーバーレイサーバーを、GUIとは別スレッドで起動する。
        アプリの起動と同時に立ち上げておき、常時OBSから読み込める状態にする。
        """
        threading.Thread(target=overlay_server.run_server, daemon=True).start()
        self.console.log("オーバーレイサーバーを起動しました: http://127.0.0.1:8765/overlay")

    # ---------- メニューバー ----------

    def _build_menu(self):
        menubar = tk.Menu(self)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="ログを開く", command=self._open_log_folder)
        file_menu.add_command(label="設定フォルダを開く", command=self._open_settings_folder)
        file_menu.add_separator()
        file_menu.add_command(label="自動起動設定(VOICEVOX / LM Studio)", command=self._open_auto_launch_settings)
        file_menu.add_separator()
        file_menu.add_command(label="終了", command=self._on_exit)
        menubar.add_cascade(label="ファイル", menu=file_menu)

        stream_menu = tk.Menu(menubar, tearoff=0)
        stream_menu.add_command(label="トークン設定(Twitch / YouTube)", command=self._open_token_settings)
        menubar.add_cascade(label="配信", menu=stream_menu)

        # LLM翻訳のON/OFF設定。OFFにすると、どの言語のコメントも
        # 判定・翻訳せずそのままVOICEVOXで読み上げる、
        # 「VOICEVOXの操作性を拡張するだけの、軽量な読み上げツール」
        # として使えるようにする(LM Studio等を用意したくない
        # ライトユーザー向けのモード)。
        # 実際の切り替えは、メイン画面上部の「翻訳: ON/OFF」ボタンから
        # 行う(以前は配信メニューにもチェックボックスを置いていたが、
        # 同じ設定を2箇所に置く必要はなく、メイン画面のボタンだけに
        # 一本化した)。ここでは変数の初期化だけ行っておく。
        app_settings = load_app_settings()
        self.translation_enabled_var = tk.BooleanVar(value=app_settings.get("translation_enabled", True))

        voicevox_menu = tk.Menu(menubar, tearoff=0)
        voicevox_menu.add_command(label="キャラクター選択", command=self._open_voice_select)
        menubar.add_cascade(label="VOICEVOX", menu=voicevox_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        self.subtitle_mode_var = tk.StringVar(value="translated")
        view_menu.add_radiobutton(
            label="字幕なし", variable=self.subtitle_mode_var, value="off",
            command=self._on_subtitle_mode_changed,
        )
        view_menu.add_radiobutton(
            label="字幕あり(翻訳のみ)", variable=self.subtitle_mode_var, value="translated",
            command=self._on_subtitle_mode_changed,
        )
        view_menu.add_radiobutton(
            label="字幕あり(原文+翻訳)", variable=self.subtitle_mode_var, value="both",
            command=self._on_subtitle_mode_changed,
        )
        view_menu.add_separator()
        view_menu.add_command(
            label="オーバーレイURLをコピー",
            command=lambda: self._copy_overlay_url(),
        )
        view_menu.add_command(
            label="オーバーレイのデザインを設定",
            command=self._open_overlay_design,
        )
        menubar.add_cascade(label="表示", menu=view_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="バージョン情報", command=self._show_about)
        help_menu.add_command(label="使い方(README)を開く", command=self._open_readme)
        help_menu.add_separator()
        help_menu.add_command(label="アップデートを確認", command=self._check_for_updates)
        menubar.add_cascade(label="ヘルプ", menu=help_menu)

        self.config(menu=menubar)

    def _not_implemented(self):
        self.console.log("この機能はまだ実装されていません。", level="normal")

    def _open_log_folder(self):
        chat_logger.open_log_folder()
        self.console.log(f"ログフォルダを開きました: {chat_logger.get_log_dir()}")

    def _open_settings_folder(self):
        """
        設定ファイル(token_config.json 等)が置かれているフォルダを開く。
        バックアップ・別PCへの引き継ぎは、ユーザー自身がこのフォルダの
        JSONファイルをコピーすることで行える(専用のエクスポート機能は
        あえて用意していない。トークンを含むため、誤って共有してしまう
        リスクを避けるため)。
        """
        path = os.path.abspath(".")
        try:
            if os.name == "nt":
                os.startfile(path)
            elif os.uname().sysname == "Darwin":
                os.system(f'open "{path}"')
            else:
                os.system(f'xdg-open "{path}"')
            self.console.log(f"設定フォルダを開きました: {path}")
        except Exception as e:
            self.console.log(f"設定フォルダを開けませんでした: {e}", level="error")

    def _show_about(self):
        from tkinter import messagebox
        messagebox.showinfo(
            "バージョン情報",
            f"{APP_NAME}\nバージョン: {APP_VERSION}\n\n"
            "翻訳: Gemma4 (ローカルLLM)\n"
            "読み上げ: VOICEVOX\n\n"
            "詳しい使い方はヘルプメニューのREADMEをご覧ください。",
            parent=self,
        )

    def _check_for_updates(self):
        """
        GitHub Releasesの最新版と、現在のバージョンを比較する。

        【インストーラーの上書きアップデートについて】
        installer.iss は DefaultDirName を {userappdata} にしており、
        AppId も毎回変えずに固定しているため、新しいインストーラーを
        そのまま実行するだけで、アンインストール等を挟まずに
        上書きで更新できるようになっている(トークン設定等の
        JSON設定ファイルも、インストール先フォルダに残ったまま引き継がれる)。
        そのため、この画面では「新しいバージョンがあるかどうかの確認」と
        「配布ページを開く」までを行い、実際のインストール(exeの実行)は
        ユーザー自身の操作に委ねる、という設計にしている。
        """
        self.console.log("アップデートを確認しています...")

        def task():
            try:
                resp = requests.get(
                    f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest",
                    timeout=10,
                )
                resp.raise_for_status()
                data = resp.json()
                latest_tag = data.get("tag_name", "")
                release_url = data.get("html_url", f"https://github.com/{GITHUB_REPO}/releases/latest")
            except Exception as e:
                self._safe_after(lambda: self._show_update_check_error(e))
                return

            self._safe_after(lambda: self._show_update_check_result(latest_tag, release_url))

        threading.Thread(target=task, daemon=True).start()

    def _show_update_check_error(self, error):
        from tkinter import messagebox
        self.console.log(f"アップデートの確認に失敗しました: {error}", level="error")
        messagebox.showerror(
            "アップデートの確認に失敗しました",
            f"最新バージョンの情報を取得できませんでした。\n\nインターネット接続を確認してください。\n\n{error}",
            parent=self,
        )

    def _show_update_check_result(self, latest_tag, release_url):
        from tkinter import messagebox
        import webbrowser

        latest_version = _parse_version(latest_tag)
        current_version = _parse_version(APP_VERSION)

        if latest_version is None:
            # タグの形式が想定外(例: "v1.1.0"以外の命名)だった場合は、
            # 新旧判定はできないが、リリースページ自体は案内できるようにしておく
            self.console.log(f"バージョン情報の形式を解釈できませんでした: {latest_tag}", level="normal")
            should_open = messagebox.askyesno(
                "アップデートを確認",
                f"最新リリース({latest_tag or '不明'})の情報をうまく解釈できませんでした。\n"
                "リリースページを開いて、手動で確認しますか?",
                parent=self,
            )
        elif latest_version > current_version:
            self.console.log(f"新しいバージョンがあります: {latest_tag}")
            should_open = messagebox.askyesno(
                "アップデートがあります",
                f"新しいバージョン {latest_tag} が公開されています。\n"
                f"(現在のバージョン: {APP_VERSION})\n\n"
                "配布ページを開いて、新しいインストーラーをダウンロードしますか?\n"
                "既存のアプリをアンインストールする必要はなく、\n"
                "新しいインストーラーをそのまま実行するだけで上書き更新できます。",
                parent=self,
            )
        else:
            self.console.log("お使いのバージョンは最新です。")
            messagebox.showinfo(
                "アップデートを確認",
                f"お使いのバージョン({APP_VERSION})は最新です。",
                parent=self,
            )
            return

        if should_open:
            webbrowser.open(release_url)

    def _open_readme(self):
        """
        README.mdを、OS標準の方法で開く。
        Markdownビューアやブラウザが関連付けられていればそれで開き、
        無ければ既定のテキストエディタで開かれる。
        """
        readme_path = resource_path(README_PATH)

        if not os.path.exists(readme_path):
            self.console.log(
                f"{README_PATH} が見つかりません。アプリと同じフォルダに配置してください。",
                level="error",
            )
            return

        try:
            if os.name == "nt":
                os.startfile(readme_path)
            elif os.uname().sysname == "Darwin":
                os.system(f'open "{readme_path}"')
            else:
                os.system(f'xdg-open "{readme_path}"')
        except Exception as e:
            self.console.log(f"READMEを開けませんでした: {e}", level="error")

    def _open_token_settings(self):
        self._open_or_focus("_token_settings_win", lambda: TokenSettingsWindow(self))

    def _on_translation_toggle(self):
        settings = load_app_settings()
        settings["translation_enabled"] = self.translation_enabled_var.get()
        save_app_settings(settings)

        # メニューのチェックボックスから切り替えた場合でも、
        # メイン画面のトグルボタンの表示(ON/OFF)を同期させる
        if hasattr(self, "translation_toggle_btn"):
            self._update_translation_toggle_label()

        if self.translation_enabled_var.get():
            self.console.log("LLM翻訳を有効にしました。")
            # 配信中(監視中)に翻訳をONにした場合は、その場でLLMをロードする。
            # 起動していない状態での切り替えでは、ロードする意味が無いので
            # is_running の時だけ行う。
            if self.is_running:
                self._load_llm_async()
        else:
            self.console.log("LLM翻訳を無効にしました。すべてのコメントをそのまま読み上げます。")
            # 逆に配信中に翻訳をOFFにした場合は、その場でLLMを解放し、
            # 無駄にVRAMを専有し続けないようにする。
            if self.is_running:
                self._unload_llm_async()

    def _open_auto_launch_settings(self):
        AutoLaunchSettingsWindow(self)

    def _on_subtitle_mode_changed(self):
        mode = self.subtitle_mode_var.get()
        overlay_server.set_display_mode(mode)
        self.console.log(f"字幕表示モードを変更しました: {mode}")

    def _copy_overlay_url(self):
        url = "http://127.0.0.1:8765/overlay"
        self.clipboard_clear()
        self.clipboard_append(url)
        self.console.log(f"オーバーレイURLをコピーしました: {url}")

    def _open_overlay_design(self):
        self._open_or_focus("_overlay_design_win", lambda: OverlayDesignWindow(self))

    # ---------- 上部: プラットフォーム/起動 ----------

    def _build_platform_bar(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="x")

        # 実際に監視スレッドが起動しているプラットフォームを個別に管理する。
        # (起動中に "Twitch" → "Twitch + YouTube" のように変更された場合、
        #  既に動いているTwitchはそのまま、YouTubeだけ追加で起動するため)
        self.watching_platforms = set()

        self.platform_var.trace_add("write", lambda *_: self._on_platform_changed())

        self.platform_var_widget = ttk.Combobox(
            frame, textvariable=self.platform_var,
            values=["Twitch", "YouTube", "Twitch + YouTube"], state="readonly", width=16,
        )
        self.platform_var_widget.pack(side="left")

        # 翻訳ON/OFFのトグルボタン。頻繁に切り替える可能性がある設定なので、
        # メニューの奥(配信メニュー)だけでなく、メイン画面にも
        # ワンクリックで切り替えられる形で置いている。
        # (self.translation_enabled_var は _build_menu 側で既に
        # 作成済みのものを、ここでも共有して使う)
        self.translation_toggle_btn = ttk.Button(
            frame, command=self._on_translation_toggle_button,
        )
        self.translation_toggle_btn.pack(side="left", padx=(10, 0))
        self._update_translation_toggle_label()

        ttk.Label(frame, text="トークンは配信メニューから設定", foreground="gray").pack(
            side="left", padx=10
        )

        self.run_btn = ttk.Button(frame, text="▶ 起動", command=self._toggle_running)
        self.run_btn.pack(side="right")

        # VOICEVOX / LM Studio への接続状態を、2行の小さいインジケーターで
        # 常時表示する。定期的に自動チェックし、今何が使える状態かを
        # 一目で分かるようにする(インストーラーでの自動セットアップが
        # 完璧でなくても、ユーザー自身が「今どうなっているか」を
        # 把握できるようにするための工夫)。
        #
        # 【重要】当初は🟢🔴🟡のような色付き絵文字を使っていたが、
        # Windows環境ではカラー絵文字が正しく描画されず、
        # 白抜きの丸(色無し)として表示されてしまう問題があった。
        # そのため、絵文字ではなく、tk.Labelのforeground(文字色)を
        # 直接指定する方式に変更し、確実に色分けされるようにしている。
        status_frame = ttk.Frame(frame)
        status_frame.pack(side="right", padx=(0, 12))
        self.voicevox_status_label = tk.Label(
            status_frame, text="● VOICEVOX", font=("", 8), fg="gray",
        )
        self.voicevox_status_label.pack(anchor="w")
        self.lmstudio_status_label = tk.Label(
            status_frame, text="● LM Studio", font=("", 8), fg="gray",
        )
        self.lmstudio_status_label.pack(anchor="w")

        self._start_status_check_loop()

    def _start_status_check_loop(self):
        """VOICEVOX/LM Studioの接続状態を、定期的にバックグラウンドで確認する"""
        def check():
            voicevox_ok = self._check_voicevox_status()
            lmstudio_state = self._check_lmstudio_status()
            self._safe_after(lambda: self._update_status_labels(voicevox_ok, lmstudio_state))
            # 5秒おきに繰り返しチェックする
            threading.Timer(5.0, lambda: threading.Thread(target=check, daemon=True).start()).start()

        threading.Thread(target=check, daemon=True).start()

    def _check_voicevox_status(self) -> bool:
        try:
            requests.get("http://127.0.0.1:50021/version", timeout=1.5)
            return True
        except Exception:
            return False

    def _check_lmstudio_status(self) -> str:
        """
        "loaded"(モデルロード済み) / "running"(起動しているがモデル未ロード) /
        "off"(未接続) のいずれかを返す。
        """
        try:
            resp = requests.get("http://127.0.0.1:1234/v1/models", timeout=1.5)
            data = resp.json()
            models = data.get("data", [])
            return "loaded" if models else "running"
        except Exception:
            return "off"

    def _update_status_labels(self, voicevox_ok, lmstudio_state):
        self.voicevox_status_label.config(fg="#4caf50" if voicevox_ok else "#f44336")

        if lmstudio_state == "loaded":
            self.lmstudio_status_label.config(fg="#4caf50")
        elif lmstudio_state == "running":
            self.lmstudio_status_label.config(fg="#ffb300")
        else:
            self.lmstudio_status_label.config(fg="#f44336")

    def _update_translation_toggle_label(self):
        """翻訳トグルボタンの表示テキストを、現在の状態に合わせて更新する"""
        if self.translation_enabled_var.get():
            self.translation_toggle_btn.config(text="翻訳: ON")
        else:
            self.translation_toggle_btn.config(text="翻訳: OFF")

    def _on_translation_toggle_button(self):
        """メイン画面のトグルボタンが押された時の処理"""
        self.translation_enabled_var.set(not self.translation_enabled_var.get())
        self._update_translation_toggle_label()
        self._on_translation_toggle()

    def _on_platform_changed(self):
        """
        プルダウンが変更された時に呼ばれる。
        既に監視が起動中の場合は、新しく選ばれたプラットフォームのうち
        まだ起動していないものだけを追加で起動する。
        起動前の状態であれば、ここでは何もしない
        (「起動」ボタンを押した時にまとめて起動される)。

        選んだプラットフォームは、次回起動時にも復元できるよう
        app_settings.json に都度保存しておく。
        """
        settings = load_app_settings()
        settings["selected_platform"] = self.platform_var.get()
        save_app_settings(settings)

        if self.is_running:
            self._start_watching()

    def _toggle_running(self):
        self.is_running = not self.is_running
        if self.is_running:
            self.run_btn.config(text="■ 停止")
            self._start_watching()
            # 翻訳がOFFの場合、LLM(LM Studio)は一切使わないため、
            # 無駄にロードして重くしないよう、翻訳ONの時だけロードする。
            if self.translation_enabled_var.get():
                self._load_llm_async()
        else:
            self.run_btn.config(text="▶ 起動")
            self.console.log("チャット監視を停止しました。(再度起動するにはアプリの再起動が必要です)")
            # twitchioのBot.run()はブロッキングかつ簡単に途中停止できないため、
            # 今回のひな形では「停止」は表示上のトグルに留めている。
            # YouTube側は stop_watching() で次のポーリング時に止められるので、
            # そちらだけは実際に停止させておく。
            youtube_watcher.stop_watching()
            self.watching_platforms.clear()
            # 翻訳がOFFの間はそもそもLLMをロードしていないはずだが、
            # 途中でON→OFFにした後の停止等、念のためどちらの状態でも
            # アンロードを試みておく(既にアンロード済みなら実質何もしない)。
            self._unload_llm_async()

    def _load_llm_async(self):
        """
        「起動」ボタンを押したタイミングで、LM Studioのモデルを
        事前にロードしておく(必須ではないが、最初のコメント処理が
        速くなる)。ネットワーク通信を伴うため別スレッドで行う。

        【重要】ロード/アンロードの処理中に、ユーザーが翻訳トグルを
        連打すると、複数のロード/アンロード処理が同時に走り、
        最終的な状態(実際にロードされているか)と、画面上の表示が
        食い違うバグがあった。これを防ぐため、処理中はトグルボタンを
        無効化し、連打自体をできないようにする。
        """
        if getattr(self, "_llm_toggle_in_progress", False):
            return  # 既に処理中なら、新たな操作は受け付けない

        self._llm_toggle_in_progress = True
        self._set_translation_toggle_enabled(False)

        def task():
            self._safe_after(lambda: self.console.log("LM Studioのモデルをロード中..."))
            load_model()
            self._safe_after(self._on_llm_toggle_finished)

        threading.Thread(target=task, daemon=True).start()

    def _unload_llm_async(self):
        """
        「停止」ボタン(または監視の停止)のタイミングで、
        LM StudioのモデルをVRAMから解放する。配信していない間まで
        VRAMを専有し続けないようにするための処理。
        処理中の連打対策は _load_llm_async と同様。
        """
        if getattr(self, "_llm_toggle_in_progress", False):
            return

        self._llm_toggle_in_progress = True
        self._set_translation_toggle_enabled(False)

        def task():
            self._safe_after(lambda: self.console.log("LM Studioのモデルを解放しています..."))
            unload_model()
            self._safe_after(self._on_llm_toggle_finished)

        threading.Thread(target=task, daemon=True).start()

    def _on_llm_toggle_finished(self):
        """ロード/アンロード処理が完了した後、ボタンを再度操作可能に戻す"""
        self._llm_toggle_in_progress = False
        self._set_translation_toggle_enabled(True)

    def _set_translation_toggle_enabled(self, enabled: bool):
        """翻訳トグルボタンの有効/無効を切り替える(連打防止用)"""
        if hasattr(self, "translation_toggle_btn"):
            self.translation_toggle_btn.config(state="normal" if enabled else "disabled")

    def _start_watching(self):
        """
        選択中のプラットフォームに応じて、監視状態を実際の選択に合わせる。
        まだ起動していないものは追加で起動し、選択から外れたものは停止する。
        「Twitch + YouTube」の場合は両方を同時に(別々のスレッドで)動かす。
        コメントが来るたびに _handle_comment がメインスレッド側で
        呼ばれるよう、self.after を使って安全にGUIへ反映する。
        """
        platform = self.platform_var.get()
        wants_twitch = platform in ("Twitch", "Twitch + YouTube")
        wants_youtube = platform in ("YouTube", "Twitch + YouTube")

        if wants_twitch and "twitch" not in self.watching_platforms:
            self._start_watching_twitch()
            self.watching_platforms.add("twitch")
        if not wants_twitch and "twitch" in self.watching_platforms:
            self._stop_watching_twitch()
            self.watching_platforms.discard("twitch")

        if wants_youtube and "youtube" not in self.watching_platforms:
            self._start_watching_youtube()
            self.watching_platforms.add("youtube")
        if not wants_youtube and "youtube" in self.watching_platforms:
            self._stop_watching_youtube()
            self.watching_platforms.discard("youtube")

    def _stop_watching_twitch(self):
        twitch_watcher.stop_watching()
        self.console.log("Twitchの監視を停止しました。")

    def _stop_watching_youtube(self):
        youtube_watcher.stop_watching()
        self.console.log("YouTubeの監視を停止しました。")

    def _start_watching_twitch(self):
        def on_comment(username, message):
            # twitchioのイベントは別スレッド(asyncioループ)から呼ばれるため、
            # Tkinterウィジェットの操作はself.afterでメインスレッドに戻して行う
            self._safe_after(lambda: self._handle_comment("twitch", username, message))

        def run_bot():
            # twitchio(asyncioベース)を別スレッドで動かす場合、
            # そのスレッドにはデフォルトのイベントループが存在しないため、
            # 明示的に新しいイベントループを作成してセットする必要がある。
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            ok = twitch_watcher.start_watching(on_comment)
            if not ok:
                self._safe_after(lambda: self.console.log(
                    "Twitch監視を開始できませんでした。トークン設定を確認してください。",
                    level="error",
                ))

        threading.Thread(target=run_bot, daemon=True).start()
        self.console.log("Twitchチャット監視を開始しました。")

    def _start_watching_youtube(self):
        def on_comment(username, message):
            self._safe_after(lambda: self._handle_comment("youtube", username, message))

        def run_watcher():
            ok = youtube_watcher.start_watching(on_comment)
            if not ok:
                self._safe_after(lambda: self.console.log(
                    "YouTube監視を開始できませんでした。APIキー・VIDEO_ID・配信状態を確認してください。",
                    level="error",
                ))

        threading.Thread(target=run_watcher, daemon=True).start()
        self.console.log("YouTubeチャット監視を開始しました。(数秒間隔のポーリング方式です)")

    def _handle_comment(self, platform, username, message):
        """1件のコメントを受け取り、判定→翻訳→読み上げ→チャット欄反映まで行う"""
        if self.selected_style_id is None:
            self.console.log("ボイスが選択されていません。VOICEVOXメニューから選んでください。", level="error")
            return

        def process():
            translation_enabled = load_app_settings().get("translation_enabled", True)

            if translation_enabled and needs_translation(message):
                translated = translate_to_japanese(message)
                original_for_display = message
            else:
                # 翻訳がOFFの場合は、判定すら行わずそのまま読み上げる。
                # (どの言語のコメントでも、無理にでもVOICEVOXで読ませる。
                # LM Studio等を用意していないライトユーザー向けのモード)
                translated = message
                original_for_display = ""  # 日本語コメント/翻訳オフ時は原文欄を空にする

            # メイン画面の音量ゲージ(0〜100)とミュート状態を、
            # 0.0〜1.0の掛け算係数に変換して読み上げに反映する
            volume_multiplier = 0.0 if self.is_muted else (self.volume_var.get() / 100.0)

            # 【重要】以前は speak() をそのまま呼んでいたため、
            # 「詳細設定」画面(voice_settings_window.py)で調整した
            # 話速・音高・抑揚・音量スケールが、テスト再生時にしか
            # 反映されず、実際のチャット読み上げでは常にデフォルト値の
            # ままになっていた(=保存はされているのに、次回起動時も
            # 常にデフォルトで読まれるように見えていた原因)。
            # voice_params.json から最新の詳細設定を読み込み、
            # メイン画面の音量ゲージ・ミュート状態(volume_multiplier)を
            # そのうえから掛け合わせてから speak_with_params() に渡す
            # ことで、両方の設定が同時に効くようにする。
            voice_params = dict(load_voice_params())
            voice_params["volumeScale"] = voice_params.get("volumeScale", 1.0) * volume_multiplier

            speak_with_params(
                translated, style_id=self.selected_style_id, params=voice_params, blocking=False,
            )
            overlay_server.push_comment(platform, username, original_for_display, translated)
            chat_logger.log_comment(platform, username, original_for_display, translated)

            self._safe_after(lambda: self.add_chat_row(platform, username, original_for_display, translated))

        # 翻訳・音声合成はネットワーク待ちが発生するため、GUIが固まらないよう別スレッドで処理
        threading.Thread(target=process, daemon=True).start()

    def _safe_after(self, callback):
        """
        別スレッドからGUI操作を行うためのself.afterラッパー。
        ウィンドウが既に破棄されている・mainloopの状態が不安定な
        タイミングで呼ばれてもアプリ全体が落ちないよう、
        例外を握りつぶしてログにだけ残す。
        """
        try:
            self.after(0, callback)
        except RuntimeError as e:
            print(f"[main_window] GUI更新をスキップしました: {e}")

    # ---------- 中央: チャットログ ----------

    def _build_chat_area(self):
        columns = ("user", "original", "translated")

        # スクロールバーを付けるため、Treeviewとスクロールバーを
        # 同じコンテナフレームの中に並べて配置する。
        container = ttk.Frame(self)
        container.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        # show="tree headings" にすることで、列#0(アイコン専用)を使えるようにする。
        # 通常のTreeviewの列(values側)には画像を置けないため、
        # プラットフォームアイコンだけは特別に列#0に表示する。
        self.chat_tree = ttk.Treeview(container, columns=columns, show="tree headings", height=12)

        # デフォルトの行の高さ(多くのテーマで20px前後)だと、
        # 18pxのアイコンが収まりきらず切れてしまうことがあるため、
        # 明示的に広げておく。
        style = ttk.Style()
        style.configure("Treeview", rowheight=28)

        # 列#0(アイコン列)には、本来「ツリー構造を展開するための
        # インジケーター(▶マーク)」分の余白が標準で入っており、
        # これが「アイコンの左に余計な空白がある」ように見える原因に
        # なっていた。今回はツリー構造(親子関係)を使わないため、
        # このインジケーター分の余白を、レイアウトの再定義によって
        # 取り除いている。
        style.layout("Treeview.Item", [
            ("Treeitem.padding", {"sticky": "nswe", "children": [
                ("Treeitem.image", {"side": "left", "sticky": ""}),
                ("Treeitem.focus", {"side": "left", "sticky": "", "children": [
                    ("Treeitem.text", {"side": "left", "sticky": ""}),
                ]}),
            ]}),
        ])

        self.chat_tree.heading("#0", text="")
        self.chat_tree.heading("user", text="ユーザー")
        self.chat_tree.heading("original", text="原文")
        self.chat_tree.heading("translated", text="読み上げ(日本語)")

        self.chat_tree.column("#0", width=26, anchor="center", stretch=False)
        self.chat_tree.column("user", width=110)
        self.chat_tree.column("original", width=300)
        self.chat_tree.column("translated", width=300)

        self.chat_tree.pack(side="left", fill="both", expand=True)

        # 縦スクロールバー。チャット欄が溜まってきた時に、
        # マウスホイールだけでなく、バーをドラッグしても過去のログを
        # 見返せるようにする。
        chat_scrollbar = ttk.Scrollbar(container, orient="vertical", command=self.chat_tree.yview)
        chat_scrollbar.pack(side="right", fill="y")
        self.chat_tree.configure(yscrollcommand=chat_scrollbar.set)

        self._platform_icons = self._load_platform_icons()

    def _load_platform_icons(self):
        """
        platform_icons/twitch.png, platform_icons/youtube.png を読み込む。
        見つからない場合は、そのプラットフォームだけ絵文字にフォールバックする
        (アイコンが用意されるまでの間も、見た目が崩れず動作するように)。

        【余白について】
        以前は画像自体に余白を足していたが、Treeviewの列の中央揃えの
        基準点が期待通りに働かず、狙った位置に寄せるのが難しかった。
        そのため、画像自体は加工せず、代わりに列#0の幅を画像サイズより
        少し広めに取ることで、列のcenter揃えだけで自然な余白を作る
        方式に変更している。
        """
        icons = {}
        icon_size = 18

        for platform, filename in [("twitch", "twitch.png"), ("youtube", "youtube.png")]:
            path = resource_path(os.path.join("platform_icons", filename))
            if PIL_AVAILABLE and os.path.exists(path):
                img = Image.open(path).convert("RGBA").resize((icon_size, icon_size))
                icons[platform] = ImageTk.PhotoImage(img)
            else:
                icons[platform] = None  # フォールバック(絵文字)を使う合図

        return icons

    def add_chat_row(self, platform, user, original, translated):
        """
        チャット欄に1行追加する。
        platform: "twitch" / "youtube"
        original: 日本語コメントの場合は "" のままでよい

        ユーザー名の先頭に半角スペースを補っているのは、
        アイコン列(#0)とユーザー名列の間の余白を、確実に
        作るため(画像側の余白やTreeviewの列幅調整だけでは、
        環境によって思った位置にならないことがあったため)。

        長時間の配信でチャット欄の行数が際限なく増え続けると、
        表示のパフォーマンスが落ちる・メモリを圧迫するため、
        設定された保管数(デフォルト100件)を超えたら、
        古い行から順に削除する。

        【自動スクロールについて】
        チャットが勢いよく流れている時、常に最新のコメントが
        画面下に見えている状態にしたい。一方で、ユーザーが過去ログを
        読み返そうとスクロールバーを上に動かしている最中に、
        新着コメントのたびに強制的に一番下へ引き戻されると、
        読んでいる内容が流れてしまって読みづらい。
        そのため、行を追加する直前の時点で「既に一番下まで
        表示していたか」を確認し、そうだった場合だけ、追加後も
        引き続き一番下(＝最新)が見えるように自動でスクロールする。
        過去ログを見返している最中(一番下ではない状態)であれば、
        表示位置はそのまま動かさない。
        """
        was_at_bottom = self._is_chat_scrolled_to_bottom()
        display_user = f"  {user}"

        icon = self._platform_icons.get(platform)
        if icon is not None:
            new_item = self.chat_tree.insert(
                "", "end", image=icon, values=(display_user, original or "—", translated),
            )
        else:
            # アイコン画像が無い場合のフォールバック
            fallback_mark = "🟣" if platform == "twitch" else "🔴"
            new_item = self.chat_tree.insert(
                "", "end", text=fallback_mark, values=(display_user, original or "—", translated),
            )

        self._trim_chat_log()

        if was_at_bottom:
            self.chat_tree.see(new_item)

    def _is_chat_scrolled_to_bottom(self):
        """
        チャット欄が、現在ちょうど一番下(最新行)まで表示されているかを判定する。
        Treeview.yview()は(表示中の先頭割合, 表示中の末尾割合)の
        タプルを返すので、末尾割合がほぼ1.0(=末尾まで見えている)かどうかで判定する。
        まだ1行も無い場合(yviewが(0.0, 1.0)を返す)も「一番下」扱いにして、
        最初の行から自動追従が効くようにする。
        """
        _, bottom_fraction = self.chat_tree.yview()
        return bottom_fraction >= 0.999

    def _trim_chat_log(self):
        """保管上限を超えた古いチャット行を削除する"""
        max_rows = load_app_settings().get("max_chat_log_rows", 100)
        children = self.chat_tree.get_children()
        overflow = len(children) - max_rows
        if overflow > 0:
            for item_id in children[:overflow]:
                self.chat_tree.delete(item_id)

    # ---------- 下部: 音量/ボイス選択 ----------

    def _build_control_bar(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill="x")

        self.is_muted = False
        self.volume_icon_var = tk.StringVar(value="🔊")
        volume_btn = tk.Label(
            frame, textvariable=self.volume_icon_var, font=("", 16), cursor="hand2",
        )
        volume_btn.pack(side="left")
        volume_btn.bind("<Button-1>", lambda e: self._toggle_mute())

        volume_scale = ttk.Scale(
            frame, from_=0, to=100, orient="horizontal",
            variable=self.volume_var, length=120,
            command=lambda v: self._save_volume(),
        )
        volume_scale.pack(side="left", padx=(4, 16))

        self.voice_icon_label = ttk.Label(frame)
        self.voice_icon_label.pack(side="left")

        ttk.Label(frame, textvariable=self.selected_label).pack(side="left", padx=(4, 10))

        ttk.Button(frame, text="ボイス選択", command=self._open_voice_select).pack(side="left")

        ttk.Button(frame, text="詳細設定", command=self._open_voice_settings).pack(side="right")

    def _toggle_mute(self):
        """
        スピーカーアイコンのクリックでミュートを切り替える。
        音量ゲージの値そのものは変えず、別フラグとして持つ。
        ゲージを動かさなくてもワンクリックで一時的に黙らせたい、
        という場面のためのショートカット。
        """
        self.is_muted = not self.is_muted
        self.volume_icon_var.set("🔇" if self.is_muted else "🔊")
        self.console.log("ミュートにしました。" if self.is_muted else "ミュートを解除しました。")

    def _save_volume(self):
        """
        音量ゲージを動かすたびに呼ばれ、次回起動時にも同じ音量で
        始められるよう app_settings.json に保存する。
        (ミュート状態は一時的なショートカットのため、あえて保存対象には
        含めていない。次回起動時は常にミュート解除の状態から始まる。)
        """
        settings = load_app_settings()
        settings["volume"] = self.volume_var.get()
        save_app_settings(settings)

    # ---------- サブウィンドウの多重起動防止 ----------

    def _open_or_focus(self, attr_name, factory):
        """
        サブウィンドウ(ボイス選択・詳細設定・オーバーレイのデザイン設定・
        トークン設定)を開く際の共通処理。

        既に同じウィンドウが開いている場合は、新しく作らず、
        既存のウィンドウを最前面に持ってくる(lift() + focus_force())。
        開いていない、または既に閉じられている場合(winfo_exists()が
        Falseになる)は、factory()で新しく作成し、self.{attr_name} に
        インスタンスを保持しておく。

        attr_name: インスタンスを保持しておく属性名(例: "_voice_select_win")
        factory: 新規ウィンドウを作成して返す関数(引数なしのcallable)
        """
        win = getattr(self, attr_name, None)
        if win is not None and win.winfo_exists():
            win.lift()
            win.focus_force()
            return win

        win = factory()
        setattr(self, attr_name, win)
        return win

    def _open_voice_select(self):
        self._open_or_focus(
            "_voice_select_win",
            lambda: VoiceSelectWindow(self, on_select=self._on_voice_selected),
        )

    def _open_voice_settings(self):
        def create():
            win = VoiceSettingsWindow(
                self, style_id=self.selected_style_id, display_name=self.selected_label.get(),
            )
            # 設定画面が閉じられたタイミングで、変更されたかもしれない
            # ホットキー設定を読み直して反映する
            win.bind("<Destroy>", lambda e: self._register_hotkeys() if e.widget == win else None)
            return win

        self._open_or_focus("_voice_settings_win", create)

    def _on_voice_selected(self, style_id, full_label, icon_path):
        self.selected_style_id = style_id
        self.selected_label.set(full_label)
        self._update_voice_icon(icon_path)
        self._save_selected_voice(style_id, full_label, icon_path)
        self.console.log(f"ボイスを変更しました: {full_label}")

    def _update_voice_icon(self, icon_path):
        if not icon_path or not os.path.exists(icon_path):
            self.voice_icon_label.config(image="", text="🎤")
            self.selected_icon_photo = None
            return

        if PIL_AVAILABLE:
            img = Image.open(icon_path).convert("RGBA").resize((28, 28))
            photo = ImageTk.PhotoImage(img)
        else:
            photo = tk.PhotoImage(file=icon_path)

        self.selected_icon_photo = photo  # GCされないよう参照を保持
        self.voice_icon_label.config(image=photo, text="")

    # ---------- 選択中ボイスの永続化 ----------

    def _save_selected_voice(self, style_id, full_label, icon_path):
        # 【重要】以前は相対パス(SELECTED_VOICE_PATH)のまま open() していたため、
        # PyInstallerでビルドしたexeを、書き込み権限が制限された場所
        # (Program Files配下等)にインストールした場合、正しい場所を
        # 読み書きできず、選択中ボイスが再起動後に引き継がれない
        # 不具合があった。writable_path() 経由に修正している。
        data = {"style_id": style_id, "full_label": full_label, "icon_path": icon_path}
        with open(writable_path(SELECTED_VOICE_PATH), "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_selected_voice(self):
        path = writable_path(SELECTED_VOICE_PATH)
        if not os.path.exists(path):
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.selected_style_id = data.get("style_id")
            self.selected_label.set(data.get("full_label", "(未選択)"))
            self._update_voice_icon(data.get("icon_path"))
        except Exception:
            pass  # 壊れていても起動自体は継続する

    # ---------- 最下部: コンソール ----------

    def _build_console(self):
        self.console = ConsolePanel(self)
        self.console.pack(fill="x", side="bottom")


if __name__ == "__main__":
    app = MainWindow()

    # PyInstallerの --splash オプションで表示したスプラッシュ画面を閉じる。
    # 【重要】--splash は「メインウィンドウが表示されたら自動で消える」
    # わけではなく、pyi_splash.close() を明示的に呼ばない限り、
    # ずっと表示されたままになる。GUIの構築(MainWindow())が
    # 完了した、このタイミングで閉じるのが適切。
    # 通常の `python main_window.py` 実行時(PyInstallerでビルド
    # していない時)は pyi_splash モジュール自体が存在しないため、
    # ImportError を無視して素通りするようにしている。
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass

    # 動作確認用のダミーチャット(実際にはチャット監視処理から呼ばれる)
    app.add_chat_row("twitch", "user_92", "Hello! nice stream today", "こんにちは、今日も配信いいね")
    app.add_chat_row("youtube", "たろう", "", "今日のご飯なに食べたの?")
    app.add_chat_row("twitch", "luna_fr", "Bonjour tout le monde", "みなさんこんにちは")

    app.mainloop()
