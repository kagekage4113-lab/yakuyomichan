# -*- coding: utf-8 -*-
"""
オーバーレイの見た目を、CSSを直接書かせるのではなく、
スライダー・数値入力・カラーピッカー・フォント選択といった、
直感的な「つまみ」で調整できる画面。

調整結果は overlay_style.css として自動生成され、
ウィンドウ内のプレビュー欄(固定のサンプルコメント)に、
操作するたびリアルタイムで反映される。

overlay_server.py 側もCSSファイルの更新時刻を監視しており、
このウィンドウを閉じなくても、実際のOBS上のオーバーレイに
即座に反映される(OBS側でソースの「更新」操作をすれば見える)。

【保存される設定】
overlay_design.json : つまみの現在値(次回このウィンドウを開いた時に復元する)
overlay_style.css    : 実際にオーバーレイへ適用されるCSS(つまみの値から自動生成)

【使い方】
from overlay_design_window import OverlayDesignWindow
OverlayDesignWindow(master)
"""

import json
import os
import tkinter as tk
from tkinter import ttk, colorchooser

from resource_path import writable_path

CSS_PATH = "overlay_style.css"
DESIGN_CONFIG_PATH = "overlay_design.json"

FONT_CHOICES = [
    "Yu Gothic", "Yu Gothic UI", "Meiryo", "Meiryo UI",
    "MS Gothic", "MS PGothic", "MS UI Gothic",
    "MS Mincho", "MS PMincho",
    "Noto Sans JP", "Noto Serif JP",
    "游明朝", "UD デジタル 教科書体 N-R",
    "HGP創英角ゴシックUB", "HG丸ゴシックM-PRO",
    "Arial", "Segoe UI", "Consolas",
]

DEFAULT_DESIGN = {
    "font_size": 18,           # コメント文の文字サイズ
    "user_font_size": 18,      # ユーザー名の文字サイズ(別管理)
    "comment_bold": False,     # コメントを太字にするか
    "comment_underline": False,  # コメントに下線を付けるか
    "user_bold": True,         # ユーザー名を太字にするか
    "user_underline": False,   # ユーザー名に下線を付けるか
    "font_family": "Yu Gothic",
    "bg_color": "#141420",
    "bg_opacity": 65,   # 0-100(%)
    "text_color": "#ffffff",
    "user_color": "#7fd4ff",
    "original_color": "#aaaaaa",
    "corner_radius": 8,
    "max_lines": 8,     # オーバーレイに同時表示するコメントの最大行数
                        # (これを超えた古い行から自動的に消えていく)
    "stacked_layout": False,  # True: ユーザー名/コメント本文/翻訳文を
                              # それぞれ独立した行に縦に並べて表示する。
                              # False(デフォルト): ユーザー名と本文を
                              # 同じ行に表示する、従来のレイアウト。
    "show_original": True,   # 原文(翻訳前のコメント)も一緒に表示するか。
                              # Falseなら翻訳文だけを表示する。
}

# 各色項目につき24色のプリセットパレット。
# 配信オーバーレイでよく使われそうな、暗め〜鮮やかな色を一通り
# 揃えている。ユーザーは右クリックで、この中の好きなマスを
# 自由な色に上書きしてカスタマイズできる。
DEFAULT_PALETTE = [
    "#141420", "#1e1e2e", "#2d2d44", "#3a3a3a",
    "#000000", "#ffffff", "#f5f5f5", "#cccccc",
    "#7fd4ff", "#4a9eff", "#0066cc", "#00c2ff",
    "#ff7f7f", "#ff4a4a", "#cc0000", "#ff6b9d",
    "#7fff9d", "#4aff7f", "#00cc44", "#a0ff4a",
    "#ffd97f", "#ffaa4a", "#ff8800", "#ffe14a",
]

PALETTE_CONFIG_PATH = "overlay_palette.json"


def _hex_to_rgb(hex_color: str):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))


