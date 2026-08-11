# -*- coding: utf-8 -*-
"""
OBSのブラウザソースに読み込ませる、チャットオーバーレイ用の
ローカルWebサーバー。

【使い方】
1. このサーバーを起動する: python overlay_server.py
2. OBSで「ブラウザ」ソースを追加し、URLに
   http://127.0.0.1:8765/overlay を指定する
   (幅・高さはお好みで。背景は透過される)
3. main_window.py 側から push_comment() を呼ぶたびに、
   オーバーレイの表示がリアルタイムで更新される
   (ブラウザ側はポーリングで定期的に取得する簡易方式)

【表示モード】
- "off"          : 何も表示しない
- "translated"   : 翻訳(読み上げ内容)だけ表示
- "both"         : 原文 + 翻訳を両方表示
GUIの「表示」メニューの字幕トグルから set_display_mode() で切り替える想定。
"""

import logging
import os
import threading
import time

from flask import Flask, jsonify, render_template_string

from resource_path import resource_path, writable_path

app = Flask(__name__)

# ポーリング(1秒おきの/api/comments取得)のアクセスログで
# コンソールが埋め尽くされるのを防ぐため、Flask標準のログ出力を抑制する。
# エラー自体はPython側の例外として別途捕捉されるので、実害はない。
logging.getLogger("werkzeug").setLevel(logging.ERROR)

MAX_DISPLAY_LINES = 8  # オーバーレイに表示する行数(画面を圧迫しすぎないよう絞る)

_state_lock = threading.Lock()
_comments = []  # {"platform":..., "user":..., "original":..., "translated":..., "ts":...}
_display_mode = "translated"  # "off" / "translated" / "both"


def push_comment(platform: str, user: str, original: str, translated: str):
    """
    メイン画面側から、新しいコメントが処理されるたびに呼び出す。
    """
    with _state_lock:
        _comments.append({
            "platform": platform,
            "user": user,
            "original": original,
            "translated": translated,
            "ts": time.time(),
        })
        # 増えすぎないよう、直近の分だけ保持する
        if len(_comments) > 100:
            _comments.pop(0)


def set_display_mode(mode: str):
    """
    "off" / "translated" / "both" のいずれかに切り替える。
    GUIの字幕トグルから呼ばれる想定。
    """
    global _display_mode
    if mode not in ("off", "translated", "both"):
        raise ValueError(f"不正なモードです: {mode}")
    with _state_lock:
        _display_mode = mode


OVERLAY_HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<link rel="stylesheet" href="/overlay.css">
</head>
<body>
  <div id="chat-container"></div>
  <script>
    const container = document.getElementById("chat-container");
    // 前回描画した内容を覚えておき、変化が無ければ再構築しない。
    // 【重要】毎回innerHTMLを作り直すと、CSSのfadeinアニメーションが
    // 都度最初から再生されてしまい、「出ては消え」を繰り返しているように
    // 点滅して見える原因になっていた。内容が同じ間は何もしないことで
    // これを防ぐ。
    let lastRenderedKey = "";

    async function refresh() {
      try {
        const res = await fetch("/api/comments");
        const data = await res.json();

        if (data.mode === "off") {
          if (lastRenderedKey !== "off") {
            container.innerHTML = "";
            lastRenderedKey = "off";
          }
          return;
        }

        // モード + コメント内容をキー化し、前回描画時と一致するなら
        // DOMには一切手を触れない(=アニメーションも再生されない)
        const key = data.mode + "::" + JSON.stringify(data.comments);
        if (key === lastRenderedKey) {
          return;
        }
        lastRenderedKey = key;

        container.innerHTML = "";
        data.comments.forEach(c => {
          const line = document.createElement("div");
          line.className = "chat-line";

          let html = `<span class="chat-user">${escapeHtml(c.user)}</span>${escapeHtml(c.translated)}`;
          if (data.mode === "both" && c.original) {
            html += `<div class="chat-original">${escapeHtml(c.original)}</div>`;
          }
          line.innerHTML = html;
          container.appendChild(line);
        });
      } catch (e) {
        // サーバー未起動時などは静かに無視し、次回のポーリングで再試行する
      }
    }

    function escapeHtml(text) {
      const div = document.createElement("div");
      div.textContent = text;
      return div.innerHTML;
    }

    // --- デザイン設定(CSS)の自動再読み込み ---
    // overlay_style.cssが更新されたら、ブラウザのキャッシュを
    // 回避しつつ、OBS側で手動更新しなくても新しい見た目が
    // 反映されるようにする。
    let lastCssVersion = null;
    const cssLink = document.querySelector('link[rel="stylesheet"]');

    async function checkCssUpdate() {
      try {
        const res = await fetch("/api/css-version");
        const data = await res.json();
        if (lastCssVersion !== null && data.version !== lastCssVersion) {
          // バージョン(更新時刻)が変わっていたら、クエリパラメータを
          // 付け直してlinkタグを差し替える。これによりブラウザは
          // 「新しいファイル」として扱い、キャッシュを使わず取得し直す。
          cssLink.href = "/overlay.css?v=" + data.version;
        }
        lastCssVersion = data.version;
      } catch (e) {
        // 取得に失敗しても、次回のポーリングで再試行するだけでよい
      }
    }

    setInterval(refresh, 1000);
    setInterval(checkCssUpdate, 1000);
    refresh();
    checkCssUpdate();
  </script>
