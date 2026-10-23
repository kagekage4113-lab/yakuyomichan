# -*- coding: utf-8 -*-
"""
オーバーレイの見た目(overlay_style.css)を、アプリ内から
直接編集できる画面。

【使い方】
from overlay_css_editor_window import OverlayCssEditorWindow
OverlayCssEditorWindow(master)
"""

import os
import tkinter as tk
from tkinter import ttk, messagebox

CSS_PATH = "overlay_style.css"

DEFAULT_CSS = """html, body {
  margin: 0;
  padding: 0;
  background: transparent;
  font-family: "Yu Gothic", "Meiryo", sans-serif;
  overflow: hidden;
}

#chat-container {
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  height: 100vh;
  padding: 12px;
  box-sizing: border-box;
}

.chat-line {
  background: rgba(20, 20, 30, 0.65);
  border-radius: 8px;
  padding: 8px 12px;
  margin-bottom: 6px;
  color: #ffffff;
  font-size: 18px;
  line-height: 1.4;
  animation: fadein 0.3s ease-in;
}

.chat-user {
  font-weight: bold;
  color: #7fd4ff;
  margin-right: 6px;
}

.chat-original {
  color: #aaaaaa;
  font-size: 14px;
  margin-top: 2px;
}

@keyframes fadein {
  from { opacity: 0; transform: translateY(6px); }
  to   { opacity: 1; transform: translateY(0); }
}
"""


class OverlayCssEditorWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("オーバーレイのデザイン編集 (CSS)")
        self.geometry("700x600")

        self._build_toolbar()
        self._build_editor()
        self._load_css()

    # ---------- UI構築 ----------

    def _build_toolbar(self):
        frame = ttk.Frame(self, padding=(10, 8))
        frame.pack(fill="x")

        ttk.Label(
            frame,
            text="色・文字サイズ・透明度・フォント等を自由に編集できます。"
                 "保存後、OBSでソースを更新すると反映されます。",
            foreground="gray",
        ).pack(side="left")

        ttk.Button(frame, text="初期値に戻す", command=self._reset_to_default).pack(side="right")

    def _build_editor(self):
        container = ttk.Frame(self, padding=(10, 0))
        container.pack(fill="both", expand=True)

        self.text = tk.Text(
            container, wrap="none", undo=True, font=("Consolas", 11),
        )
        vsb = ttk.Scrollbar(container, orient="vertical", command=self.text.yview)
        hsb = ttk.Scrollbar(container, orient="horizontal", command=self.text.xview)
        self.text.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.text.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")

        container.rowconfigure(0, weight=1)
        container.columnconfigure(0, weight=1)

        footer = ttk.Frame(self, padding=10)
        footer.pack(fill="x", side="bottom")
        ttk.Label(
            footer, text="※ 保存すると overlay_style.css が上書きされます。",
            foreground="gray", font=("", 8),
        ).pack(side="left")
        ttk.Button(footer, text="保存", command=self._save).pack(side="right")
        ttk.Button(footer, text="閉じる", command=self.destroy).pack(side="right", padx=(0, 8))

    # ---------- 読み込み・保存 ----------

    def _load_css(self):
        if os.path.exists(CSS_PATH):
            with open(CSS_PATH, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = DEFAULT_CSS
        self.text.delete("1.0", "end")
        self.text.insert("1.0", content)

    def _save(self):
        content = self.text.get("1.0", "end-1c")
        with open(CSS_PATH, "w", encoding="utf-8") as f:
            f.write(content)
        messagebox.showinfo(
            "保存しました",
            "デザインを保存しました。\nOBSでソースを右クリック→「更新」すると反映されます。",
            parent=self,
        )

    def _reset_to_default(self):
        if not messagebox.askyesno(
            "確認", "編集内容を破棄して、初期デザインに戻しますか?", parent=self,
        ):
            return
        self.text.delete("1.0", "end")
        self.text.insert("1.0", DEFAULT_CSS)


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    win = OverlayCssEditorWindow(root)
    win.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
