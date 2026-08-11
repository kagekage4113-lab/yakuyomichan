# -*- coding: utf-8 -*-
"""
LM Studio経由でGemma4 2Bを呼び出し、配信コメントを
自然な日本語に翻訳するモジュール。

lang_detect.needs_translation() が True と判定したコメントだけ、
ここに回す想定。日本語コメントや短い記号系は、このモジュールを
経由せずそのまま読み上げに回すことで、LLM呼び出しの回数自体を
減らし、応答を速くする設計になっている。

【前提】
LM Studioが起動していて、指定モデル(google/gemma-4-e2b等)が
ロードされた状態で、http://127.0.0.1:1234 でAPIが待ち受けていること。

【使い方】
from translator import translate_to_japanese
result = translate_to_japanese("Hello! nice stream today")
"""

import requests

LM_STUDIO_URL = "http://127.0.0.1:1234/v1/chat/completions"
MODEL_NAME = "google/gemma-4-e2b"  # LM Studio側でロードしているモデル名に合わせる

SYSTEM_PROMPT = (
    "あなたは配信のチャットコメントを日本語に訳す翻訳者です。\n"
    "以下のルールを厳守しなさい。\n\n"
    "- 入力されたコメントを、自然な日本語に翻訳しなさい\n"
    "- 前置きや説明は一切書かず、翻訳結果の文章だけを出力しなさい\n"
    "- 元の文の勢い・カジュアルさを保ちなさい(丁寧語に変換しすぎない)\n"
    "- 意味が分からない場合でも、それらしい自然な日本語一文を返しなさい\n"
    "- 思考過程やタグは一切出力せず、翻訳結果の一文だけを出力しなさい"
)


def translate_to_japanese(text: str, timeout: int = 15) -> str:
    """
    与えられたテキストを日本語に翻訳して返す。

    LM Studioに接続できない、あるいはエラーが起きた場合は、
    例外を投げず、元のテキストをそのまま返す(読み上げが
    完全に止まってしまうのを避けるためのフォールバック)。
    呼び出し元でエラーログを出したい場合は、戻り値と入力が
    一致しているかどうかで判定できる。
    """
    payload = {
        "model": MODEL_NAME,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0.3,   # 翻訳タスクなので、創造性より安定性を優先
        "max_tokens": 120,    # 短いコメントの翻訳なので、長い出力は不要
        # 推論モデル(Qwen/DeepSeek系等)を使った場合に備えて、
        # 明示的にThinking(内部の推論過程の出力)を無効化しておく。
        # Gemma4系はもともとThinking機能を持たないため影響しないが、
        # 別モデルに差し替えた場合の安全策として付けている。
        # LM Studioのバージョン・モデルによっては効かないこともあるため、
        # 上記システムプロンプトの末尾にも同趣旨の指示を明記している
        # (二重の対策)。
        "enable_thinking": False,
    }

    try:
        resp = requests.post(LM_STUDIO_URL, json=payload, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        translated = data["choices"][0]["message"]["content"].strip()
        translated = _strip_thinking_tags(translated)
        return translated if translated else text
    except Exception as e:
        print(f"[translator] 翻訳に失敗しました(元の文をそのまま使います): {e}")
        return text


def _strip_thinking_tags(text: str) -> str:
    """
    一部のモデルは、enable_thinking=Falseを指定しても
    <think>...</think> のようなタグ付きの思考過程を出力してしまう
    ことがある。念のため、そうしたタグとその中身を取り除いてから
    返すための保険。Gemma4系では通常不要だが、安全のため常時適用する。
    """
    import re
    return re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL).strip()


def is_server_running(timeout: float = 0.5) -> bool:
    """
    LM Studioのローカルサーバーが、そもそも起動しているかどうかを
    素早く確認する。load_model/unload_modelの冒頭でこれを使うことで、
    LM Studio自体が起動していない時に、無駄なタイムアウト待ち
    (デフォルトのtimeout秒×リトライ回数分)が発生するのを防ぐ。
    タイムアウトを短く(0.5秒)しているのは、あくまで「動いているか
    どうか」の生死確認だけが目的で、実際の応答内容は見ないため。
    """
    try:
        requests.get("http://127.0.0.1:1234/v1/models", timeout=timeout)
        return True
    except Exception:
        return False


