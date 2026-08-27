# -*- coding: utf-8 -*-
"""
VOICEVOXの詳細設定画面(話速・音高・抑揚・音量の調整)

【機能】
- 各パラメータをスライダーで調整
- スライダーの隣に数値入力欄(手入力も可能、双方向に連動)
- リセットボタン(全パラメータをデフォルト値に戻す)
- テストボタン(現在の設定値で、選択中のボイスの試聴音声を生成)
- 設定値は voice_params.json に保存し、次回起動時にも反映する

【使い方】
from voice_settings_window import VoiceSettingsWindow
VoiceSettingsWindow(master, style_id=3, display_name="ずんだもん")
"""

import json
import os
import threading
import tkinter as tk
from tkinter import ttk

from resource_path import writable_path

VOICE_PARAMS_PATH = "voice_params.json"
HOTKEY_CONFIG_PATH = "hotkey_config.json"

# パラメータ名: (表示名, 最小値, 最大値, デフォルト値, 刻み幅)
PARAM_DEFS = {
    "speedScale": ("話速", 0.5, 2.0, 1.0, 0.01),
    "pitchScale": ("音高", -0.15, 0.15, 0.0, 0.01),
    "intonationScale": ("抑揚", 0.0, 2.0, 1.0, 0.01),
    "volumeScale": ("音量", 0.0, 2.0, 1.0, 0.01),
}

# 読み上げ内容のフィルター設定。VOICEVOXへ渡すパラメータではなく、
# 読み上げる「前」にテキスト自体を加工するかどうかの設定のため、
# main_window.py側でこれらのキーは speak_with_params() に渡す前に
# 取り除く(pop する)扱いにしている。
TEXT_FILTER_DEFAULTS = {
    "filter_urls": True,       # URLを読み上げから除外するか
    "filter_emoji": True,      # 絵文字・顔文字を読み上げから除外するか
    "max_speech_chars": 0,     # 読み上げる文字数の上限(0 = 無制限)
    "emote_announce_enabled": False,     # エモート付きコメントの代わりに一言読み上げるか
    "emote_announce_text": "エモートが届きました",  # その際に読み上げる文言
}

DEFAULT_HOTKEY = "Ctrl+Shift+M"  # ミュート切り替えの初期割り当て


def load_hotkey_config():
    """
    【重要】以前は相対パス("hotkey_config.json")のまま open() していたため、
    PyInstallerでビルドしたexeを、書き込み権限が制限された場所
    (Program Files配下等)にインストールした場合、正しい場所を
    読み書きできず、設定が保存されない不具合があった。
    writable_path() を使い、常に「exeがあるフォルダ」を基準にする
    ことで解消している(以下、voice_paramsも同様)。
    """
    path = writable_path(HOTKEY_CONFIG_PATH)
    if not os.path.exists(path):
        return {"mute_toggle": DEFAULT_HOTKEY}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"mute_toggle": DEFAULT_HOTKEY}


