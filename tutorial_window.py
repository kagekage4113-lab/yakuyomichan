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

import os
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from app_settings import load_app_settings, save_app_settings

if os.name == "nt":
    import ctypes
    from ctypes import wintypes

# メニューバーの並び順・ラベル文字列(main_window.py の _build_menu で
# add_cascade した順、0始まり)。「② トークンを設定する」
# 「③ 自動起動設定を確認する」のスポットライトで、メニューバー自体の
# 項目を狙うために使う。Win32 APIでの厳密な位置取得に失敗した場合は、
# この文字列をフォントで実測して、おおよその位置を推定するのにも使う。
# 【重要】メニューの並び順・ラベル文言を変更した場合は、ここも合わせて直すこと。
MENU_LABELS = ["ファイル", "配信", "VOICEVOX", "表示", "ヘルプ"]
# 【重要】メニューの並び順を変更した場合は、ここも合わせて直すこと。
MENU_INDEX_FILE = 0     # 「ファイル」
MENU_INDEX_STREAM = 1   # 「配信」

TUTORIAL_STEPS = [
    {
        "title": "① プラットフォームを選ぶ",
        "text": "左上のプルダウンから、監視したい配信サービスを選びます。\n"
                "Twitch / YouTube / 両方、から選べます。",
        "target_attr": "platform_var_widget",
        "target_menu_index": None,
    },
    {
        "title": "② トークンを設定する",
        "text": "メニューの「配信」→「トークン設定」から、\n"
                "Twitch・YouTubeの認証情報を入力してください。\n"
                "詳しい取得方法は、ヘルプメニューの各種ガイドをご覧ください。",
        "target_attr": None,
        # メニューが閉じている状態でも、Windowsのメニューバー自体の
        # 座標をGetMenuItemRect()で取得してスポットライトを当てる
        "target_menu_index": MENU_INDEX_STREAM,
    },
    {
        "title": "③ 自動起動設定を確認する",
        "text": "メニューの「ファイル」→「自動起動設定」から、\n"
                "VOICEVOX・LMStudioを自動で起動するかどうかを設定できます。\n"
                "インストーラーを使った場合は、既に設定済みのことが多いです。",
        "target_attr": None,
        "target_menu_index": MENU_INDEX_FILE,
    },
]

# ---------- スポットライト演出まわりの設定 ----------
# 対象ウィジェット以外を薄暗くし、対象部分だけくり抜いて明るいまま見せる、
# よくあるチュートリアルの「スポットライト」演出。
# 実装方法: 対象ウィジェットの上下左右を囲む4枚の暗い半透明ウィンドウを
# 敷き詰め、対象部分だけ意図的に何も置かない(=隙間から地の画面がそのまま
# 明るく見える)ことで、擬似的に「穴あき」の効果を作っている。
SPOTLIGHT_PADDING = 6          # 対象ウィジェットの周囲に余白を持たせる(px)
MENU_BAR_HEIGHT_ESTIMATE = 20  # メニューバー全体をハイライトする際の高さの目安(px)
MENU_ITEM_PADDING_X = 10       # メニュー項目1つあたりの左右合計の推定余白(px)
HIGHLIGHT_DISPLAY_DELAY_MS = 400  # ウィンドウ表示が確定するのを待つための遅延時間(ms)
ACCENT_BORDER_COLOR = "#ffd54a"    # 対象を囲む縁取りの色(明るい黄色)
ACCENT_BORDER_THICKNESS = 3        # 縁取りの太さ(px)


