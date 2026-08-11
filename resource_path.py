# -*- coding: utf-8 -*-
"""
データファイル(character_meta.json、character_icons等)への
パスを解決するための、共通ヘルパーモジュール。

【背景】
PyInstallerで --onedir 形式にビルドすると、実行ファイル
(MainApp.exe)自体は dist/MainApp/ 直下に置かれるが、
--add-data で埋め込んだデータファイル(character_meta.json等)は、
実際には dist/MainApp/_internal/ という、別のサブフォルダに
配置される。

通常の "character_meta.json" のような相対パスのままだと、
「exeがあるフォルダ」を探しに行ってしまい、_internal の中にある
ファイルを見つけられない。

この関数は、PyInstallerでビルドされている場合は _internal
フォルダの実際の場所(sys._MEIPASS)を、そうでない場合(通常の
`python main_window.py` 実行時)は今まで通りカレントフォルダを
基準にする、という切り替えを行う。

【使い方】
from resource_path import resource_path
path = resource_path("character_meta.json")
with open(path, "r", encoding="utf-8") as f:
    ...
"""

import os
import sys


def resource_path(relative_path: str) -> str:
    """
    データファイルへの、実行環境に応じた正しいパスを返す。

    - PyInstallerでビルドされた実行ファイルとして動いている場合:
      sys._MEIPASS (実際には _internal フォルダ) を基準にする
    - 通常のPythonスクリプトとして実行されている場合:
      これまで通り、カレントディレクトリ(相対パス)をそのまま使う
    """
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return relative_path


def writable_path(relative_path: str) -> str:
    """
    設定ファイル・キャッシュ等、実行中に「書き込み」が発生する
    ファイルのためのパス解決。

    【重要】resource_path() とは異なり、こちらは常に
    「実行ファイル(exe)があるフォルダ」を指す。
    _internal フォルダの中は、実行時に書き込みを行うのに
    適した場所ではない(将来的に読み取り専用として扱われる
    可能性がある、Program Files配下にインストールされた場合に
    書き込み権限が無いことがある、等の理由)ため、
    ユーザーの設定ファイル(token_config.json、
    selected_voice.json 等)は、明確に分けて扱う。
    """
    if hasattr(sys, "_MEIPASS"):
        # exe自体があるフォルダ(_internalの一つ上の階層)
        exe_dir = os.path.dirname(sys.executable)
        return os.path.join(exe_dir, relative_path)
    return relative_path
