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

VOICE_PARAMS_PATH = "voice_params.json"
HOTKEY_CONFIG_PATH = "hotkey_config.json"

# パラメータ名: (表示名, 最小値, 最大値, デフォルト値, 刻み幅)
PARAM_DEFS = {
    "speedScale": ("話速", 0.5, 2.0, 1.0, 0.01),
    "pitchScale": ("音高", -0.15, 0.15, 0.0, 0.01),
    "intonationScale": ("抑揚", 0.0, 2.0, 1.0, 0.01),
    "volumeScale": ("音量", 0.0, 2.0, 1.0, 0.01),
}

DEFAULT_HOTKEY = "Ctrl+Shift+M"  # ミュート切り替えの初期割り当て


def load_hotkey_config():
    if not os.path.exists(HOTKEY_CONFIG_PATH):
        return {"mute_toggle": DEFAULT_HOTKEY}
    try:
        with open(HOTKEY_CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"mute_toggle": DEFAULT_HOTKEY}


def save_hotkey_config(config: dict):
    with open(HOTKEY_CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(config, f, ensure_ascii=False, indent=2)


def load_voice_params():
    """保存済みの調整値を読み込む。無ければデフォルト値を返す。"""
    defaults = {key: PARAM_DEFS[key][3] for key in PARAM_DEFS}
    if not os.path.exists(VOICE_PARAMS_PATH):
        return defaults
    try:
        with open(VOICE_PARAMS_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        defaults.update(saved)
    except Exception:
        pass
    return defaults


def save_voice_params(params: dict):
    with open(VOICE_PARAMS_PATH, "w", encoding="utf-8") as f:
        json.dump(params, f, ensure_ascii=False, indent=2)


class VoiceSettingsWindow(tk.Toplevel):
    def __init__(self, master, style_id=None, display_name="(未選択)"):
        super().__init__(master)
        self.title("VOICEVOX 詳細設定")
        self.geometry("480x460")
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

        ttk.Label(
            self, text=f"対象ボイス: {display_name}", font=("", 11, "bold"),
        ).pack(pady=(14, 4))

        self._build_sliders()
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
        return {key: self.scale_vars[key].get() for key in PARAM_DEFS}

    def _test_play(self):
        if self.style_id is None:
            return

        params = self._current_params()

        def task():
            try:
                from voicevox_speak import speak_with_params
                speak_with_params(
                    "こんにちは、今日もいい天気ですね。",
                    style_id=self.style_id,
                    params=params,
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