</body>
</html>
"""

DEFAULT_CSS_PATH = "overlay_style.css"


@app.route("/overlay")
def overlay():
    print("[overlay_server] オーバーレイに接続されました。(OBS等のブラウザソースが開かれました)")
    return render_template_string(OVERLAY_HTML)


def _get_css_path() -> str:
    """
    overlay_style.css の、書き込み可能な場所(exeと同じフォルダ)への
    パスを返す。まだ存在しなければ、同梱されている雛形データ
    (resource_path側)をコピーしてから使う。
    このCSSは overlay_design_window.py からユーザーが編集・保存する
    対象でもあるため、読み込み専用の同梱データ置き場ではなく、
    書き込み可能な場所を正として扱う。
    """
    target_path = writable_path(DEFAULT_CSS_PATH)

    if not os.path.exists(target_path):
        bundled_path = resource_path(DEFAULT_CSS_PATH)
        if os.path.exists(bundled_path):
            with open(bundled_path, "r", encoding="utf-8") as f:
                initial_css = f.read()
            with open(target_path, "w", encoding="utf-8") as f:
                f.write(initial_css)

    return target_path


@app.route("/overlay.css")
def overlay_css():
    """
    見た目を定義するCSSを配信する。
    overlay_style.css をユーザーが自由に編集すれば、ブラウザ側を
    更新(OBSならソースを右クリック→更新)するだけで反映される。
    ファイルが見つからない場合のために、最低限のフォールバックCSSも
    用意しておく(オーバーレイが真っ白/操作不能にならないようにするため)。
    """
    css_path = _get_css_path()
    if os.path.exists(css_path):
        with open(css_path, "r", encoding="utf-8") as f:
            css = f.read()
    else:
        css = (
            "html,body{margin:0;padding:0;background:transparent;"
            "font-family:sans-serif;overflow:hidden;}"
            "#chat-container{display:flex;flex-direction:column;"
            "justify-content:flex-end;height:100vh;padding:12px;"
            "box-sizing:border-box;}"
            ".chat-line{background:rgba(20,20,30,0.65);border-radius:8px;"
            "padding:8px 12px;margin-bottom:6px;color:#fff;font-size:18px;}"
            ".chat-user{font-weight:bold;color:#7fd4ff;margin-right:6px;}"
            ".chat-original{color:#aaa;font-size:14px;margin-top:2px;}"
        )
    return css, 200, {"Content-Type": "text/css; charset=utf-8"}


@app.route("/api/comments")
def api_comments():
    with _state_lock:
        recent = _comments[-MAX_DISPLAY_LINES:]
        mode = _display_mode
    return jsonify({"mode": mode, "comments": recent})


@app.route("/api/css-version")
def api_css_version():
    """
    overlay_style.cssの最終更新時刻を返す。
    ブラウザ側はこれをポーリングし、値が変わっていたら
    CSSを(キャッシュを回避しつつ)再取得することで、
    OBS側でソースを手動更新しなくても、デザイン変更が
    即座に反映されるようにしている。
    """
    css_path = _get_css_path()
    if os.path.exists(css_path):
        version = os.path.getmtime(css_path)
    else:
        version = 0
    return jsonify({"version": version})


def run_server(host="127.0.0.1", port=8765):
    """
    メイン画面から別スレッドで呼び出す想定。
    Flaskの開発用サーバーで十分(ローカル配信ツールなので)。
    """
    app.run(host=host, port=port, debug=False, use_reloader=False)


if __name__ == "__main__":
    # 動作確認用: ダミーコメントを入れてサーバーを起動する
    push_comment("twitch", "user_92", "Hello! nice stream today", "こんにちは、今日も配信いいね")
    push_comment("youtube", "たろう", "", "今日のご飯なに食べたの?")
    set_display_mode("both")
    print("http://127.0.0.1:8765/overlay をブラウザで開いて確認してください。")
    run_server()
