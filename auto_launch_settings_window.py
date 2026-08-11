# -*- coding: utf-8 -*-
"""
VOICEVOX / LM Studio の自動起動設定画面(別ウィンドウ)。

このアプリを起動した時に、VOICEVOX・LM Studioも
自動で立ち上げるかどうかを、トグルと実行ファイルパスで設定する。

【使い方】
from auto_launch_settings_window import AutoLaunchSettingsWindow
AutoLaunchSettingsWindow(master)
"""

import tkinter as tk
from tkinter import ttk, filedialog

from auto_launch import load_config, save_config
from app_settings import load_app_settings, save_app_settings


class AutoLaunchSettingsWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("自動起動設定")
        self.geometry("520x340")
        self.resizable(False, True)  # 縦方向だけリサイズ可能にしておく(内容が増減しても対応できるように)

        self.config_data = load_config()

        self.voicevox_enabled = tk.BooleanVar(value=self.config_data["voicevox"]["enabled"])
        self.voicevox_path = tk.StringVar(value=self.config_data["voicevox"]["exe_path"])
        self.lm_studio_enabled = tk.BooleanVar(value=self.config_data["lm_studio"]["enabled"])
        self.lm_studio_path = tk.StringVar(value=self.config_data["lm_studio"]["exe_path"])
        self.unload_on_exit = tk.BooleanVar(value=self.config_data.get("unload_llm_on_exit", False))

        self.app_settings = load_app_settings()
        self.max_chat_log_rows = tk.StringVar(value=str(self.app_settings["max_chat_log_rows"]))

        self._build_section(
            "VOICEVOX", self.voicevox_enabled, self.voicevox_path, row_offset=0,
        )
        self._build_section(
            "LM Studio", self.lm_studio_enabled, self.lm_studio_path, row_offset=1,
        )
        self._build_unload_section()
        self._build_chat_log_section()
        self._build_footer()

        # 中身を組み立てた後の、実際に必要な高さに合わせてウィンドウを
        # フィットさせる。固定サイズ(520x340)のままだと、後から
        # セクションを追加した際に、下側(保存・閉じるボタン等)が
        # ウィンドウからはみ出して見えなくなってしまっていたため。
        self.update_idletasks()
        required_height = self.winfo_reqheight()
        self.geometry(f"520x{required_height}")

    def _build_section(self, label, enabled_var, path_var, row_offset):
        frame = ttk.LabelFrame(self, text=label, padding=12)
        frame.pack(fill="x", padx=14, pady=(14 if row_offset == 0 else 8, 0))

        ttk.Checkbutton(
            frame, text=f"アプリ起動時に{label}も自動で起動する", variable=enabled_var,
        ).grid(row=0, column=0, columnspan=3, sticky="w")

        ttk.Label(frame, text="実行ファイル(.exe)").grid(row=1, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(frame, textvariable=path_var, width=42).grid(
            row=1, column=1, sticky="ew", pady=(8, 0), padx=6
        )
        ttk.Button(
            frame, text="参照...", command=lambda: self._browse(path_var),
        ).grid(row=1, column=2, pady=(8, 0))

        frame.columnconfigure(1, weight=1)

    def _browse(self, path_var):
        path = filedialog.askopenfilename(
            title="実行ファイルを選択", filetypes=[("実行ファイル", "*.exe"), ("すべてのファイル", "*.*")],
            parent=self,
        )
        if path:
            path_var.set(path)

    def _build_unload_section(self):
        frame = ttk.LabelFrame(self, text="終了時の動作", padding=12)
        frame.pack(fill="x", padx=14, pady=(8, 0))

        ttk.Checkbutton(
            frame,
            text="アプリを終了する時、LM Studioのモデルをメモリから解放する",
            variable=self.unload_on_exit,
        ).pack(anchor="w")

        ttk.Label(
            frame,
            text="オンにすると、アプリを閉じた後もVRAMがLLMに専有され続けるのを防げます。\n"
                 "(LM Studioアプリ自体は起動したままになります)",
            foreground="gray", font=("", 8), justify="left",
        ).pack(anchor="w", pady=(4, 0))

    def _build_chat_log_section(self):
        frame = ttk.LabelFrame(self, text="チャットログ欄", padding=12)
        frame.pack(fill="x", padx=14, pady=(8, 0))

        row = ttk.Frame(frame)
        row.pack(fill="x")
        ttk.Label(row, text="画面に保持する件数").pack(side="left")
        ttk.Entry(row, textvariable=self.max_chat_log_rows, width=6, justify="right").pack(
            side="left", padx=8,
        )
        ttk.Label(row, text="件").pack(side="left")

        ttk.Label(
            frame,
            text="古いコメントは自動的に消えていきます(既定: 100件)。\n"
                 "件数を増やすほど、長時間の配信で表示が重くなる場合があります。\n"
                 "(保存されるログファイル自体には影響しません)",
            foreground="gray", font=("", 8), justify="left",
        ).pack(anchor="w", pady=(4, 0))

    def _build_footer(self):
        frame = ttk.Frame(self, padding=(14, 10))
        frame.pack(fill="x", side="bottom")

        ttk.Label(
            frame,
            text="LM Studioは起動しても、モデルのロード・サーバー起動は\n"
                 "手動が必要な場合があります。LM Studio側の自動起動設定もご確認ください。",
            foreground="gray", font=("", 8), justify="left",
        ).pack(side="left")

        ttk.Button(frame, text="保存", command=self._save).pack(side="right")
        ttk.Button(frame, text="閉じる", command=self.destroy).pack(side="right", padx=(0, 8))

    def _save(self):
        config = {
            "voicevox": {
                "enabled": self.voicevox_enabled.get(),
                "exe_path": self.voicevox_path.get().strip(),
            },
            "lm_studio": {
                "enabled": self.lm_studio_enabled.get(),
                "exe_path": self.lm_studio_path.get().strip(),
            },
            "unload_llm_on_exit": self.unload_on_exit.get(),
        }
        save_config(config)

        try:
            max_rows = int(self.max_chat_log_rows.get())
            max_rows = max(10, max_rows)  # 極端に少なすぎる値を防ぐ最低ライン
        except ValueError:
            max_rows = self.app_settings["max_chat_log_rows"]  # 不正な入力は元の値を維持

        self.app_settings["max_chat_log_rows"] = max_rows
        save_app_settings(self.app_settings)

        self.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    win = AutoLaunchSettingsWindow(root)
    win.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
