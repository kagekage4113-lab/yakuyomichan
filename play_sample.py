# -*- coding: utf-8 -*-
"""
VOICEVOXのサンプル試聴を、名前呼び+簡単な挨拶の2パターンに固定し、
かつ「初回だけ生成して、以降はローカルのwavファイルを再生するだけ」
にすることで、2回目以降の再生を高速化するモジュール。

VOICEVOX本体アプリのサンプル再生(複数候補からランダムに選ばれ、
歌などの長いものが混ざる)とは無関係に、常にこの2文のどちらかが
即座に再生される。

【キャッシュの場所】
sample_cache/{style_id}_{0or1}.wav
(style_id ごと・サンプル番号ごとに1ファイル)

【使い方】
from play_sample import play_sample_toggle
play_sample_toggle(style_id=3, display_name="ずんだもん")
  → 呼ぶたびに、0番目→1番目→0番目...と交互に再生される
"""

import os
import threading

import requests

VOICEVOX_URL = "http://127.0.0.1:50021"
CACHE_DIR = "sample_cache"

# ここで再生するサンプル文を固定する。
# {name} の部分は、選んだキャラクターの display_name に置き換わる。
SAMPLE_TEXTS = [
    "{name}です。よろしくお願いします。",
    "こんにちは、今日もいい天気ですね。",
]

# style_id ごとに「次はどちらを再生するか(0 or 1)」を覚えておく
_toggle_state = {}


def _synthesize(text, style_id):
    """VOICEVOXのエンジンAPIで、指定テキスト・スタイルの音声を生成する"""
    query_resp = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": style_id},
        timeout=30,
    )
    query_resp.raise_for_status()
    query_json = query_resp.json()

    synth_resp = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": style_id},
        json=query_json,
        timeout=30,
    )
    synth_resp.raise_for_status()
    return synth_resp.content  # wavバイト列


def _get_cached_path(style_id, sample_index):
    os.makedirs(CACHE_DIR, exist_ok=True)
    return os.path.join(CACHE_DIR, f"{style_id}_{sample_index}.wav")


def _ensure_cached(style_id, display_name, sample_index):
    """
    そのスタイル・サンプル番号のwavが、まだローカルに無ければ
    VOICEVOXで生成してキャッシュする。既にあれば何もしない。
    戻り値: wavファイルのパス
    """
    path = _get_cached_path(style_id, sample_index)
    if os.path.exists(path):
        return path

    text = SAMPLE_TEXTS[sample_index].format(name=display_name)
    wav_bytes = _synthesize(text, style_id)
    with open(path, "wb") as f:
        f.write(wav_bytes)
    return path


def _play_wav_file(path):
    """
    ローカルのwavファイルを実際にスピーカーで再生する。
    Windows環境ではwinsoundを優先的に使う(追加の依存が不要なため)。
    それ以外の環境ではplaysoundにフォールバックする。
    """
    try:
        import winsound
        winsound.PlaySound(path, winsound.SND_FILENAME | winsound.SND_ASYNC)
        return
    except ImportError:
        pass

    try:
        from playsound import playsound
        # 再生中にGUIが固まらないよう別スレッドで実行
        threading.Thread(target=playsound, args=(path,), daemon=True).start()
    except ImportError:
        print(f"警告: 音声再生ライブラリが見つかりません。手動で再生してください: {path}")


def play_sample_toggle(style_id, display_name):
    """
    そのキャラ・スタイルのサンプルを再生する。
    呼ぶたびに「名前呼び」「挨拶」が交互に切り替わる。

    戻り値: 今回再生したサンプルの番号(0 or 1)。
            GUI側で、ボタンの表示(次はどちらが再生されるか)を
            更新するのに使う。
    """
    current = _toggle_state.get(style_id, 0)

    try:
        path = _ensure_cached(style_id, display_name, current)
        _play_wav_file(path)
    except Exception as e:
        print(f"試聴に失敗しました(VOICEVOXが起動していない可能性があります): {e}")

    # 次回は逆側を再生する
    _toggle_state[style_id] = 1 - current
    return current


def clear_cache():
    """
    音声モデルを入れ替えた場合など、キャッシュを作り直したい時に使う。
    """
    if not os.path.exists(CACHE_DIR):
        return
    for filename in os.listdir(CACHE_DIR):
        os.remove(os.path.join(CACHE_DIR, filename))


if __name__ == "__main__":
    # 動作確認用: ずんだもん(ノーマル、style_id=3)で交互再生を2回試す
    for _ in range(2):
        idx = play_sample_toggle(style_id=3, display_name="ずんだもん")
        print(f"再生したサンプル番号: {idx}")