def _get_menu_bar_item_rect(root, item_index):
    """
    メニューバーで、上から数えて item_index 番目(0始まり、add_cascadeした順)の
    トップレベル項目(例:「ファイル」「配信」など)の、画面上での矩形
    (x, y, width, height)を取得する。

    【なぜWin32 APIを直接呼ぶ必要があるか】
    Tkinterには、メニューバー項目自体の座標を取得する標準APIが無い。
    メニューが開いていない間、トップレベルの項目(「ファイル」等の文字)は
    OSのネイティブなメニューバー描画の一部でしかなく、Tkのウィジェットとして
    は存在しないため、winfo_rootx() 等では取得できない。
    そのため、Win32 APIの GetMenuItemRect() を ctypes 経由で直接呼び出し、
    スクリーン座標系での矩形を取得している。本アプリはWindows専用の
    配布物のため、Windows専用の実装でも問題ない。
    取得に失敗した場合(該当インデックスが存在しない、他OSで実行された、等)は
    Noneを返す。呼び出し側は、Noneの場合はスポットライト無しで
    テキスト説明のみにフォールバックする。
    """
    if os.name != "nt":
        return None
    try:
        user32 = ctypes.windll.user32
        user32.GetMenu.argtypes = [wintypes.HWND]
        user32.GetMenu.restype = wintypes.HMENU
        user32.GetMenuItemRect.argtypes = [
            wintypes.HWND, wintypes.HMENU, wintypes.UINT, ctypes.POINTER(wintypes.RECT),
        ]
        user32.GetMenuItemRect.restype = wintypes.BOOL

        hwnd = root.winfo_id()
        hmenu = user32.GetMenu(hwnd)
        if not hmenu:
            return None

        rect = wintypes.RECT()
        if not user32.GetMenuItemRect(hwnd, hmenu, item_index, ctypes.byref(rect)):
            return None

        return (rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
    except Exception:
        return None


class TutorialWindow(tk.Toplevel):
    def __init__(self, master):
        super().__init__(master)
        self.master_app = master
        self.title("はじめに")
        self.geometry("420x320")
        self.resizable(False, False)
        self.transient(master)

        # 【重要】強調表示用の縁取りウィンドウは常に最前面(topmost)で
        # 出すため、チュートリアル本体のダイアログもtopmostにしておかないと、
        # 縁取りの後ろに隠れて「次へ」ボタン等が押せなくなってしまう。
        # 【重要・Windowsのフォーカス制限対策】アプリ起動直後など、
        # ユーザーがまだ一度もクリック操作をしていないタイミングでは、
        # Windowsがプログラム側からの最前面化を制限することがあるため、
        # 一度OFFにしてから改めてONにする(定番の回避策)。
        self.attributes("-topmost", True)
        self.attributes("-topmost", False)
        self.attributes("-topmost", True)

        # ダイアログの初期位置を、メイン画面の右下寄りに調整する。
        # 何も指定しないとOS任せの位置(だいたい画面中央や左上寄り)になり、
        # 今回ハイライトしたい「左上のプラットフォーム選択」等と、
        # ダイアログ自体が重なって見づらくなることがあったため。
        self._position_near_master()

        self.current_step = 0
        self._highlight_widget = None
        self._original_relief = None
        self._spotlight_windows = []
        self._current_target_widget = None
        self._current_target_menu_index = None

        self._build_ui()

        # 【重要】チュートリアルが表示される最初の瞬間は、メイン画面側の
        # 描画がまだ完全に確定していないことがあり、そのまま初回の
        # ハイライト位置を計算すると、ズレた位置になることがあった。
        # 最初の _show_step(0) の前に、念のためメイン画面の描画を
        # 一度確実に確定させておく。
        # (この時点ではまだ <Configure> の監視バインドを行っていないため、
        # ここで update() が内部的に Configure イベントを誘発したとしても、
        # _on_master_configure が呼ばれて再帰的にズレる、という心配はない)
        try:
            self.master_app.update()
        except tk.TclError:
            pass

        self._show_step(0)

        # チュートリアル表示中に、万一メイン画面が動かされた/リサイズされた
        # 場合でも、スポットライトの位置がズレたままにならないよう、
        # メイン画面のConfigureイベントを監視して追従させる。
        # 【重要】_show_step(0) 内部のハイライト表示自体は after(30, ...) で
        # 少し遅れて実行されるため、このバインドを _show_step(0) の直後に
        # 行っても、まだそのハイライトは実行されていない。バインドの
        # タイミングが早すぎて、初回のハイライト計算中に Configure が
        # 誤発火する心配はない。
        self._configure_binding = self.master_app.bind(
            "<Configure>", self._on_master_configure, add="+",
        )
        self.bind("<Destroy>", self._on_destroy)

        # 【重要・重大バグ修正】
        # 以前は、ウィンドウ右上の「×」ボタンで閉じた場合、Tkinterの
        # デフォルト動作でそのままdestroy()が呼ばれ、_close()を
        # 経由しないまま終了していた。そのため、スポットライト用の
        # 暗幕オーバーレイ(_spotlight_windows)が後片付けされず、
        # 画面全体が暗幕で覆われたまま操作不能になり、タスクバーから
        # 強制終了するしかなくなる、という重大な不具合につながっていた。
        # ウィンドウを閉じる手段(×ボタン、Alt+F4等)に関わらず、
        # 必ず _close() を経由させることで、暗幕が確実に片付くようにする。
        self.protocol("WM_DELETE_WINDOW", self._close)

        # 【重要・不具合対策】
        # スポットライトの暗幕は「常に最前面(topmost)」に固定しているため、
        # 本アプリと無関係な、全く別のウィンドウ・アプリに切り替えても、
        # 暗幕だけがそのまま画面に張り付いて残ってしまい、その裏側では
        # マウス操作を受け付けなくなる、という不具合が確認された。
        # 対策として、定期的に「今アクティブなウィンドウ」をWin32 APIで
        # チェックし、本アプリ(メイン画面 or チュートリアル自身)以外が
        # アクティブになったら、暗幕を一時的に隠す(本アプリに戻ったら
        # 再表示する)監視ループを開始する。
        self._foreground_watch_job = None
        self._spotlight_hidden = False
        self._start_foreground_watch()

    def _start_foreground_watch(self):
        if os.name != "nt":
            return  # Windows以外では監視APIが無いため何もしない
        self._foreground_watch_job = self.after(300, self._check_foreground_and_toggle_spotlight)

    def _check_foreground_and_toggle_spotlight(self):
        """
        現在アクティブな(前面にある)ウィンドウが、本アプリ自身
        (メイン画面 or チュートリアルダイアログ)かどうかを調べ、
        違えば暗幕を隠し、本アプリに戻っていれば暗幕を再表示する。
        300msごとに自分自身を再スケジュールし、チュートリアルが
        開いている間ずっと繰り返す。
        """
        try:
            user32 = ctypes.windll.user32
            fg_hwnd = user32.GetForegroundWindow()
            own_hwnds = {self.winfo_id(), self.master_app.winfo_id()}
            is_ours = fg_hwnd in own_hwnds
        except Exception:
            # 判定自体に失敗した場合は、誤って隠し続けて操作不能にする
            # 事故を避けるため、「隠さない(=これまで通り表示する)」を
            # 安全側のデフォルトとする。
            is_ours = True

        if is_ours and self._spotlight_hidden:
            self._reveal_spotlight_windows()
        elif not is_ours and not self._spotlight_hidden:
            self._hide_spotlight_windows()

        self._foreground_watch_job = self.after(300, self._check_foreground_and_toggle_spotlight)

    def _hide_spotlight_windows(self):
        self._spotlight_hidden = True
        for win in self._spotlight_windows:
            try:
                win.withdraw()
            except tk.TclError:
                pass

    def _reveal_spotlight_windows(self):
        self._spotlight_hidden = False
        for win in self._spotlight_windows:
            try:
                win.deiconify()
            except tk.TclError:
                pass

    def _position_near_master(self):
        try:
            self.master_app.update_idletasks()
            mx = self.master_app.winfo_rootx()
            my = self.master_app.winfo_rooty()
            mw = self.master_app.winfo_width()
            mh = self.master_app.winfo_height()
            x = mx + mw - 440
            y = my + mh - 340
            self.geometry(f"420x320+{max(x, 0)}+{max(y, 0)}")
        except tk.TclError:
            pass  # 取得に失敗した場合は、OS任せの初期位置のままにする

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

        self.back_btn = ttk.Button(footer, text="戻る", command=self._prev_step)
        self.back_btn.pack(side="right", padx=(0, 8))

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

        # 最初のステップでは「戻る」を押せないようにする
        if index == 0:
            self.back_btn.state(["disabled"])
        else:
            self.back_btn.state(["!disabled"])

        # 対象ウィジェットがあれば、枠を黄色くハイライトしつつ、
        # 周囲を暗くするスポットライト演出も重ねて表示する。
        # 対象がメニューバー項目(トークン設定/自動起動設定のように、
        # 直接参照できるウィジェットが無いもの)の場合は、
        # Windowsのメニューバー自体の座標を取得してスポットライトを当てる。
        target_attr = step.get("target_attr")
        target_menu_index = step.get("target_menu_index")
        self._current_target_widget = None
        self._current_target_menu_index = None

        if target_attr and hasattr(self.master_app, target_attr):
            widget = getattr(self.master_app, target_attr)
            self._highlight_widget = widget
            self._current_target_widget = widget
            try:
                self._original_relief = widget.cget("relief")
                widget.config(relief="solid", borderwidth=2)
            except tk.TclError:
                pass  # ハイライトできないウィジェット種別の場合は諦める(致命的ではない)
            # 【重要】ウィンドウが表示されてから、実際にOS側で
            # 完全に描画・アクティブ化されるまでには、わずかながら
            # 時間差がある。その間に座標取得やtopmost化を行うと、
            # 位置がズレたり、表示されたと思ったら消えたりする
            # 不具合が繰り返し発生したため、表示が確実に落ち着く
            # だけの時間(HIGHLIGHT_DISPLAY_DELAY_MS)を置いてから
            # ハイライトを表示するようにしている。
            self.after(HIGHLIGHT_DISPLAY_DELAY_MS, lambda w=widget: self._show_spotlight_for_widget(w))
        elif target_menu_index is not None:
            self._current_target_menu_index = target_menu_index
            self.after(
                HIGHLIGHT_DISPLAY_DELAY_MS,
                lambda i=target_menu_index: self._show_spotlight_for_menu(i),
            )
        else:
            # 対象がどうしても取れないステップでは、
            # スポットライトを消し、ダイアログの説明文だけで案内する
            self._clear_spotlight()

    def _show_spotlight_for_widget(self, widget):
        """widget の矩形を「穴」にして、それ以外を暗くする"""
        try:
            tx, ty, tw, th = self._get_rect(widget)
        except tk.TclError:
            return  # ウィジェットが破棄済み等で取得できない場合は諦める

        if tw <= 0 or th <= 0:
            return

        target_hole = (
            tx - SPOTLIGHT_PADDING, ty - SPOTLIGHT_PADDING,
            tw + SPOTLIGHT_PADDING * 2, th + SPOTLIGHT_PADDING * 2,
        )
        self._show_spotlight_rect(target_hole)

    def _show_spotlight_for_menu(self, item_index):
        """
        メニューバーの item_index 番目の項目(「ファイル」「配信」等)を
        「穴」にして、それ以外を暗くする。

        【重要】Win32 APIでの厳密な座標取得(GetMenuItemRect)は、
        環境(Windowsのバージョン・DPI設定等)によっては失敗することが
        実際に確認された。以前は、失敗した場合にスポットライトを
        完全に消していたため「②のステップになった瞬間、暗幕がふっと
        消える」という不具合になっていた。
        そこで、厳密な位置取得に失敗した場合は、各メニュー項目の
        ラベル文字列を実際のフォントで計測し、その累積幅から
        item_index番目の項目のおおよその位置を推定するフォールバックに
        切り替えるようにした(_estimate_menu_item_rect)。
        ネイティブメニューの実際の余白とは多少ズレる可能性があるが、
        「メニューバー全体」ではなく、狙った項目1つだけをある程度
        絞り込んでハイライトできる。
        """
        rect = _get_menu_bar_item_rect(self.master_app, item_index)
        used_fallback = False
        if rect is None:
            rect = self._estimate_menu_item_rect(item_index)
            used_fallback = True

        if rect is None:
            self._clear_spotlight()
            return

        if used_fallback and hasattr(self.master_app, "console"):
            self.master_app.console.log(
                "チュートリアル: メニュー項目の正確な位置を取得できなかったため、"
                "文字幅からおおよその位置を推定してハイライトしています。",
            )

        x, y, w, h = rect
        target_hole = (
            x - SPOTLIGHT_PADDING, y - SPOTLIGHT_PADDING,
            w + SPOTLIGHT_PADDING * 2, h + SPOTLIGHT_PADDING * 2,
        )
        self._show_spotlight_rect(target_hole)

    def _estimate_menu_item_rect(self, item_index):
        """
        Win32 APIでの厳密な位置取得に失敗した場合のフォールバック。
        メニューバーの各項目ラベル(MENU_LABELS、add_cascadeした順)を
        実際のフォントで計測し、その累積幅から item_index 番目の項目の
        おおよその位置(x座標)を推定する。

        Tkinterのトップレベルウィジェット自身の winfo_rootx/rooty は、
        Windows環境では通常「タイトルバー・メニューバーより下、
        実際のクライアント領域の左上」を指す。つまりメニューバー自体は、
        そのすぐ上にある帯状の領域とみなせるため、メニューバーの
        高さ分だけ上にずらした矩形として近似している。
        (メニューの実際の左右余白・高さはOSのテーマ・DPI設定で
        多少前後するが、SPOTLIGHT_PADDINGの分の余裕もあるため、
        多少のズレがあっても実用上は十分機能する)
        """
        if item_index < 0 or item_index >= len(MENU_LABELS):
            return None

        try:
            self.master_app.update_idletasks()
            mx = self.master_app.winfo_rootx()
            my = self.master_app.winfo_rooty()
        except tk.TclError:
            return None

        try:
            font = tkfont.Font(font=("TkMenuFont", 9))
        except tk.TclError:
            return None

        x = mx
        for i, label in enumerate(MENU_LABELS):
            item_width = font.measure(label) + MENU_ITEM_PADDING_X
            if i == item_index:
                return (x, my - MENU_BAR_HEIGHT_ESTIMATE, item_width, MENU_BAR_HEIGHT_ESTIMATE)
            x += item_width

        return None

    def _show_spotlight_rect(self, target_hole):
        """
        指定した矩形(target_hole)の周りに、明るい色の縁取りを描いて
        強調表示する(暗幕は使わない、縁取りのみのシンプルな構成)。
        """
        self._clear_spotlight()
        self._draw_accent_border(target_hole)

    def _draw_accent_border(self, rect):
        """
        指定した矩形(rect)の外周に沿って、明るい色の細い縁取りを
        4本(上下左右)のToplevelウィンドウで描く。暗幕による
        「周りが暗い」という対比だけでなく、対象そのものに
        はっきりした縁取りを付けることで、より積極的に
        「ここです」と示す効果を狙っている。
        """
        x, y, w, h = rect
        if w <= 0 or h <= 0:
            return

        thickness = ACCENT_BORDER_THICKNESS
        bars = [
            (x, y, w, thickness),                            # 上辺
            (x, y + h - thickness, w, thickness),             # 下辺
            (x, y, thickness, h),                              # 左辺
            (x + w - thickness, y, thickness, h),              # 右辺
        ]
        for bx, by, bw, bh in bars:
            if bw <= 0 or bh <= 0:
                continue
            bar = tk.Toplevel(self.master_app)
            bar.overrideredirect(True)
            bar.configure(bg=ACCENT_BORDER_COLOR)
            bar.attributes("-topmost", True)
            bar.geometry(f"{int(bw)}x{int(bh)}+{int(bx)}+{int(by)}")

            # 【重要】Windowsは、アプリ起動直後などユーザーが実際に
            # クリック操作をまだ行っていないタイミングでは、
            # プログラム側から新規ウィンドウを勝手に最前面(topmost)へ
            # 割り込ませることを制限することがある(フォーカスの
            # 横取り防止の仕様)。これにより、-topmost を設定しても
            # 実際には最前面に来ず、縁取りが見えないまま、という
            # 現象が起きていたと考えられる(「次へ」「戻る」等の
            # クリック操作を挟むと直る、という報告と一致する)。
            # 対策として、topmost属性を一度OFFにしてから改めてONに
            # 戻すことで、Windowsに強制的にz-orderを再評価させる、
            # という定番の回避策を行っている。
            bar.attributes("-topmost", False)
            bar.attributes("-topmost", True)
            bar.lift()

            self._spotlight_windows.append(bar)

    def _get_rect(self, widget):
        """
        ウィジェット(またはウィンドウ)の、画面上の絶対座標での矩形を返す。

        【重要・経緯】以前ここを update() に変更したことがあったが、
        update() はOS側の保留イベントも全て処理してしまうため、
        メイン画面の <Configure> イベント(位置・サイズ変更の通知)まで
        誘発してしまい、それが「メイン画面が動いたらスポットライトを
        追従させる」処理(_on_master_configure)を再帰的に呼び出し、
        結果としてハイライトが一瞬正しい位置に表示された直後、
        再計算によって別の位置へズレてしまう、という副作用が発生した。
        そのため、ここは軽量で副作用の少ない update_idletasks() に
        戻している。「初回表示時に描画が確定しきっていない」問題への
        対策は、__init__側で(Configureの監視を仕掛ける前の、
        安全なタイミングで)1回だけ行うようにしている。
        """
        widget.update_idletasks()
        return (
            widget.winfo_rootx(), widget.winfo_rooty(),
            widget.winfo_width(), widget.winfo_height(),
        )

    def _clear_spotlight(self):
        for win in self._spotlight_windows:
            try:
                win.destroy()
            except tk.TclError:
                pass
        self._spotlight_windows = []

    def _on_master_configure(self, event):
        """
        メイン画面が移動・リサイズされた際、表示中のスポットライトが
        あれば位置を追従させる。頻繁に発火するイベントだが、
        _show_spotlight_*自体は軽量な処理のため、都度呼び直して問題ない。
        """
        if self._current_target_widget is not None:
            self._show_spotlight_for_widget(self._current_target_widget)
        elif self._current_target_menu_index is not None:
            self._show_spotlight_for_menu(self._current_target_menu_index)

    def _on_destroy(self, event):
        # このTutorialWindow自体が閉じられた時にだけ処理する
        # (子ウィジェットのDestroyイベントまで拾わないようにチェックする)
        if event.widget is self:
            try:
                self.master_app.unbind("<Configure>", self._configure_binding)
            except tk.TclError:
                pass

            # フォアグラウンドウィンドウの監視ループ(300ms毎の自己再スケジュール)
            # を止めておく。止めないと、既に破棄されたウィジェットに対して
            # after()コールバックが呼ばれ続け、エラーログが出続けることになる。
            if self._foreground_watch_job is not None:
                try:
                    self.after_cancel(self._foreground_watch_job)
                except tk.TclError:
                    pass
                self._foreground_watch_job = None

            # 【重要・保険】WM_DELETE_WINDOWのprotocol設定により、通常は
            # _close()経由で暗幕は既に片付けられているはずだが、万一
            # 何らかの理由でそれを経由せずこのウィンドウが破棄された
            # 場合(想定外の呼び出し経路等)でも、暗幕が残って操作不能に
            # なる事態だけは絶対に避けたいため、<Destroy>イベント側でも
            # 保険として後片付けを行っておく。既に片付け済みであれば、
            # 単に空のリストに対して何もしないだけなので、二重に
            # 呼んでも害はない。
            self._clear_spotlight()

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

    def _prev_step(self):
        if self.current_step > 0:
            self.current_step -= 1
            self._show_step(self.current_step)

    def _close(self):
        self._clear_highlight()
        self._clear_spotlight()

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