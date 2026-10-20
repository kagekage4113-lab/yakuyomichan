==============================================================
 YakuYomi-chan  (Version 1.6.0)
 A free, open-source Windows app that translates and reads
 live-stream chat aloud
==============================================================

■ What is this?

  It reads live chat from Twitch and YouTube, translates foreign-language
  comments into Japanese, and reads them aloud with VOICEVOX.
  It also provides a subtitle overlay you can show in OBS.

  - Translation runs on a local AI (LM Studio + Gemma) on your own PC.
    Chat comments are never sent to an external translation service.
  - It also works without translation (read-aloud only).


■ Requirements

  1. VOICEVOX   ... for speech (free)
  2. LM Studio  ... for translation (free; only if you use translation)
  3. A stream token ... Twitch or YouTube

  Installers for VOICEVOX and LM Studio are bundled in the
  "optional_installers" folder inside the app folder.
  See the Help menu in the app for setup guides.


■ Quick start

  1. Launch VOICEVOX.
  2. (For translation) Load a model in LM Studio and start its local server.
  3. Open "配信 (Stream)" menu -> "トークン設定 (Token settings)" and enter
     your Twitch channel name and token (or YouTube info).
  4. Choose the platform on the main screen (Twitch / YouTube / both).
  5. Press "▶ 起動 (Start)" to begin monitoring chat and reading aloud.

  The "● VOICEVOX" and "● LM Studio" indicators at the bottom show whether
  each one is reachable. A tutorial is shown on first launch.

  Note: the app's interface is in Japanese.


■ Main features

  [Translation]
  - Only foreign-language comments are translated into Japanese.
  - Toggle with the "翻訳: ON / OFF" button at the top of the main screen.
    When OFF, no LM Studio is needed and it works as a read-aloud tool.

  [Speech (VOICEVOX)]
  - Pick a character with "ボイス選択 (Voice select)".
  - Adjust speed, pitch, intonation, etc. in "詳細設定 (Advanced)".
  - Set a mute-toggle hotkey (default: Ctrl+Shift+M).
  - Platform choice and volume are remembered between launches.

  [Speech filters (in Advanced settings)]
  - Do not read URLs
  - Do not read emoji / kaomoji / Twitch emotes
  - Announce incoming emotes with a phrase (text is editable)
  - Maximum characters read aloud (cut text ends with "(以下略)")
  * Filters affect audio only. The chat log and the overlay always show
    the full text.
  * Comments containing emotes are not translated; the original is shown.
  * Kaomoji containing kanji (e.g. ( *´艸｀) ) may be partly read aloud.

  [OBS overlay (subtitles)]
  - Add an OBS "Browser Source" with this URL:
      http://127.0.0.1:8765/overlay
    (Copy it from "表示 (View)" -> "オーバーレイURLをコピー".)
  - Choose a subtitle mode in the View menu:
      Off / Translation only / Original + translation
  - "オーバーレイのデザインを設定" lets you change font, colors, number
    of lines, and more:
      - 3-column layout (user / comment / translation)
      - Show or hide the original text
      - Twitch emotes as images
      - Twitch badges (requires a Client ID)
      - Twitch clip thumbnails (requires a Client ID)
        - The clip URL text can be hidden
  - If changes do not appear, refresh the cache of the OBS Browser Source.

  [Chat log]
  - The main screen lists user / original / read-aloud text.
  - It follows the newest line (stays put while you scroll up).
  - "ファイル (File)" -> "ログを開く" opens the saved log folder.

  [Other]
  - "ファイル" -> "自動起動設定" configures auto-launch of VOICEVOX / LM Studio.
  - "ヘルプ (Help)" -> "アップデートを確認" checks for a new version.


■ Twitch badges and clip thumbnails (optional)

  These use the Twitch API and need a "Client ID". Enter it in
  "配信" -> "トークン設定" -> "Client ID (任意)".

  - Use the Client ID from the SAME app registration that issued your token.
    A mismatched pair will fail.
  - If it is empty or fails, only badges/thumbnails are missing;
    translation and speech are not affected.


■ Settings files

  Settings are saved next to the exe. Open them from
  "ファイル" -> "設定フォルダを開く".

    token_config.json     ... tokens, channel names
    app_settings.json     ... platform, volume
    voice_params.json     ... speech settings and filters
    overlay_design.json   ... overlay design
    hotkey_config.json    ... hotkey
    selected_voice.json   ... selected voice
    logs\                 ... chat logs

  * token_config.json contains credentials. Never share it or show it
    on stream.


■ Updating / uninstalling

  - Update: just run the newer installer; it upgrades in place and keeps
    your settings.
  - Uninstall: Windows Settings -> Apps.


■ Troubleshooting

  - "Could not start Twitch monitoring"
      -> Check that the channel name and token are entered.
  - No speech
      -> Check that VOICEVOX is running (see the indicator at the bottom).
  - No translation
      -> Check that the LM Studio server is running with a model loaded,
         and that translation is "ON".
  - Overlay not updating
      -> Refresh the OBS Browser Source cache.

  If it is still unresolved, please open an issue on GitHub.


■ Links and licenses

  GitHub: https://github.com/kagekage4113-lab/multilingual-chat-tts-bot

  When using VOICEVOX voices, follow each character's terms of use and
  credit "VOICEVOX:<character name>" on streams. LM Studio and the AI
  model you use are subject to their own licenses.

==============================================================