def build_css(design: dict) -> str:
    """つまみの値(design辞書)から、実際のCSSテキストを組み立てる"""
    r, g, b = _hex_to_rgb(design["bg_color"])
    bg_alpha = design["bg_opacity"] / 100.0

    return f"""html, body {{
  margin: 0;
  padding: 0;
  background: transparent;
  font-family: "{design['font_family']}", sans-serif;
  overflow: hidden;
}}

#chat-container {{
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  height: 100vh;
  padding: 12px;
  box-sizing: border-box;
}}

.chat-line {{
  background: rgba({r}, {g}, {b}, {bg_alpha});
  border-radius: {design['corner_radius']}px;
  padding: 8px 12px;
  margin-bottom: 6px;
  color: {design['text_color']};
  font-size: {design['font_size']}px;
  font-weight: {'bold' if design.get('comment_bold', False) else 'normal'};
  text-decoration: {'underline' if design.get('comment_underline', False) else 'none'};
  line-height: 1.4;
  animation: fadein 0.3s ease-in;
}}

.chat-user {{
  font-weight: {'bold' if design.get('user_bold', True) else 'normal'};
  text-decoration: {'underline' if design.get('user_underline', False) else 'none'};
  color: {design['user_color']};
  font-size: {design.get('user_font_size', design['font_size'])}px;
  margin-right: 6px;
}}

.chat-original {{
  color: {design['original_color']};
  font-size: {max(design['font_size'] - 4, 10)}px;
  margin-top: 2px;
}}

/* 「ユーザー名を独立した行にする(3行レイアウト)」ON時に使われるクラス。
   .chat-user(同じ行に表示する従来レイアウト用)とは別に用意している。 */
.chat-user-line {{
  font-weight: {'bold' if design.get('user_bold', True) else 'normal'};
  text-decoration: {'underline' if design.get('user_underline', False) else 'none'};
  color: {design['user_color']};
  font-size: {design.get('user_font_size', design['font_size'])}px;
}}

.chat-translated {{
  margin-top: 2px;
}}

@keyframes fadein {{
  from {{ opacity: 0; transform: translateY(6px); }}
  to   {{ opacity: 1; transform: translateY(0); }}
}}
"""


def load_shared_palette() -> list:
    """
    全ての色項目(背景色/文字色/ユーザー名色/原文色)で共有する、
    24色のパレットを読み込む。保存済みのカスタマイズが無ければ、
    デフォルトパレットを使う。
    """
    path = writable_path(PALETTE_CONFIG_PATH)
    if not os.path.exists(path):
        return list(DEFAULT_PALETTE)
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, list) and len(saved) == 24:
            return saved
        return list(DEFAULT_PALETTE)
    except Exception:
        return list(DEFAULT_PALETTE)


def save_shared_palette(palette: list):
    with open(writable_path(PALETTE_CONFIG_PATH), "w", encoding="utf-8") as f:
        json.dump(palette, f, ensure_ascii=False, indent=2)


def load_design() -> dict:
    path = writable_path(DESIGN_CONFIG_PATH)
    if not os.path.exists(path):
        return dict(DEFAULT_DESIGN)
    try:
        with open(path, "r", encoding="utf-8") as f:
            saved = json.load(f)
        design = dict(DEFAULT_DESIGN)
        design.update(saved)
        return design
    except Exception:
        return dict(DEFAULT_DESIGN)


def save_design(design: dict):
    with open(writable_path(DESIGN_CONFIG_PATH), "w", encoding="utf-8") as f:
        json.dump(design, f, ensure_ascii=False, indent=2)
    with open(writable_path(CSS_PATH), "w", encoding="utf-8") as f:
        f.write(build_css(design))
    # overlay_server.py側は、このCSSファイルの更新時刻(mtime)を
    # ポーリングで監視しており、保存するたびに自動でブラウザ側の
    # 表示にも反映される(OBS側では「ソースを更新」すれば見える)。


class OverlayDesignWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.title("オーバーレイのデザイン設定")
        self.geometry("640x600")
        self.minsize(400, 500)

        self.design = load_design()
        self.shared_palette = load_shared_palette()
        self._updating = False  # スライダー⇔数値入力の相互更新ループ防止

        self._build_font_section()
        self._build_color_section()
        self._build_size_section()
        self._build_preview()
        self._build_footer()

        # 中身を組み立てた後の、実際に必要な幅・高さに合わせて
        # ウィンドウをフィットさせる(固定値のままだと、右側に
        # 大きな余白ができてしまっていたため)。
        # fill="x" で広がる仕組みのセクションが多いため、一旦
        # 十分に小さいサイズに戻してから、必要なサイズを測り直す。
        self.geometry("1x1")
        self.update_idletasks()
        required_width = self.winfo_reqwidth()
        required_height = self.winfo_reqheight()
        self.geometry(f"{required_width}x{required_height}")

        # 【重要・不具合修正】プレビュー(Canvas)は、構築直後は仮の
        # 固定高さ(100px)で作られており、実際の設定(3行レイアウト
        # + 原文表示、等)に応じた本来の高さは _update_preview() が
        # 呼ばれて初めて確定する。以前は、この _update_preview() を
        # after_idle で「ウィンドウサイズ確定後」に遅延実行していたため、
        # プレビューが仮の高さより大きくなるケース(3行レイアウト等)で、
        # ウィンドウの高さがそれに追従できず、フッターの
        # 「保存して閉じる」ボタンがウィンドウ下端からはみ出して
        # 見切れてしまう不具合が起きていた。
        # そこで、ここで一度 _update_preview() を同期的に呼んで
        # プレビューの最終的な高さを確定させてから、改めて
        # ウィンドウサイズを測り直し(2段階目のフィット)、
        # はみ出しが起きないようにする。
        self.update_idletasks()
        self._update_preview()
        self.update_idletasks()
        required_width = self.winfo_reqwidth()
        required_height = self.winfo_reqheight()
        self.geometry(f"{required_width}x{required_height}")

        # 上記の2段階目フィットの過程で、Canvasの<Configure>イベントが
        # 再度発火して_update_previewが呼ばれることがあるため、
        # 念のため全てのイベント処理が完了した後にもう一度描画しておく。
        self.after_idle(self._update_preview)

    # ---------- フォント ----------

    def _build_font_section(self):
        frame = ttk.LabelFrame(self, text="フォント", padding=12)
        frame.pack(fill="x", padx=14, pady=(14, 6))

        self.font_var = tk.StringVar(value=self.design["font_family"])
        combo = ttk.Combobox(
            frame, textvariable=self.font_var, values=FONT_CHOICES, state="readonly",
        )
        combo.pack(fill="x")
        combo.bind("<<ComboboxSelected>>", lambda e: self._on_change())

    # ---------- 色(項目クリック→パレットで適用) ----------

    def _build_color_section(self):
        frame = ttk.LabelFrame(self, text="色", padding=12)
        frame.pack(fill="x", padx=14, pady=6)

        body = ttk.Frame(frame)
        body.pack(fill="x")

        # 左側: 4項目のボタン一覧(クリックすると「選択待ち」になる)
        left = ttk.Frame(body)
        left.pack(side="left", anchor="n")

        color_items = [
            ("bg_color", "背景"),
            ("text_color", "文字"),
            ("user_color", "名前"),
            ("original_color", "原文"),
        ]

        self.current_swatch_labels = {}
        self.color_item_buttons = {}
        self.active_color_key = None

        for key, label in color_items:
            row = ttk.Frame(left)
            row.pack(fill="x", pady=3)

            item_btn = tk.Label(
                row, text=label, width=6, anchor="w", cursor="hand2",
                relief="raised", borderwidth=1, padx=6, pady=4,
            )
            item_btn.pack(side="left")
            item_btn.bind("<Button-1>", lambda e, k=key: self._activate_color_target(k))
            self.color_item_buttons[key] = item_btn

            current_swatch = tk.Label(
                row, bg=self.design[key], width=3, relief="sunken",
            )
            current_swatch.pack(side="left", padx=(4, 0))
            self.current_swatch_labels[key] = current_swatch

        # 右側: 共有の24色パレット(1個だけ)
        right = ttk.Frame(body)
        right.pack(side="left", anchor="n", padx=(18, 0))

        self.target_label_var = tk.StringVar(value="項目をクリックして\n色を選んでください")
        ttk.Label(
            right, textvariable=self.target_label_var, foreground="gray", font=("", 8),
            justify="left",
        ).pack(anchor="w", pady=(0, 4))

        self.palette_container = ttk.Frame(right)
        self.palette_container.pack(anchor="w")
        self._build_shared_palette(self.palette_container)

        ttk.Label(
            frame,
            text="左クリック: 選択中の項目に色を適用  /  右クリック: そのマスの色を自由に編集",
            foreground="gray", font=("", 8),
        ).pack(anchor="w", pady=(8, 6))

        ttk.Button(frame, text="色設定を初期値に戻す", command=self._reset_colors).pack(anchor="e")

    def _build_shared_palette(self, parent):
        """共有の24色パレットを、6列×4行のグリッドで表示する"""
        swatch_size = 20
        for i, color_hex in enumerate(self.shared_palette):
            row_i, col_i = divmod(i, 6)
            btn = tk.Frame(
                parent, bg=color_hex, width=swatch_size, height=swatch_size,
                relief="raised", borderwidth=1, cursor="hand2",
            )
            btn.grid(row=row_i, column=col_i, padx=2, pady=2)
            btn.grid_propagate(False)

            btn.bind("<Button-1>", lambda e, idx=i: self._apply_shared_color(idx))
            btn.bind("<Button-3>", lambda e, idx=i: self._edit_shared_color(idx))

    def _activate_color_target(self, key):
        """
        項目名(例:「背景」)をクリックすると、その項目を
        「今から色を選ぶ対象」として選択状態にする。
        以後、右のパレットをクリックすると、この項目にその色が適用される。
        """
        self.active_color_key = key
        label = {"bg_color": "背景", "text_color": "文字", "user_color": "名前", "original_color": "原文"}[key]
        self.target_label_var.set(f"「{label}」に適用する色を\n選んでください")

        for k, btn in self.color_item_buttons.items():
            btn.config(relief="solid" if k == key else "raised", borderwidth=2 if k == key else 1)

    def _apply_shared_color(self, index):
        """パレットを左クリック: 現在選択中の項目(active_color_key)にその色を適用する"""
        if self.active_color_key is None:
            self.target_label_var.set("先に左の項目(背景など)を\nクリックしてください")
            return

        color_hex = self.shared_palette[index]
        key = self.active_color_key
        self.design[key] = color_hex
        self.current_swatch_labels[key].config(bg=color_hex)
        self._on_change()

    def _edit_shared_color(self, index):
        """パレットを右クリック: そのマスの色そのものを自由に編集する"""
        current = self.shared_palette[index]
        color = colorchooser.askcolor(color=current, title="パレットの色を編集", parent=self)
        if color[1]:
            self.shared_palette[index] = color[1]
            save_shared_palette(self.shared_palette)
            for widget in self.palette_container.winfo_children():
                widget.destroy()
            self._build_shared_palette(self.palette_container)
            # 編集したマスの色を、そのまま選択中の項目にも適用する
            self._apply_shared_color(index)

    def _reset_colors(self):
        self.shared_palette = list(DEFAULT_PALETTE)
        save_shared_palette(self.shared_palette)

        color_keys = ["bg_color", "text_color", "user_color", "original_color"]
        for key in color_keys:
            self.design[key] = DEFAULT_DESIGN[key]
            self.current_swatch_labels[key].config(bg=self.design[key])

        for widget in self.palette_container.winfo_children():
            widget.destroy()
        self._build_shared_palette(self.palette_container)

        self._on_change()

    # ---------- サイズ・透明度(スライダー+数値入力) ----------

    def _build_size_section(self):
        frame = ttk.LabelFrame(self, text="サイズ・透明度", padding=12)
        frame.pack(fill="x", padx=14, pady=6)

        self.scale_vars = {}
        self.entry_vars = {}
        self.style_vars = {}  # 太字・下線のBooleanVar
        self._style_toggle_buttons = {}

        # 全ての行(コメントサイズ/Userサイズ/透明度/角の丸み)を
        # 同じgridに配置することで、ラベル・ゲージ・数値の位置が
        # 完全に列で揃うようにする(pack単体だと行ごとに微妙な
        # 幅のズレが出やすいため)。
        # 列構成: [0]ラベル [1]B [2]U [3]ゲージ [4]数値

        slider_items = [
            ("font_size", "コメントサイズ", 10, 40, "comment_bold", "comment_underline"),
            ("user_font_size", "Userサイズ", 10, 40, "user_bold", "user_underline"),
        ]

        row_i = 0
        for key, label, vmin, vmax, bold_key, underline_key in slider_items:
            ttk.Label(frame, text=label, width=11, anchor="w").grid(
                row=row_i, column=0, sticky="w", pady=3,
            )

            bold_var = tk.BooleanVar(value=self.design[bold_key])
            self.style_vars[bold_key] = bold_var
            bold_btn = tk.Checkbutton(
                frame, text="B", variable=bold_var, indicatoron=False, width=2,
                font=("", 9, "bold"), selectcolor=self.cget("bg"),
                command=lambda k=bold_key: self._on_toggle_style(k),
            )
            bold_btn.grid(row=row_i, column=1, padx=(0, 1))
            self._style_toggle_buttons[bold_key] = bold_btn
            bold_btn.config(relief="sunken" if bold_var.get() else "raised")

            underline_var = tk.BooleanVar(value=self.design[underline_key])
            self.style_vars[underline_key] = underline_var
            underline_btn = tk.Checkbutton(
                frame, text="U", variable=underline_var, indicatoron=False, width=2,
                font=("", 9, "underline"), selectcolor=self.cget("bg"),
                command=lambda k=underline_key: self._on_toggle_style(k),
            )
            underline_btn.grid(row=row_i, column=2, padx=(0, 6))
            self._style_toggle_buttons[underline_key] = underline_btn
            underline_btn.config(relief="sunken" if underline_var.get() else "raised")

            var = tk.IntVar(value=self.design[key])
            self.scale_vars[key] = var
            scale = ttk.Scale(
                frame, from_=vmin, to=vmax, orient="horizontal", variable=var, length=180,
                command=lambda v, k=key: self._on_scale_dragged(k),
            )
            scale.grid(row=row_i, column=3, sticky="ew", padx=6)

            entry_var = tk.StringVar(value=str(self.design[key]))
            self.entry_vars[key] = entry_var
            entry = ttk.Entry(frame, textvariable=entry_var, width=4, justify="right")
            entry.grid(row=row_i, column=4, sticky="e")
            entry.bind("<Return>", lambda e, k=key, vmn=vmin, vmx=vmax: self._on_entry_changed(k, vmn, vmx))
            entry.bind("<FocusOut>", lambda e, k=key, vmn=vmin, vmx=vmax: self._on_entry_changed(k, vmn, vmx))

            row_i += 1

        # 透明度・角の丸みには B/U が無いが、列位置を揃えるため
        # 同じ列(3=ゲージ, 4=数値)にそのまま配置する
        plain_items = [
            ("bg_opacity", "背景の透明度", 0, 100),
            ("corner_radius", "角の丸み", 0, 24),
            ("max_lines", "表示行数", 1, 30),
        ]
        for key, label, vmin, vmax in plain_items:
            ttk.Label(frame, text=label, width=11, anchor="w").grid(
                row=row_i, column=0, sticky="w", pady=3,
            )

            var = tk.IntVar(value=self.design[key])
            self.scale_vars[key] = var
            scale = ttk.Scale(
                frame, from_=vmin, to=vmax, orient="horizontal", variable=var, length=180,
                command=lambda v, k=key: self._on_scale_dragged(k),
            )
            scale.grid(row=row_i, column=3, sticky="ew", padx=6)

            entry_var = tk.StringVar(value=str(self.design[key]))
            self.entry_vars[key] = entry_var
            entry = ttk.Entry(frame, textvariable=entry_var, width=4, justify="right")
            entry.grid(row=row_i, column=4, sticky="e")
            entry.bind("<Return>", lambda e, k=key, vmn=vmin, vmx=vmax: self._on_entry_changed(k, vmn, vmx))
            entry.bind("<FocusOut>", lambda e, k=key, vmn=vmin, vmx=vmax: self._on_entry_changed(k, vmn, vmx))

            row_i += 1

        # ユーザー名を独立した行にするかどうかの切り替え(3行レイアウト)。
        # スライダーではなく単純なON/OFFなので、専用のCheckbuttonを用意する。
        stacked_var = tk.BooleanVar(value=self.design.get("stacked_layout", False))
        self.style_vars["stacked_layout"] = stacked_var
        ttk.Checkbutton(
            frame, text="ユーザー名を独立した行にする(3行レイアウト)",
            variable=stacked_var, command=self._on_change,
        ).grid(row=row_i, column=0, columnspan=5, sticky="w", pady=(6, 0))
        row_i += 1

        # 原文(翻訳前のコメント)を表示するかどうかの切り替え。
        # 【重要】以前は、これを切り替える手段がメイン画面の
        # 「表示」メニュー内の字幕モード(翻訳のみ/原文+翻訳)しか無く、
        # ここで見つけにくかった。デザイン設定画面からも直接
        # 切り替えられるようにする。
        show_original_var = tk.BooleanVar(value=self.design.get("show_original", True))
        self.style_vars["show_original"] = show_original_var
        ttk.Checkbutton(
            frame, text="原文(翻訳前のコメント)も表示する",
            variable=show_original_var, command=self._on_change,
        ).grid(row=row_i, column=0, columnspan=5, sticky="w", pady=(2, 0))
        row_i += 1

        ttk.Button(frame, text="サイズ設定を初期値に戻す", command=self._reset_sizes).grid(
            row=row_i, column=0, columnspan=5, sticky="e", pady=(8, 0),
        )

    def _reset_sizes(self):
        for key in ("font_size", "user_font_size", "bg_opacity", "corner_radius", "max_lines"):
            self.design[key] = DEFAULT_DESIGN[key]
            self.scale_vars[key].set(self.design[key])
            self.entry_vars[key].set(str(self.design[key]))
        for key in ("comment_bold", "comment_underline", "user_bold", "user_underline",
                    "stacked_layout", "show_original"):
            self.design[key] = DEFAULT_DESIGN[key]
            self.style_vars[key].set(self.design[key])
        self._on_change()

    def _on_scale_dragged(self, key):
        if self._updating:
            return
        self._updating = True
        self.entry_vars[key].set(str(self.scale_vars[key].get()))
        self._updating = False
        self._on_change()

    def _on_entry_changed(self, key, vmin, vmax):
        if self._updating:
            return
        try:
            value = int(float(self.entry_vars[key].get()))
        except ValueError:
            value = self.design[key]
        value = max(vmin, min(vmax, value))

        self._updating = True
        self.scale_vars[key].set(value)
        self.entry_vars[key].set(str(value))
        self._updating = False
        self._on_change()

    # ---------- 変更反映 ----------

    def _on_toggle_style(self, key):
        """B/Uボタンが押された時、relief(枠のへこみ)を選択状態に合わせて切り替える"""
        is_on = self.style_vars[key].get()
        self._style_toggle_buttons[key].config(relief="sunken" if is_on else "raised")
        self._on_change()

    def _on_change(self):
        """つまみが操作されるたびに、design辞書を更新してCSSを再生成する"""
        self.design["font_family"] = self.font_var.get()
        for key, var in self.scale_vars.items():
            self.design[key] = var.get()
        for key, var in self.style_vars.items():
            self.design[key] = var.get()

        save_design(self.design)
        self._update_preview()

    # ---------- プレビュー(角丸対応のCanvasベース) ----------

    def _build_preview(self):
        """
        実際のオーバーレイ用ブラウザを開くのではなく、
        固定のサンプルコメントを使って、今の設定でどう見えるかを
        このウィンドウの中に常時表示する。

        Tkinter標準のLabel/Frameには角丸の概念が無いため、
        Canvasに角丸の四角形を自前で描画し、その上にテキストを
        重ねる形で、CSSのborder-radiusに近い見た目を再現している。
        """
        outer = ttk.LabelFrame(self, text="プレビュー(サンプルコメント)", padding=8)
        outer.pack(fill="x", padx=14, pady=6)

        # プレビューの背景は、実際のOBS上での見え方に近い、
        # ゲーム画面を想定した中間的な明るさの色にしておく
        self.preview_bg_color = "#3a3a3a"
        self.preview_canvas = tk.Canvas(
            outer, bg=self.preview_bg_color, height=100, highlightthickness=0,
        )
        self.preview_canvas.pack(fill="x")

        # winfo_width()は、レイアウトの再計算が完了する前に呼ぶと
        # 古い/不正確な値を返すことがあり、それが原因で角丸の
        # 四角形が範囲外にはみ出して見える不具合が起きていた。
        # <Configure>イベント(実際にウィジェットのサイズが確定・変化した
        # 瞬間に発火する)をきっかけに再描画することで、常に正しい
        # 幅を使って描画されるようにする。
        self.preview_canvas.bind("<Configure>", lambda e: self._update_preview())

    def _set_preview_canvas_height(self, canvas, height):
        """
        プレビューCanvasの高さを変更する。
        【重要】このCanvasの<Configure>イベントに_update_preview()を
        バインドしているため、無条件にcanvas.config(height=...)を呼ぶと、
        高さの変更が新たな<Configure>イベントを誘発し、
        _update_preview()が再帰的に呼ばれてしまう可能性がある
        (実際には値が収束して1往復で止まるはずだが、念のため
        高さが実際に変わる場合だけ更新するようにして、無駄な
        再描画・潜在的なちらつきを防いでいる)。
        """
        if getattr(self, "_preview_canvas_height", None) == height:
            return
        self._preview_canvas_height = height
        canvas.config(height=height)

    def _draw_rounded_rect(self, canvas, x1, y1, x2, y2, radius, **kwargs):
        """Canvas上に角丸の四角形を描画するヘルパー"""
        points = [
            x1 + radius, y1,
            x2 - radius, y1,
            x2, y1,
            x2, y1 + radius,
            x2, y2 - radius,
            x2, y2,
            x2 - radius, y2,
            x1 + radius, y2,
            x1, y2,
            x1, y2 - radius,
            x1, y1 + radius,
            x1, y1,
        ]
        return canvas.create_polygon(points, smooth=True, **kwargs)

    def _update_preview(self):
        """design辞書の現在値をもとに、プレビュー表示を更新する"""
        design = self.design
        canvas = self.preview_canvas
        canvas.delete("all")

        # 背景の半透明を、Tkinterでは直接再現できないため、
        # プレビュー背景色と、設定した背景色・透明度を計算で合成し、
        # それっぽく見せる(簡易的な模擬)
        bg_r, bg_g, bg_b = _hex_to_rgb(self.preview_bg_color)
        fg_r, fg_g, fg_b = _hex_to_rgb(design["bg_color"])
        alpha = design["bg_opacity"] / 100.0
        mixed_r = int(fg_r * alpha + bg_r * (1 - alpha))
        mixed_g = int(fg_g * alpha + bg_g * (1 - alpha))
        mixed_b = int(fg_b * alpha + bg_b * (1 - alpha))
        mixed_color = f"#{mixed_r:02x}{mixed_g:02x}{mixed_b:02x}"

        font_family = design["font_family"]
        font_size = max(int(design["font_size"] * 0.8), 8)
        user_font_size = max(int(design.get("user_font_size", design["font_size"]) * 0.8), 8)
        original_font_size = max(int((design["font_size"] - 4) * 0.8), 7)
        radius = design["corner_radius"]

        # 太字・下線はTkinterのfontタプルだけでは同時指定しづらいため、
        # tkinter.font.Fontオブジェクトを都度組み立てて使う
        import tkinter.font as tkfont

        user_font = tkfont.Font(
            family=font_family, size=user_font_size,
            weight="bold" if design.get("user_bold", True) else "normal",
            underline=design.get("user_underline", False),
        )
        comment_font = tkfont.Font(
            family=font_family, size=font_size,
            weight="bold" if design.get("comment_bold", False) else "normal",
            underline=design.get("comment_underline", False),
        )

        canvas_width = canvas.winfo_width() or 400

        stacked_layout = design.get("stacked_layout", False)
        show_original = design.get("show_original", True)

        # 【重要】以前はここで常に「ユーザー名+本文が同じ行、原文はその下」
        # という決め打ちのレイアウトで描画しており、stacked_layout・
        # show_originalの設定を変えても、このプレビューだけは見た目が
        # 一切変わらないという不具合があった(実際のオーバーレイのJS側は
        # ちゃんと設定を反映していたが、このCanvasプレビューだけ
        # 追従できていなかった)。設定に応じて描画するテキスト行を
        # 組み立て直すようにする。

        USER_TEXT = "user_92"
        COMMENT_TEXT = "こんにちは、今日も配信いいね"
        ORIGINAL_TEXT = "Hello! nice stream today"

        original_font = (font_family, original_font_size)

        if stacked_layout:
            # 3行レイアウト: ユーザー名 / 原文(表示する場合) / 翻訳文
            lines = [("user", USER_TEXT)]
            if show_original:
                lines.append(("original", ORIGINAL_TEXT))
            lines.append(("comment", COMMENT_TEXT))

            line_height = 24
            box_height = 20 + line_height * len(lines)
            self._draw_rounded_rect(
                canvas, 10, 12, canvas_width - 10, 12 + box_height, radius,
                fill=mixed_color, outline="",
            )

            y = 12 + 18
            for kind, text in lines:
                if kind == "user":
                    canvas.create_text(
                        22, y, anchor="w", text=text,
                        fill=design["user_color"], font=user_font,
                    )
                elif kind == "original":
                    canvas.create_text(
                        22, y, anchor="w", text=text,
                        fill=design["original_color"], font=original_font,
                    )
                else:
                    canvas.create_text(
                        22, y, anchor="w", text=text,
                        fill=design["text_color"], font=comment_font,
                    )
                y += line_height

            self._set_preview_canvas_height(canvas, box_height + 24)
        else:
            # 従来レイアウト: ユーザー名+翻訳文が同じ行、原文はその下(表示する場合)
            box_height = 68 if show_original else 40
            self._draw_rounded_rect(
                canvas, 10, 12, canvas_width - 10, 12 + box_height, radius,
                fill=mixed_color, outline="",
            )

            user_text_id = canvas.create_text(
                22, 30, anchor="w", text=USER_TEXT,
                fill=design["user_color"], font=user_font,
            )
            user_bbox = canvas.bbox(user_text_id)
            comment_x = (user_bbox[2] + 8) if user_bbox else 100

            canvas.create_text(
                comment_x, 30, anchor="w", text=COMMENT_TEXT,
                fill=design["text_color"], font=comment_font,
            )

            if show_original:
                canvas.create_text(
                    22, 58, anchor="w", text=ORIGINAL_TEXT,
                    fill=design["original_color"], font=original_font,
                )

            self._set_preview_canvas_height(canvas, box_height + 24)

    # ---------- フッター ----------

    def _build_footer(self):
        frame = ttk.Frame(self, padding=(14, 10))
        frame.pack(fill="x", side="bottom")

        ttk.Button(frame, text="保存して閉じる", command=self._save_and_close).pack(side="right")

    def _save_and_close(self):
        """
        【重要】この画面自体は、つまみを操作するたびに自動保存される
        設計になっているため、本来この処理を経なくても設定は
        既に保存済みのはず。それでも明示的な「保存して閉じる」ボタンを
        用意しているのは、閉じる操作のついでに、念のため現在の
        入力欄・スライダーの状態を design に反映してから保存し直す
        ことで、「閉じたつもりが、直前の操作が反映されていなかった」
        というすれ違いが起きないようにするため。
        """
        self._on_change()
        self.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    root.withdraw()
    win = OverlayDesignWindow(root)
    win.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
