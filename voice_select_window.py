# -*- coding: utf-8 -*-
"""
VOICEVOX キャラクター検索/選択画面

【機能】
- 性別・ジャンルタグをチェックボックスで複数選択して絞り込み(AND検索)
- フリーワード検索(名前の一部で絞り込み)
- 該当件数の表示、絞込みリセット
- 一覧はアイコン付きカード形式(お気に入り☆、試聴🔊ボタン付き)
- カードをクリックすると、そのキャラの「スタイル一覧」
  (ノーマル/あまあま/ささやき等)がサブウィンドウで選べる
- お気に入り登録した内容は character_meta.json に書き戻す

【前提】
- 同じフォルダに character_meta.json と character_icons/ があること
- 試聴機能を使うには VOICEVOX エンジンが起動していること
  (play_sample.py を利用する。起動していなくても画面表示自体は動作する)

【使い方】
python voice_select_window.py
"""

import json
import os
import tkinter as tk
from tkinter import ttk

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from resource_path import resource_path, writable_path

META_PATH = "character_meta.json"
ICON_DIR = "character_icons"
ICON_SIZE = 40  # 一覧に出すアイコンのサイズ(px)

GENDER_OPTIONS = ["男性", "女性", "中性"]


class VoiceSelectWindow(tk.Toplevel):
    """VOICEVOXキャラクター検索/選択画面(別ウィンドウ)"""

    def __init__(self, master, on_select=None):
        super().__init__(master)
        self.title("VOICEVOX キャラクター選択")
        self.geometry("1000x600")
        self.minsize(700, 480)

        # on_select: ユーザーがキャラ+スタイルを最終決定した時に呼ばれるコールバック
        # on_select(style_id, full_label, icon_path) の形で呼ばれる想定
        self.on_select = on_select

        self.character_meta = self._load_meta()
        self.icon_cache = {}  # uuid -> PhotoImage のキャッシュ(毎回読み込み直さない)

        self.gender_vars = {g: tk.BooleanVar(value=False) for g in GENDER_OPTIONS}
        self.genre_vars = {}  # genre名 -> BooleanVar (キャラデータから動的に作る)
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *_: self._refresh_list())

        self._build_filter_area()
        self._build_search_bar()
        self._build_list_area()
        self._build_footer()

        self._refresh_list()

    # ---------- データ読み込み ----------

    def _load_meta(self):
        """
        character_meta.json を読み込む。

        【重要】このファイルは「お気に入り登録」でユーザーが書き換える
        対象でもあるため、読み込み専用の同梱データ置き場(_internal等)
        ではなく、書き込み可能な場所(exeと同じフォルダ)を正とする。

        exeの隣にまだファイルが無い場合(初回起動時)は、同梱されている
        雛形データ(resource_path側)を、書き込み可能な場所にコピーして
        から使う。これにより、2回目以降の起動では、ユーザーが編集した
        内容がそのまま引き継がれる。
        """
        target_path = writable_path(META_PATH)

        if not os.path.exists(target_path):
            bundled_path = resource_path(META_PATH)
            if os.path.exists(bundled_path):
                with open(bundled_path, "r", encoding="utf-8") as f:
                    initial_data = f.read()
                with open(target_path, "w", encoding="utf-8") as f:
                    f.write(initial_data)
            else:
                return {}

        with open(target_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _save_meta(self):
        with open(writable_path(META_PATH), "w", encoding="utf-8") as f:
            json.dump(self.character_meta, f, ensure_ascii=False, indent=2)

    def _get_icon(self, uuid, icon_file):
        """アイコン画像をPhotoImageとして取得(キャッシュ付き)"""
        if uuid in self.icon_cache:
            return self.icon_cache[uuid]

        if not icon_file:
            self.icon_cache[uuid] = None
            return None

        # アイコン画像自体は、ユーザーが書き換えることのない
        # 同梱データなので、resource_path(読み込み専用の場所)でよい
        path = resource_path(os.path.join(ICON_DIR, icon_file))
        if not os.path.exists(path):
            self.icon_cache[uuid] = None
            return None

        if PIL_AVAILABLE:
            img = Image.open(path).convert("RGBA").resize((ICON_SIZE, ICON_SIZE))
            photo = ImageTk.PhotoImage(img)
        else:
            # Pillowが無い環境でも最低限pngだけは表示できるようフォールバック
            photo = tk.PhotoImage(file=path)

        self.icon_cache[uuid] = photo
        return photo

    # ---------- UI構築 ----------

    def _build_filter_area(self):
        frame = ttk.Frame(self, padding=(12, 10))
        frame.pack(fill="x")

        # 性別チェックボックス
        gender_frame = ttk.LabelFrame(frame, text="性別")
        gender_frame.pack(side="left", padx=(0, 16), fill="y")
        for g in GENDER_OPTIONS:
            cb = ttk.Checkbutton(
                gender_frame, text=g, variable=self.gender_vars[g],
                command=self._refresh_list,
            )
            cb.pack(side="left", padx=6, pady=6)

        # ジャンルタグチェックボックス(character_metaから動的に収集)
        genre_frame = ttk.LabelFrame(frame, text="ジャンル")
        genre_frame.pack(side="left", fill="both", expand=True)

        all_genres = set()
        for entry in self.character_meta.values():
            all_genres.update(entry.get("genre_tags", []))

        row = ttk.Frame(genre_frame)
        row.pack(fill="x", padx=4, pady=4)
        for i, genre in enumerate(sorted(all_genres)):
            var = tk.BooleanVar(value=False)
            self.genre_vars[genre] = var
            cb = ttk.Checkbutton(row, text=genre, variable=var, command=self._refresh_list)
            cb.grid(row=i // 6, column=i % 6, sticky="w", padx=4, pady=2)

    def _build_search_bar(self):
        frame = ttk.Frame(self, padding=(12, 4))
        frame.pack(fill="x")

        ttk.Label(frame, text="🔍").pack(side="left")
        entry = ttk.Entry(frame, textvariable=self.search_var)
        entry.pack(side="left", fill="x", expand=True, padx=6)

        self.count_label = ttk.Label(frame, text="")
        self.count_label.pack(side="left", padx=8)

        reset_btn = ttk.Button(frame, text="絞込みリセット", command=self._reset_filters)
        reset_btn.pack(side="left")

    def _build_list_area(self):
        container = ttk.Frame(self, padding=(12, 4))
        container.pack(fill="both", expand=True)

        canvas = tk.Canvas(container, highlightthickness=0)
        scrollbar = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        self.list_frame = ttk.Frame(canvas)

        self._configure_after_id = None
        self.list_frame.bind("<Configure>", self._on_list_frame_configure)
        canvas.create_window((0, 0), window=self.list_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        self.canvas = canvas
        self._bind_mousewheel(canvas)

    def _on_list_frame_configure(self, event):
        """
        一覧のサイズが変わった時にscrollregionを更新する。
        ウィンドウをドラッグでリサイズしている最中は、この処理が
        1秒間に何十回も呼ばれてしまい、その都度 canvas.bbox("all")
        (全ウィジェットの範囲を再計算する、比較的重い処理)を
        実行すると、リサイズ操作自体がカクつく原因になる。
        そのため、操作が一瞬止まった時にだけ実際の再計算を行う
        (デバウンス)ようにしている。
        """
        if self._configure_after_id is not None:
            self.after_cancel(self._configure_after_id)
        self._configure_after_id = self.after(120, self._apply_scrollregion)

    def _apply_scrollregion(self):
        self._configure_after_id = None
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))

    def _bind_mousewheel(self, canvas):
        """
        マウスホイールでの一覧スクロールに対応する。
        Windows/Macと、Linux(Button-4/5方式)の両方に対応しておく。
        マウスがこのウィンドウの上にある時だけ効くようにする
        (他のウィンドウのスクロールに干渉しないため)。
        """
        def _on_wheel_windows(event):
            canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

        def _on_wheel_linux_up(event):
            canvas.yview_scroll(-1, "units")

        def _on_wheel_linux_down(event):
            canvas.yview_scroll(1, "units")

        def _bind_all(event):
            canvas.bind_all("<MouseWheel>", _on_wheel_windows)
            canvas.bind_all("<Button-4>", _on_wheel_linux_up)
            canvas.bind_all("<Button-5>", _on_wheel_linux_down)

        def _unbind_all(event):
            canvas.unbind_all("<MouseWheel>")
            canvas.unbind_all("<Button-4>")
            canvas.unbind_all("<Button-5>")

        # ウィンドウにカーソルが入っている間だけホイールを有効化する
        canvas.bind("<Enter>", _bind_all)
        canvas.bind("<Leave>", _unbind_all)

    def _build_footer(self):
        frame = ttk.Frame(self, padding=(12, 8))
        frame.pack(fill="x")
        ttk.Label(
            frame,
            text="☆をクリックでお気に入り登録。名前をクリックすると声のスタイルを選べます。",
            foreground="gray",
        ).pack(side="left")
        ttk.Button(frame, text="閉じる", command=self.destroy).pack(side="right")

    # ---------- 絞り込みロジック ----------

    def _reset_filters(self):
        for var in self.gender_vars.values():
            var.set(False)
        for var in self.genre_vars.values():
            var.set(False)
        self.search_var.set("")
        self._refresh_list()

    def _matches_filter(self, entry):
        # 性別フィルター(チェックが1つも無ければ全通過、あれば選ばれたものだけ)
        checked_genders = [g for g, v in self.gender_vars.items() if v.get()]
        if checked_genders and entry.get("gender") not in checked_genders:
            return False

        # ジャンルフィルター(AND条件: チェックされた全タグを含むものだけ)
        checked_genres = [g for g, v in self.genre_vars.items() if v.get()]
        entry_genres = set(entry.get("genre_tags", []))
        if checked_genres and not all(g in entry_genres for g in checked_genres):
            return False

        # フリーワード検索
        keyword = self.search_var.get().strip()
        if keyword and keyword not in entry.get("display_name", ""):
            return False

        return True

    def _refresh_list(self):
        for widget in self.list_frame.winfo_children():
            widget.destroy()

        matched = [
            (uuid, entry) for uuid, entry in self.character_meta.items()
            if self._matches_filter(entry)
        ]

        self.count_label.config(text=f"{len(matched)}件該当")

        for i, (uuid, entry) in enumerate(matched):
            self._build_card(self.list_frame, uuid, entry, row=i // 3, col=i % 3)

        for c in range(3):
            self.list_frame.columnconfigure(c, weight=1)

    def _build_card(self, parent, uuid, entry, row, col):
        card = ttk.Frame(parent, padding=8, relief="groove", borderwidth=1)
        card.grid(row=row, column=col, padx=6, pady=6, sticky="ew")

        # name/genre列(column=1)を伸縮させ、☆と🔊(column=2,3)を
        # 常にカードの右端に揃える。これにより、名前の長さが
        # バラバラでも☆🔊の位置がガタつかず、右揃えで統一される。
        card.columnconfigure(1, weight=1)

        icon = self._get_icon(uuid, entry.get("icon_file"))
        icon_label = ttk.Label(card, image=icon) if icon else ttk.Label(card, text="🎤", width=4)
        icon_label.grid(row=0, column=0, rowspan=2, padx=(0, 8))

        name_label = ttk.Label(
            card, text=entry["display_name"], font=("", 11, "bold"), cursor="hand2",
        )
        name_label.grid(row=0, column=1, sticky="w")
        name_label.bind("<Button-1>", lambda e, u=uuid: self._open_style_picker(u))

        genre_text = " / ".join(entry.get("genre_tags", []))
        ttk.Label(card, text=genre_text, foreground="gray").grid(row=1, column=1, sticky="w")

        star_var = tk.StringVar(value="★" if entry.get("is_favorite") else "☆")
        star_btn = ttk.Button(
            card, textvariable=star_var, width=2,
            command=lambda u=uuid, sv=star_var: self._toggle_favorite(u, sv),
        )
        star_btn.grid(row=0, column=2, rowspan=2, padx=4, sticky="e")

        # 試聴ボタン: 番号(🔊1 / 🔊2)で「次に再生されるのはどちらか」を示す。
        # クリックするたびに交互に切り替わる。同じものをもう一度聞きたい
        # 場合はダブルクリックで対応する。
        play_label_var = tk.StringVar(value="🔊1")
        play_btn = ttk.Button(
            card, textvariable=play_label_var, width=3,
            command=lambda u=uuid, lv=play_label_var: self._play_sample(u, lv),
        )
        play_btn.grid(row=0, column=3, rowspan=2, padx=(0, 4), sticky="e")
        # ダブルクリック: 直前に再生したのと同じサンプルをもう一度再生する
        play_btn.bind(
            "<Double-Button-1>",
            lambda e, u=uuid, lv=play_label_var: self._play_sample(u, lv, repeat_last=True),
        )

    def _toggle_favorite(self, uuid, star_var):
        entry = self.character_meta[uuid]
        entry["is_favorite"] = not entry.get("is_favorite", False)
        star_var.set("★" if entry["is_favorite"] else "☆")
        self._save_meta()

    def _play_sample(self, uuid, play_label_var=None, repeat_last=False):
        entry = self.character_meta[uuid]
        if not entry.get("styles"):
            return
        style_id = entry["styles"][0]["style_id"]

        try:
            from play_sample import play_sample_toggle, _toggle_state

            if repeat_last:
                # ダブルクリック時は「直前に再生したのと同じ番号」を、
                # トグルせずにもう一度再生したいので、一時的に巻き戻す
                current = _toggle_state.get(style_id, 0)
                _toggle_state[style_id] = 1 - current  # 直前に再生した側に戻す

            played_index = play_sample_toggle(style_id=style_id, display_name=entry["display_name"])

            if play_label_var is not None:
                # 次に再生される番号(1-indexedで表示)をボタンに反映
                next_index = 1 - played_index
                play_label_var.set(f"🔊{next_index + 1}")
        except Exception as e:
            print(f"試聴に失敗しました(VOICEVOXが起動していない可能性があります): {e}")

    def _open_style_picker(self, uuid):
        entry = self.character_meta[uuid]
        StylePickerDialog(self, entry, on_confirm=self._on_style_confirmed, uuid=uuid)

    def _on_style_confirmed(self, uuid, style_id, style_name):
        entry = self.character_meta[uuid]
        full_label = f"{entry['display_name']}({style_name})"
        icon_path = resource_path(os.path.join(ICON_DIR, entry.get("icon_file", "")))
        if self.on_select:
            self.on_select(style_id, full_label, icon_path)
        # 検索画面自体は閉じない(引き続き他のキャラも見比べられるように)。
        # 閉じるのはStylePickerDialog側の役目(_confirm内で既に行っている)。


class StylePickerDialog(tk.Toplevel):
    """1人のキャラを選んだ後に出す、スタイル(ノーマル/ささやき等)選択のサブ画面"""

    def __init__(self, master, entry, on_confirm, uuid):
        super().__init__(master)
        self.title(f"{entry['display_name']} のスタイル選択")
        self.geometry("300x360")
        self.on_confirm = on_confirm
        self.uuid = uuid

        ttk.Label(
            self, text=f"{entry['display_name']}", font=("", 13, "bold"),
        ).pack(pady=(12, 4))
        ttk.Label(self, text="声のスタイルを選んでください", foreground="gray").pack()

        list_frame = ttk.Frame(self, padding=10)
        list_frame.pack(fill="both", expand=True)

        for style in entry.get("styles", []):
            btn = ttk.Button(
                list_frame,
                text=style["style_name"],
                command=lambda s=style: self._confirm(s),
            )
            btn.pack(fill="x", pady=3)

    def _confirm(self, style):
        self.on_confirm(self.uuid, style["style_id"], style["style_name"])
        self.destroy()


if __name__ == "__main__":
    # 単体動作確認用
    root = tk.Tk()
    root.withdraw()  # メインウィンドウは使わないので隠す

    def on_select(style_id, full_label, icon_path):
        print(f"選択されました: style_id={style_id}, label={full_label}, icon={icon_path}")

    win = VoiceSelectWindow(root, on_select=on_select)
    win.protocol("WM_DELETE_WINDOW", root.destroy)
    root.mainloop()
