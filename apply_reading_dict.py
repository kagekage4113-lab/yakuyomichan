# -*- coding: utf-8 -*-
"""
読み間違い補正辞書 単体適用ツール(ReadingDictApplier.exe の元になるスクリプト)

やく読みちゃんを更新せずに、補正辞書だけをVOICEVOXへ登録したい人向け。
exeをダブルクリックするだけで使える(Pythonは不要)。

動作:
  1. 確認ダイアログを出す(登録先はVOICEVOX自身の辞書のため)
  2. VOICEVOXが起動していなければ、よくあるインストール先を探して
     エンジンを一時的に起動する(見つからなければ、起動を案内して終了)
  3. 辞書を登録し、結果を表示する
  4. このツールがエンジンを起動していた場合は、終了時に閉じる

オプション:
  --remove  登録した語を削除する(取り消し)
  --yes     確認ダイアログを出さずに実行する

【ビルド】
  pyinstaller --onefile --noconsole --name ReadingDictApplier apply_reading_dict.py
  (reading_dictionary.py と同じフォルダで実行する)
"""

import os
import subprocess
import sys
import time

import reading_dictionary

BASE_URL = "http://127.0.0.1:50021"
TITLE = "やく読みちゃん 読み間違い補正辞書"

MB_YESNO = 0x04
MB_ICONERROR = 0x10
MB_ICONQUESTION = 0x20
MB_ICONINFORMATION = 0x40
IDYES = 6


def message_box(text, flags=MB_ICONINFORMATION):
    """Windowsのメッセージボックスを出す(Windows以外ではコンソールに出す)"""
    try:
        import ctypes
        return ctypes.windll.user32.MessageBoxW(0, text, TITLE, flags)
    except Exception:
        print(f"[{TITLE}]\n{text}\n")
        return IDYES


def candidate_engine_paths():
    """VOICEVOXエンジン(run.exe)の、よくあるインストール先の候補"""
    local = os.environ.get("LOCALAPPDATA", "")
    program_files = os.environ.get("ProgramFiles", "")
    candidates = []
    for root in (os.path.join(local, "Programs", "VOICEVOX"), os.path.join(program_files, "VOICEVOX")):
        candidates.append(os.path.join(root, "vv-engine", "run.exe"))
        candidates.append(os.path.join(root, "run.exe"))
    return [p for p in candidates if p and os.path.exists(p)]


def ensure_engine():
    """
    VOICEVOXエンジンに接続できる状態にする。
    戻り値: (接続できたか, このツールが起動したプロセスまたはNone)
    """
    if reading_dictionary.is_engine_up(BASE_URL):
        return True, None

    for path in candidate_engine_paths():
        try:
            flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
            proc = subprocess.Popen([path], cwd=os.path.dirname(path), creationflags=flags)
        except OSError:
            continue
        for _ in range(45):  # 2秒 × 45回 = 最大90秒待つ
            if reading_dictionary.is_engine_up(BASE_URL):
                return True, proc
            time.sleep(2)
        proc.terminate()

    return False, None


def main():
    args = sys.argv[1:]
    remove_mode = "--remove" in args
    skip_confirm = "--yes" in args

    if not skip_confirm:
        if remove_mode:
            question = (
                "やく読みちゃんが登録した補正辞書の語を、\n"
                "VOICEVOXの辞書から削除します。\n\n削除しますか?"
            )
        else:
            question = (
                "辞書パッチを適用します。\n"
                "VOICEVOXが起動しているか、ご確認をお願いします。\n\n"
                f"VOICEVOXが読み間違えやすい語({len(reading_dictionary.ENTRIES)}語)の読みを、\n"
                "VOICEVOXのユーザー辞書に登録します。\n\n"
                "・登録先はVOICEVOX自身の辞書のため、VOICEVOXを使う\n"
                "  他のアプリにも反映されます。\n"
                "・既に同じ語を登録している場合は上書きしません。\n"
                "・もう一度このツールを --remove 付きで実行すると取り消せます\n"
                "  (やく読みちゃん本体のメニューからも取り消せます)。\n\n"
                "登録しますか?"
            )
        if message_box(question, MB_YESNO | MB_ICONQUESTION) != IDYES:
            return 0

    ok, started_proc = ensure_engine()
    if not ok:
        message_box(
            "VOICEVOXに接続できませんでした。\n\n"
            "VOICEVOXを起動してから、もう一度このツールを実行してください。",
            MB_ICONERROR,
        )
        return 1

    try:
        if remove_mode:
            result = reading_dictionary.remove_dictionary(BASE_URL)
            text = f"削除: {result['removed']}語" + (f" / 失敗: {result['failed']}語" if result["failed"] else "")
        else:
            result = reading_dictionary.apply_dictionary(BASE_URL)
            text = (
                f"登録: {result['added']}語 / 登録済みのため飛ばした語: {result['skipped']}語"
                + (f" / 失敗: {result['failed']}語" if result["failed"] else "")
            )
    except Exception as e:
        message_box(f"処理に失敗しました。\n\n{e}", MB_ICONERROR)
        return 1
    finally:
        if started_proc is not None:
            started_proc.terminate()

    message_box(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
