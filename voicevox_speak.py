# -*- coding: utf-8 -*-
"""
選択中のVOICEVOXキャラ(style_id)で、任意のテキストを
実際に音声合成して読み上げるモジュール。

play_sample.py は「固定2パターンのサンプル試聴・キャッシュ化」用だったが、
こちらは「チャットの翻訳結果など、毎回内容が変わる本番のテキスト」を
読み上げるためのもの。内容が毎回違うのでキャッシュはしない。

【前提】
VOICEVOXエンジンが起動していて、
http://127.0.0.1:50021 でAPIが待ち受けていること。

【使い方】
from voicevox_speak import speak
speak("こんにちは、今日も配信いいね", style_id=3)
"""

import os
import tempfile
import threading

import requests

from resource_path import writable_path

VOICEVOX_URL = "http://127.0.0.1:50021"


def _synthesize(text: str, style_id: int, params: dict = None) -> bytes:
    """
    VOICEVOXのエンジンAPIで、指定テキスト・スタイルの音声(wav)を生成する。

    params: {"speedScale": 1.0, "pitchScale": 0.0, "intonationScale": 1.0,
             "volumeScale": 1.0} のような、audio_queryの調整項目。
             Noneならデフォルト値(VOICEVOXが返す既定値)のまま生成する。
    """
    query_resp = requests.post(
        f"{VOICEVOX_URL}/audio_query",
        params={"text": text, "speaker": style_id},
        timeout=30,
    )
    query_resp.raise_for_status()
    query_json = query_resp.json()

    if params:
        # audio_queryが返すJSONの該当キーを、指定された値で上書きする
        for key, value in params.items():
            if key in query_json:
                query_json[key] = value

    synth_resp = requests.post(
        f"{VOICEVOX_URL}/synthesis",
        params={"speaker": style_id},
        json=query_json,
        timeout=30,
    )
    synth_resp.raise_for_status()
    return synth_resp.content


def _play_wav_bytes(wav_bytes: bytes):
    """
    生成したwavデータを、一時ファイル経由でスピーカーに再生する。
    Windows環境ではwinsoundを優先する(追加の依存が不要なため)。
    """
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp.write(wav_bytes)
            tmp_path = tmp.name

        try:
            import winsound
            winsound.PlaySound(tmp_path, winsound.SND_FILENAME)  # 同期再生
        except ImportError:
            from playsound import playsound
            playsound(tmp_path)
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass  # 再生直後で削除できない場合はOS任せにする


def _load_saved_params():
    """
    voice_settings_window.py が保存した voice_params.json があれば読み込む。
    無ければNone(=VOICEVOXの既定値のまま)を返す。

    【重要】以前は相対パス("voice_params.json")のまま open() していたため、
    PyInstallerでビルドしたexeを、書き込み権限が制限された場所
    (Program Files配下等)にインストールした場合、voice_settings_window.py
    側が書き込んだ設定(exeの隣、writable_path基準)を、こちらが
    見つけられない、というズレが生じていた。writable_path() 経由に
    修正し、保存側と読み込み側の基準を一致させている。
    """
    path = writable_path("voice_params.json")
    if not os.path.exists(path):
        return None
    try:
        import json
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def speak(text: str, style_id: int, blocking: bool = False, volume_multiplier: float = 1.0):
    """
    テキストを、指定スタイルの声で読み上げる。
    詳細設定画面で保存された話速・音高等のパラメータがあれば、
    自動的に適用される。

    volume_multiplier: メイン画面の音量ゲージ・ミュート状態を反映するための
      掛け算係数(0.0〜1.0)。詳細設定側のvolumeScaleとは別軸で、
      「今すぐの音量調整・ミュート」を素早く反映するために使う。
      0.0を渡せばミュート(無音)として扱われる。

    blocking=False(既定): 別スレッドで再生し、すぐに関数を返す。
      チャット監視ループが読み上げ待ちで止まらないようにするため。
    blocking=True: 再生が終わるまで待つ(手動テスト用)。
    """
    params = _load_saved_params() or {}
    params = dict(params)  # 呼び出し元のvoice_params.jsonを書き換えないようコピーする

    base_volume = params.get("volumeScale", 1.0)
    params["volumeScale"] = base_volume * volume_multiplier

    speak_with_params(text, style_id, params=params, blocking=blocking)


def speak_with_params(text: str, style_id: int, params: dict = None, blocking: bool = False):
    """
    speak() と同じだが、パラメータを明示的に指定できる版。
    詳細設定画面の「テスト再生」のように、保存前の値で
    試し聞きしたい場合に使う。
    """
    def _task():
        try:
            wav_bytes = _synthesize(text, style_id, params=params)
            _play_wav_bytes(wav_bytes)
        except Exception as e:
            print(f"[voicevox_speak] 読み上げに失敗しました: {e}")

    if blocking:
        _task()
    else:
        threading.Thread(target=_task, daemon=True).start()


if __name__ == "__main__":
    # 動作確認用: 選択中のボイス(selected_voice.json)があればそれを使い、
    # 無ければずんだもん(style_id=3)で試す
    import json

    style_id = 3
    label = "ずんだもん(ノーマル)"

    selected_voice_path = writable_path("selected_voice.json")
    if os.path.exists(selected_voice_path):
        with open(selected_voice_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        style_id = data.get("style_id", style_id)
        label = data.get("full_label", label)

    print(f"読み上げボイス: {label} (style_id={style_id})")
    speak("こんにちは、今日も配信いいね", style_id=style_id, blocking=True)
    print("再生完了")