def save_hotkey_config(config: dict):
    with open(writable_path(HOTKEY_CONFIG_PATH), "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_voice_params():
    """保存済みの調整値を読み込む。無ければデフォルト値を返す。"""
    defaults = {key: PARAM_DEFS[key][3] for key in PARAM_DEFS}
    defaults.update(TEXT_FILTER_DEFAULTS)
    path = writable_path(VOICE_PARAMS_PATH)
    if not os.path.exists(path):
        return defaults
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        defaults.update(saved)
    except Exception:
        pass
    return defaults


def save_voice_params(params: dict):
    with open(writable_path(VOICE_PARAMS_PATH), "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)


class VoiceSettingsWindow(tk.Toplevel):
    def __init__(self, master, style_id=None, display_name="(未選択)"):
        super().__init__(master)
        self.title("VOICEVOX 詳細設定")
        self.geometry("480x660")
        self.resizable(False, False)

        self.style_id = style_id
        self.display_name = display_name

        self.params = load_voice_params()
        self.scale_vars = {}   # key -> DoubleVar(スライダー用)
        self.entry_vars = {}   # key -> StringVar(数値入力欄用)
        self._updating = False  # スライダー⇔入力欄の相互更新で無限ループしないためのフラグ

        self.hotkey_config = load_hotkey_config()
        self.hotkey_display_var = tk.StringVar(value=self.hotkey_config.get("mute_toggle", DEFAULT_HOTKEY))
        self._capturing_hotkey = False

        # 読み上げ内容のフィルター設定
        self.filter_urls_var = tk.BooleanVar(value=self.params.get("filter_urls", True))
        self.filter_emoji_var = tk.BooleanVar(value=self.params.get("filter_emoji", True))
        self.max_chars_var = tk.StringVar(value=str(self.params.get("max_speech_chars", 0)))

        # エモートを含むコメントは、本文自体は読み上げない(技術的な理由。
        # 詳しくはUIの説明文を参照)代わりに、固定の一言だけ読み上げる
        # ことができるようにするための設定。
        self.emote_announce_var = tk.BooleanVar(value=self.params.get("emote_announce_enabled", False))
        self.emote_announce_text_var = tk.StringVar(
            value=self.params.get("emote_announce_text", "エモートが届きました"),
        )

        ttk.Label(
            self, text=f"対象ボイス: {display_name}", font=("", 11, "bold"),
        ).pack(pady=(14, 4))

        self._build_sliders()
        self._build_filter_section()
        self._build_hotkey_section()
        self._build_footer()

    # ---------- スライダー行の構築 ----------

    def _build_sliders(self):
        container = ttk.Frame(self, padding=16)
        container.pack(fill="both", expand=True)

        for row, (key, (label, vmin, vmax, default, step)) in enumerate(PARAM_DEFS.items()):
            current_value = self.params.get(key, default)

            ttk.Label(container, text=label, width=8).grid(row=row, column=0, sticky="w", pady=10)

            scale_var = tk.DoubleVar(value=current_value)
            entry_var = tk.StringVar(value=f"{current_value:.2f}")
            self.scale_vars[key] = scale_var
            self.entry_vars[key] = entry_var

            scale = ttk.Scale(
                container, from_=vmin, to=vmax, orient="horizontal",
                variable=scale_var, length=260,
                command=lambda v, k=key: self._on_scale_changed(k),
            )
            scale.grid(row=row, column=1, sticky="ew", padx=8)

            entry = ttk.Entry(container, textvariable=entry_var, width=6, justify="right")
            entry.grid(row=row, column=2)
            entry.bind("<Return>", lambda e, k=key: self._on_entry_changed(k))
            entry.bind("<FocusOut>", lambda e, k=key: self._on_entry_changed(k))

        container.columnconfigure(1, weight=1)

    def _on_scale_changed(self, key):
        if self._updating:
            return
        self._updating = True
        value = self.scale_vars[key].get()
        self.entry_vars[key].set(f"{value:.2f}")
        self._updating = False

    def _on_entry_changed(self, key):
        if self._updating:
            return
        _, vmin, vmax, default, _ = PARAM_DEFS[key]
        try:
            value = float(self.entry_vars[key].get())
        except ValueError:
            value = default

        value = max(vmin, min(vmax, value))  # 範囲外の手入力を丸める

        self._updating = True
        self.scale_vars[key].set(value)
        self.entry_vars[key].set(f"{value:.2f}")
        self._updating = False

    # ---------- 読み上げ内容のフィルター ----------

    def _build_filter_section(self):
        frame = ttk.LabelFrame(self, text="読み上げ内容のフィルター", padding=12)
        frame.pack(fill="x", padx=16, pady=(4, 0))

        ttk.Checkbutton(
            frame, text="URLを読み上げない", variable=self.filter_urls_var,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 4))

        ttk.Checkbutton(
            frame, text="絵文字・顔文字・Twitchエモートを読み上げない", variable=self.filter_emoji_var,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 0))

        ttk.Label(
            frame,
            text="Twitchのエモート(スタンプ)が含まれるコメントは、翻訳・読み上げをせず、\n"
                 "公式チャットと同じ原文のまま表示します。",
            foreground="gray", font=("", 8), wraplength=420, justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(0, 4))

        self.emote_announce_check = ttk.Checkbutton(
            frame, text="エモートを含むコメントは代わりに一言読み上げる",
            variable=self.emote_announce_var, command=self._on_emote_announce_toggled,
        )
        self.emote_announce_check.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.emote_announce_entry = ttk.Entry(frame, textvariable=self.emote_announce_text_var, width=30)
        self.emote_announce_entry.grid(row=4, column=0, columnspan=2, sticky="w", pady=(4, 4), padx=(20, 0))

        ttk.Label(
            frame,
            text="コメント本文の代わりに、この文言を読み上げます\n"
                 "(エモート部分を自然に読み上げるのは技術的に難しいため、固定の一言のみ対応しています)。",
            foreground="gray", font=("", 8), wraplength=420, justify="left",
        ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0, 4))

        self._on_emote_announce_toggled()  # 初期状態(入力欄の有効/無効)を反映しておく

        ttk.Label(frame, text="文字数の上限").grid(row=6, column=0, sticky="w", pady=(6, 0))

        chars_row = ttk.Frame(frame)
        chars_row.grid(row=6, column=1, sticky="w", pady=(6, 0))
        entry = ttk.Entry(chars_row, textvariable=self.max_chars_var, width=6, justify="right")
        entry.pack(side="left")
        entry.bind("<Return>", lambda e: self._on_max_chars_changed())
        entry.bind("<FocusOut>", lambda e: self._on_max_chars_changed())
        ttk.Label(chars_row, text="文字(0で無制限)", foreground="gray").pack(side="left", padx=(6, 0))

        ttk.Label(
            frame,
            text="上限を超えた場合、読み上げ末尾に「(以下略)」を付けて打ち切ります。チャット欄には全文が表示されます。",
            foreground="gray", font=("", 8), wraplength=420, justify="left",
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(6, 0))

        frame.columnconfigure(1, weight=1)

    def _on_emote_announce_toggled(self):
        """チェックの有無に応じて、読み上げ文言の入力欄を有効/無効にする"""
        if self.emote_announce_var.get():
            self.emote_announce_entry.state(["!disabled"])
        else:
            self.emote_announce_entry.state(["disabled"])

    def _on_max_chars_changed(self):
        """文字数入力欄の値を検証し、0以上の整数に丸める"""
        try:
            value = int(self.max_chars_var.get())
        except ValueError:
            value = 0
        value = max(0, value)
        self.max_chars_var.set(str(value))

    # ---------- ホットキー設定 ----------

    def _build_hotkey_section(self):
        frame = ttk.LabelFrame(self, text="ホットキー", padding=12)
        frame.pack(fill="x", padx=16, pady=(4, 0))

        ttk.Label(frame, text="ミュート切り替え").grid(row=0, column=0, sticky="w")

        self.hotkey_button = ttk.Button(
            frame, textvariable=self.hotkey_display_var, width=20,
            command=self._start_hotkey_capture,
        )
        self.hotkey_button.grid(row=0, column=1, padx=8)

        ttk.Label(
            frame, text="ボタンを押してから、割り当てたいキーの組み合わせを押してください。",
            foreground="gray", font=("", 8),
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

        frame.columnconfigure(1, weight=1)

    def _start_hotkey_capture(self):
        """
        ボタンを押すとキャプチャモードに入り、次に押されたキーの
        組み合わせ(Ctrl/Shift/Alt + 何か)をホットキーとして採用する。
        """
        self._capturing_hotkey = True
        self.hotkey_display_var.set("キーを押してください...")
        self.bind("<KeyPress>", self._on_hotkey_keypress)
        self.focus_set()

    def _on_hotkey_keypress(self, event):
        if not self._capturing_hotkey:
            return

        # 修飾キー単体の押下は無視し、実際の組み合わせが確定するまで待つ
        if event.keysym in ("Control_L", "Control_R", "Shift_L", "Shift_R", "Alt_L", "Alt_R"):
            return

        parts = []
        if event.state & 0x4:   # Controlキー
            parts.append("Ctrl")
        if event.state & 0x1:   # Shiftキー
            parts.append("Shift")
        if event.state & 0x20000 or event.state & 0x8:  # Altキー(環境により値が異なるため両対応)
            parts.append("Alt")

        key_name = event.keysym
        if len(key_name) == 1:
            key_name = key_name.upper()
        parts.append(key_name)

        hotkey_str = "+".join(parts)
        self.hotkey_display_var.set(hotkey_str)
        self.hotkey_config["mute_toggle"] = hotkey_str

        self._capturing_hotkey = False
        self.unbind("<KeyPress>")

    # ---------- フッター(リセット/テスト/保存) ----------

    def _build_footer(self):
        frame = ttk.Frame(self, padding=(16, 8))
        frame.pack(fill="x", side="bottom")

        ttk.Button(frame, text="リセット", command=self._reset).pack(side="left")
        ttk.Button(frame, text="テスト再生 🔊", command=self._test_play).pack(side="left", padx=8)

        ttk.Button(frame, text="保存して閉じる", command=self._save_and_close).pack(side="right")
        ttk.Button(frame, text="閉じる", command=self.destroy).pack(side="right", padx=(0, 8))

    def _reset(self):
        self._updating = True
        for key, (_, _, _, default, _) in PARAM_DEFS.items():
            self.scale_vars[key].set(default)
            self.entry_vars[key].set(f"{default:.2f}")
        self._updating = False

    def _current_params(self):
        """
        保存・読み上げに使う設定値をまとめて返す。
        PARAM_DEFS(VOICEVOXの音声パラメータ)に加えて、
        読み上げ内容のフィルター設定も一緒に保存する。
        フィルター系のキーは、main_window.py側でVOICEVOXへの
        API呼び出し直前に取り除かれ(pop)、テキスト前処理にのみ使われる。
        """
        params = {key: self.scale_vars[key].get() for key in PARAM_DEFS}
        self._on_max_chars_changed()  # 保存前に、入力欄の値を一度検証・丸める
        params["filter_urls"] = self.filter_urls_var.get()
        params["filter_emoji"] = self.filter_emoji_var.get()
        params["emote_announce_enabled"] = self.emote_announce_var.get()
        params["emote_announce_text"] = self.emote_announce_text_var.get()
        try:
            params["max_speech_chars"] = int(self.max_chars_var.get())
        except ValueError:
            params["max_speech_chars"] = 0
        return params

    def _test_play(self):
        if self.style_id is None:
            return

        # テスト再生では、VOICEVOXの音声パラメータ(話速等)だけを渡す。
        # フィルター設定(URL/絵文字除外・文字数上限)はテキスト前処理用の
        # 設定であり、VOICEVOXのAPIには不要なキーのため含めない。
        voicevox_params = {key: self.scale_vars[key].get() for key in PARAM_DEFS}

        def task():
            try:
                from voicevox_speak import speak_with_params
                speak_with_params(
                    "こんにちは、今日もいい天気ですね。",
                    style_id=self.style_id,
                    params=voicevox_params,
                    blocking=True,
                )
            except Exception as e:
                print(f"[voice_settings] テスト再生に失敗しました: {e}")

        threading.Thread(target=task, daemon=True).start()

    def _save_and_close(self):
        save_voice_params(self._current_params())
        save_hotkey_config(self.hotkey_config)
        self.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    win = VoiceSettingsWindow(root, style_id=3, display_name="ずんだもん(ノーマル)")
    win.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