def load_model(timeout: int = 30) -> bool:
    """
    チャット監視の「起動」時に呼ぶことを想定した、モデルの事前ロード。
    LM StudioはJITロード(最初のリクエストで自動的にロードする仕組み)を
    持っているため、これを呼ばなくても動作はするが、事前に呼んでおく
    ことで「起動ボタンを押した直後の、最初のコメントの反応が遅い」
    という体感を減らせる。

    新しいAPI(0.4.0以降の /api/v1/models/load)を先に試し、
    失敗したら、軽いダミーリクエストでJITロードを誘発するだけの
    フォールバックにする。
    """
    if not is_server_running():
        print("[translator] LM Studioが起動していません。LM Studioを起動してから、もう一度お試しください。")
        return False

    try:
        resp = requests.post(
            "http://127.0.0.1:1234/api/v1/models/load",
            json={"model": MODEL_NAME},
            timeout=timeout,
        )
        if resp.ok:
            print("[translator] LM Studioのモデルをロードしました。")
            return True
    except Exception:
        pass  # このAPIが無いバージョンの可能性があるので、次の方法を試す

    try:
        requests.post(
            LM_STUDIO_URL,
            json={
                "model": MODEL_NAME,
                "messages": [{"role": "user", "content": "hello"}],
                "max_tokens": 1,
            },
            timeout=timeout,
        )
        print("[translator] LM Studioへの軽いリクエストでロードを促しました。")
        return True
    except Exception as e:
        print(f"[translator] モデルのロード確認に失敗しました: {e}")
        return False


def unload_model(timeout: int = 3) -> bool:
    """
    このアプリを閉じる際に呼ぶことを想定した、LM StudioのモデルアンロードAPI。
    「アプリを閉じてもLM StudioがVRAMを専有し続ける」という不満に対応するため、
    アプリ終了時にこれを呼び、モデルをメモリから解放する。

    LM Studioのバージョンによってエンドポイントが違うため、
    新しいAPI(0.4.0以降の /api/v1/models/unload)を先に試し、
    失敗したら、より広く使える方法(ttl=0を指定した軽いリクエスト)に
    フォールバックする。どちらも失敗した場合はFalseを返すが、
    これはアプリの終了処理自体を止める理由にはしない
    (呼び出し元は、失敗してもそのまま終了してよい)。
    """
    if not is_server_running():
        # LM Studio自体が起動していないなら、アンロードするモデルも
        # 存在しないので、無駄なタイムアウト待ちをせずすぐ諦める
        print("[translator] LM Studioが起動していないため、アンロード処理をスキップします。")
        return False

    # 方法1: 新しいv1 REST API(LM Studio 0.4.0以降)
    try:
        resp = requests.post(
            "http://127.0.0.1:1234/api/v1/models/unload",
            json={"instance_id": MODEL_NAME},
            timeout=timeout,
        )
        if resp.ok:
            print("[translator] LM Studioのモデルをアンロードしました。")
            return True
    except Exception:
        pass  # このAPIが無いバージョンの可能性があるので、次の方法を試す

    # 【重要】以前は、方法1が失敗した場合の予備として、
    # ttl=0 を指定した「軽量なはずの」リクエストを送る方法2を
    # 用意していた。しかし実際には、このリクエストもLM Studio側で
    # 通常のチャット補完(推論)として扱われてしまい、応答が返って
    # くるまで数秒単位で待たされる、という「軽量ではない」実態が
    # あったため、不確実な二重の待ち時間を生むだけと判断し削除した。
    # 方法1(公式のアンロードAPI)に対応していないLM Studioの場合は、
    # ユーザー自身にLM Studio側で手動アンロードしてもらう。
    print(
        "[translator] このLM Studioのバージョンではアンロード用APIが使えないようです。"
        "LM Studio側の画面から手動でモデルをアンロードしてください。"
    )
    return False


if __name__ == "__main__":
    # 動作確認用
    test_comments = [
        "Hello! nice stream today",
        "Bonjour tout le monde",
        "이 게임 재밌어 보이네요",
        "这个操作太厉害了",
        "OMG that was insane lol",
    ]

    for comment in test_comments:
        result = translate_to_japanese(comment)
        print(f"{comment!r}\n  → {result!r}\n")