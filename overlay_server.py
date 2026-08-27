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

from flask import Flask, jsonify, make_response, render_template_string

from resource_path import resource_path, writable_path
from overlay_design_window import load_design

app = Flask(__name__)

# ポーリング(1秒おきの/api/comments取得)のアクセスログで
# コンソールが埋め尽くされるのを防ぐため、Flask標準のログ出力を抑制する。
# エラー自体はPython側の例外として別途捕捉されるので、実害はない。
logging.getLogger("werkzeug").setLevel(logging.ERROR)

MAX_DISPLAY_LINES = 8  # overlay_design.jsonが未作成の場合のフォールバック値
                        # (通常はオーバーレイのデザイン設定画面の「表示行数」で
                        # 決めた値がoverlay_design.jsonから読み込まれ、こちらは使われない)

_state_lock = threading.Lock()
_comments = []  # {"platform":..., "user":..., "original":..., "translated":..., "emotes":..., "ts":...}
_display_mode = "translated"  # "off" / "translated" / "both"


def push_comment(platform: str, user: str, original: str, translated: str, emotes=None, badges=None):
    """
    メイン画面側から、新しいコメントが処理されるたびに呼び出す。

    emotes: Twitchエモートの位置情報つきリスト
      ([{"id":..., "start":..., "end":..., "text":...}, ...])。
      twitch_watcher.py の _parse_emotes_tag() が返す形式そのまま。
      original(原文)の中の該当位置を、ブラウザ側で実際のエモート
      画像に差し替えるために使う。YouTube等、対応する概念が無い
      プラットフォームからは None(=空リスト扱い)で呼ばれる。
    badges: サブスク・モデレーター等の実績バッジ一覧
      ([{"set_id":..., "version":..., "image_url":...}, ...])。
      image_urlがNoneのバッジ(Client-ID未設定時など)は、
      ブラウザ側で自然に無視される。ユーザー名の隣に、
      常時(設定のON/OFFなしで)表示する。
    """
    with _state_lock:
        _comments.append({
            "platform": platform,
            "user": user,
            "original": original,
            "translated": translated,
            "emotes": emotes or [],
            "badges": badges or [],
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

        // モード + レイアウト設定 + コメント内容をキー化し、前回描画時と
        // 一致するならDOMには一切手を触れない(=アニメーションも再生されない)
        const key = data.mode + "::" + data.stacked_layout + "::" + data.show_original
                  + "::" + JSON.stringify(data.comments);
        if (key === lastRenderedKey) {
          return;
        }
        lastRenderedKey = key;

        container.innerHTML = "";
        data.comments.forEach(c => {
          const line = document.createElement("div");
          line.className = "chat-line";

          const emotes = c.emotes || [];
          const badges = c.badges || [];

          // Twitchのサブスク・モデレーター等のバッジは、実際のチャット欄と
          // 同じ感覚で使えるよう、常時(ON/OFFの設定なしで)表示する。
          // image_urlが無いバッジ(Client-ID未設定/取得失敗時)は、
          // 画像を出しようがないので静かにスキップする。
          const badgesHtml = badges
            .filter(b => b.image_url)
            .map(b => `<img class="chat-badge" src="${b.image_url}" alt="${escapeHtml(b.set_id || '')}" `
                    + `title="${escapeHtml(b.set_id || '')}" `
                    + `style="height:1.1em;vertical-align:middle;margin-right:3px;">`)
            .join("");
          const userHtml = badgesHtml + escapeHtml(c.user);

          // 【重要】main_window.py側で、エモートを含むコメントは
          // そもそも翻訳を挟まない設計にしている(翻訳するとエモート名が
          // 意味不明な訳文になり、かつ文字位置もズレてしまうため)。
          // そのため、emotesが存在する行の c.translated は、常に
          // 「翻訳されていない原文そのもの」であることが保証されており、
          // 文字位置もemotesの位置情報とズレない。よって、翻訳側・原文側
          // どちらであっても、renderWithEmotesで正確な位置に画像を
          // 差し込める(以前あった「末尾にまとめて添えるだけ」という
          // 妥協策は、この設計変更により不要になった)。
          let translatedHtml = renderWithEmotes(c.translated, emotes);

          // 【重要】以前は data.mode === "both" (メイン画面の「表示」
          // メニュー内の字幕モード)だけで原文表示の有無を判定しており、
          // オーバーレイのデザイン設定画面から直接コントロールする
          // 手段が無かった(メニューの奥に隠れていて気づきにくい、
          // という指摘があった)。デザイン設定の「show_original」を
          // 直接見るようにし、ここで完結して切り替えられるようにする。
          const hasOriginal = data.show_original && !!c.original;

          let html;
          if (data.stacked_layout) {
            // 3行レイアウト: ユーザー名 / コメント本文(原文) / 翻訳文(あれば)
            // を、それぞれ独立した行として縦に並べる。
            html = `<div class="chat-user-line">${userHtml}</div>`;
            if (hasOriginal) {
              html += `<div class="chat-original">${renderWithEmotes(c.original, emotes)}</div>`;
              html += `<div class="chat-translated">${translatedHtml}</div>`;
            } else {
              html += `<div class="chat-translated">${translatedHtml}</div>`;
            }
          } else {
            // 従来のレイアウト: ユーザー名と本文が同じ行に表示される
            html = `<span class="chat-user">${userHtml}</span>${translatedHtml}`;
            if (hasOriginal) {
              // 原文側は、実際の文字位置に沿って正確にエモート画像を差し込める
              html += `<div class="chat-original">${renderWithEmotes(c.original, emotes)}</div>`;
            }
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

    function emoteImgTag(emote) {
      const url = `https://static-cdn.jtvnw.net/emoticons/v2/${encodeURIComponent(emote.id)}/default/dark/2.0`;
      const alt = escapeHtml(emote.text || "");
      return `<img class="chat-emote" src="${url}" alt="${alt}" title="${alt}" `
           + `style="height:1.3em;vertical-align:middle;margin:0 2px;">`;
    }

    function renderWithEmotes(text, emotes) {
      if (!emotes || emotes.length === 0) {
        return escapeHtml(text);
      }
      let html = "";
      let cursor = 0;
      // emotesは出現位置(start)順に並んでいる前提(twitch_watcher.py側でsort済み)
      emotes.forEach(e => {
        if (e.start < cursor || e.start > text.length) {
          return;  // 想定外の位置(既に処理済みの範囲と重複、等)は安全のため無視
        }
        if (e.start > cursor) {
          html += escapeHtml(text.slice(cursor, e.start));
        }
        html += emoteImgTag(e);
        cursor = e.end + 1;
      });
      if (cursor < text.length) {
        html += escapeHtml(text.slice(cursor));
      }
      return html;
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
    # 【重要】このページ(HTML+JS本体)自体がブラウザ/OBSにキャッシュされると、
    # アプリを新しいバージョンに更新しても、OBS側で「ソースを更新」
    # (あるいはOBS再起動)しない限り、古いJSのまま動き続けてしまう
    # (CSSは別途バージョン管理してポーリング再取得しているが、
    # HTML/JS本体はこれまでキャッシュ制御をしていなかった)。
    # 明示的にキャッシュ禁止ヘッダーを付けることで、この事故を防ぐ。
    response = make_response(render_template_string(OVERLAY_HTML))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


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
            ".chat-user-line{font-weight:bold;color:#7fd4ff;}"
            ".chat-translated{margin-top:2px;}"
        )
    return css, 200, {"Content-Type": "text/css; charset=utf-8"}


@app.route("/api/comments")
def api_comments():
    # 表示行数・レイアウト設定は、オーバーレイのデザイン設定画面
    # (overlay_design_window.py)でユーザーが調整した値
    # (overlay_design.json)をその都度読み込む。設定画面をまだ一度も
    # 開いていない/保存していない場合は、load_design()がデフォルト値を
    # 返すので、常にどちらかの値で正しく動作する。
    design = load_design()
    max_lines = design.get("max_lines", MAX_DISPLAY_LINES)
    stacked_layout = design.get("stacked_layout", False)
    show_original = design.get("show_original", True)

    with _state_lock:
        recent = _comments[-max_lines:] if max_lines > 0 else []
        mode = _display_mode
    return jsonify({
        "mode": mode, "comments": recent,
        "stacked_layout": stacked_layout, "show_original": show_original,
    })


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
    # エモート付きコメントの表示確認用(実在のTwitchエモートID "25" = Kappa を使用)。
    # 【重要】main_window.py側の設計により、エモートを含むコメントは翻訳を
    # 挟まないため、translatedとoriginalは同じ原文になる(位置情報が
    # ズレないようにするため)。ここでも実際の挙動に合わせている。
    push_comment(
        "twitch", "emote_user", "", "Kappa nice one Kappa",
        emotes=[
            {"id": "25", "start": 0, "end": 4, "text": "Kappa"},
            {"id": "25", "start": 15, "end": 19, "text": "Kappa"},
        ],
    )
    set_display_mode("both")
    print("http://127.0.0.1:8765/overlay をブラウザで開いて確認してください。")
    run_server()
