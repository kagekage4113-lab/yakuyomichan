# Multilingual Chat Translation & Text-to-Speech Bot

Translates multilingual stream chat into Japanese and reads it aloud with VOICEVOX. Runs entirely on a local LLM — no cloud API, no monthly fees.

More natural and human-like than Twitch's built-in machine translation.

日本語の詳しい説明は [README_ja.txt](README_ja.txt) をご覧ください。


## Features

- **Chat monitoring** — Twitch, YouTube, or both at the same time
- **AI translation** — A local LLM (Gemma4) translates any language into natural Japanese
- **Text-to-speech** — Reads translated text aloud with VOICEVOX voices
- **OBS overlay** — Transparent overlay showing translations (with original text, optionally)
- **Voice picker** — Browse VOICEVOX characters by gender/genre, preview, save favorites
- **Fine-tuned controls** — Speed, pitch, intonation, volume sliders
- **Hotkey** — Toggle mute with a custom key combination
- **Chat log** — All processed comments saved automatically, organized by date

This tool deliberately avoids complex conversational-AI features. By focusing only on "translate and read aloud," it stays lightweight and stable.


## Download

Get the latest installer from the [Releases](../../releases) page.

Run `Install.exe` to install the main application. VOICEVOX and LM Studio (required for translation) are bundled as separate installers inside the `optional_installers` folder after setup — see `install_guide.txt` there for step-by-step instructions.

If you only want text-to-speech (no translation), you can skip installing LM Studio entirely and just use VOICEVOX with this app.


## Documentation

- [README_ja.txt](README_ja.txt) — Full Japanese guide (installation, token setup, OBS integration, FAQ)
- [README_en.txt](README_en.txt) — Full English guide


## About the Voice Assets

Some default voice samples use audio from the free character "Tsukuyomi-chan" ([official site](https://tyc.rei-yumesaki.net/)), used under the Tsukuyomi-chan Character License.


## License

Released as free, open-source software. Not intended for commercial distribution.

Never share configuration files containing personal tokens (e.g. `token_config.json`).
