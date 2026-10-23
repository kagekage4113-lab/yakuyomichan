# Multilingual Chat Translation & Text-to-Speech Bot

A tool that translates stream chat comments — regardless of language — into natural Japanese, and reads them aloud using VOICEVOX voices.

It aims for more natural, human-like translation than Twitch's built-in machine translation, using only a local LLM. No cloud API is used, so there are no monthly fees.

*(日本語版はこちら: [README_ja.md](README_ja.md))*

---

## Features

- **Chat monitoring**: Supports Twitch, YouTube, or both platforms simultaneously
- **AI auto-translation**: A local LLM (Gemma4) translates comments into natural Japanese, regardless of the source language
- **Text-to-speech**: Reads translated text aloud using VOICEVOX voices
- **OBS overlay**: Displays translated text (optionally with the original) as a transparent overlay on your stream
- **Voice selection**: Browse all VOICEVOX characters, filter by gender/genre, preview voices, and save favorites
- **Advanced settings**: Adjust speed, pitch, intonation, and volume with sliders
- **Hotkey**: Toggle mute at any time with a customizable key combination
- **Chat log**: Automatically saves every processed comment, organized by date

This tool deliberately does not include a complex conversational AI personality. By focusing solely on "translate and read aloud," it stays lightweight and stable.

---

## Installation

### Easy Install (Recommended)

Run the included `Install.exe`. Simply follow the wizard, and the following will be set up automatically:

1. The main application
2. VOICEVOX (text-to-speech engine)
3. LM Studio (local LLM runtime)
4. Gemma4 E2B (translation model)

During installation, you can check/uncheck each component individually. If you already have VOICEVOX or LM Studio installed separately, you can uncheck them and install only the main application.

> **Note**: If you install all components, the total download size is approximately **10 GB**. VOICEVOX, LM Studio, and the LLM model are all fetched from the cloud during installation, so this may take several minutes to tens of minutes depending on your connection speed. Please ensure you have sufficient disk space (15 GB+ recommended) and a stable internet connection.

Once installation completes, the auto-launch settings for VOICEVOX and LM Studio are configured automatically, and the bot starts up. On first launch, a popup will prompt you to configure your Twitch/YouTube tokens (see "Token Setup" below).

### Manual Installation (for custom setups)

If you'd rather not use `Install.exe`, you can set things up manually from a Python environment. This is recommended if you already use VOICEVOX or LM Studio, or want fine-grained control over your environment.

#### 1. Install Python libraries

```
pip install requests flask pillow twitchio keyboard
```

#### 2. Set up LM Studio and VOICEVOX

| Software | Role | Download |
|---|---|---|
| **LM Studio** | Runs the local LLM (Gemma4) | https://lmstudio.ai/ |
| **VOICEVOX** | Text-to-speech engine | https://voicevox.hiroshiba.jp/ |

As a rough guideline, a GPU with 4GB+ VRAM will give you comfortable performance. It also works without a GPU, but translation response time will be slower.

For translation, we recommend Google's **Gemma4 E2B** (lightweight variant). Search for `google/gemma-4-e2b` in LM Studio's model search screen and download it.

---

## Setup Steps (Common to Both Installation Methods)

The following steps apply whether you used the installer or set things up manually.

### 1. Confirm LM Studio and VOICEVOX are running

- **LM Studio**: Load your model, then go to the "Local Server" tab and click "Start Server" (this starts listening on `http://127.0.0.1:1234`). If you used the installer, this may already be automated via the auto-launch settings.
- **VOICEVOX**: Simply launching it is enough — the engine automatically listens on `http://127.0.0.1:50021`.

### 2. Sync VOICEVOX character data (first time only)

With VOICEVOX running, run the following once. This saves the character list and icons locally.

```
python sync_voicevox_characters.py
python fill_character_meta.py
```

### 3. Configure tokens

After launching the app, go to the "Stream" menu → "Token Settings" and enter your Twitch and/or YouTube credentials.

#### For Twitch

- **OAuth token**: Get one with `chat:read` scope from a service like `https://twitchtokengenerator.com`
- **Channel name**: Your Twitch channel name

#### For YouTube

Getting a YouTube chat working requires an API key from Google Cloud Console. It looks intimidating, but it's free and takes about 5 minutes.

1. **Go to `https://console.cloud.google.com/` and sign in with your Google account**
2. Click "Select a project" at the top → "New Project" and create one (any name works, e.g. `chat-bot`)
3. With your new project selected, search for **"YouTube Data API v3"** in the search bar and open its page
4. **Click "Enable"**
   - This step matters: if you skip it, the next step (restricting your API key) may show "No APIs selected" with nothing to choose from.
5. In the left menu, go to "Credentials" → "+ Create Credentials" → "API Key"
6. **Under "API restrictions," select "YouTube Data API v3"** (the one you just enabled)
   - If it doesn't appear as an option, double-check that step 4 was completed.
   - If it still doesn't work, you can select "Don't restrict key" instead and issue the key anyway — this is fine for personal use.
7. Copy the resulting key (starts with `AIzaSy...`) and paste it into the app's token settings screen.

Your **stream's VIDEO_ID** can be found in the URL of your YouTube Studio livestream management page.

```
https://studio.youtube.com/video/[THIS PART IS THE VIDEO_ID]/livestreaming?c=...
```

It's the string right after `/video/`, up to the next `/` (about 11 alphanumeric characters).

> **Note**: You don't need a new API key for every stream — one key tied to your Google account can be reused indefinitely. The VIDEO_ID, however, changes with every new stream, so you'll need to update it each time.

### 4. Launch the app

If you used the installer, the app launches automatically once installation finishes. For manual installs, use one of the following:

**Option A: Double-click the batch file (recommended)**

Double-click `start_app.bat` to launch. To place a shortcut on your desktop, right-click `start_app.bat`, select "Create shortcut," and move the resulting shortcut to your desktop.

**Option B: Launch from the command line**

```
python main_window.py
```

You're all set. Select a platform and click "Start" to begin monitoring chat.

### 5. (Manual installs only) Auto-launch settings for VOICEVOX / LM Studio

If you used the installer, this is already configured and you can skip this step. For manual installs, if you'd rather not launch VOICEVOX and LM Studio separately every time, go to "File" → "Auto-Launch Settings" to have them start automatically alongside this app.

Enable the toggle and specify the path to each executable (.exe). Locations vary by environment, but typically look like this (replace `[USERNAME]` with your actual Windows username):

```
LM Studio  : C:\Program Files\LM Studio\LM Studio.exe
VOICEVOX   : C:\Users\[USERNAME]\AppData\Local\Programs\VOICEVOX\VOICEVOX.exe
```

If you can't find it, right-click the desktop or Start Menu shortcut and select "Open file location" to find the actual executable.

> **Note**: LM Studio may not automatically load a model or start its Local Server just from launching. If so, enable LM Studio's "start server automatically" option in its own settings, or load/start it manually.

---

## Using it with OBS

1. When you launch the app, an overlay server starts automatically.
2. In OBS, add a "Browser" source.
3. Enter `http://127.0.0.1:8765/overlay` as the URL (you can also copy this from "View" → "Copy Overlay URL" in the app menu).
4. The background is transparent by default.

You can toggle what the overlay displays — "No subtitles," "Translation only," or "Original + translation" — from the "View" menu.

---

## FAQ

**Q. I don't hear any audio at all.**
A. Check that VOICEVOX is running, the volume slider in the main window isn't at 0, and mute (the speaker icon) isn't enabled.

**Q. Comments are read out in the original language instead of being translated.**
A. Check that LM Studio is running and the correct model is loaded. If the app can't connect to LM Studio, it falls back to reading the original text as-is — this is intentional, so that read-aloud never stops entirely.

**Q. YouTube chat isn't responding.**
A. You need to actually be live-streaming before the YouTube chat ID can be retrieved. Also note that the YouTube Data API uses polling (checking every few seconds) rather than real-time push notifications like Twitch, so responses will be somewhat slower.

---

## About the Voice Assets

Some of the default voice samples use audio from the free character "Tsukuyomi-chan."

- Tsukuyomi-chan Corpus: https://tyc.rei-yumesaki.net/material/corpus/
- Official Tsukuyomi-chan site: https://tyc.rei-yumesaki.net/

Tsukuyomi-chan's assets are used in accordance with the Tsukuyomi-chan Character License.

---

## Roadmap

- Two-way translation via Edge-TTS: Japanese → other languages (English, Chinese, Korean, European languages, etc.), so streamers can also make their own speech understood by foreign-language viewers (complementing the current "foreign language → Japanese" direction)
- Customizable colors and fonts for the chat overlay

---

## License & Notes

- This tool is released as free, open-source software. It is not intended for commercial distribution or for-profit use.
- If you install all components via the installer, expect roughly 10 GB of downloads in total. Please check your connection and available disk space beforehand.
- Never share or publish configuration files containing personal information, such as `token_config.json`, which holds your Twitch/YouTube API tokens.
- When using VOICEVOX, please follow the license terms of each individual character.

---

## Technical Overview (for developers)

| Role | Technology |
|---|---|
| GUI | Python (Tkinter) |
| Translation | Gemma4 (via LM Studio, OpenAI-compatible API) |
| Text-to-speech | VOICEVOX (local API) |
| Chat monitoring | twitchio (Twitch) / YouTube Data API v3 (YouTube) |
| Overlay delivery | Flask (local web server) |

Roles of the main files:

- `main_window.py`: Main window
- `voice_select_window.py`: VOICEVOX character search/selection screen
- `voice_settings_window.py`: Advanced settings (speed, pitch, etc.)
- `token_settings_window.py`: Token settings screen
- `auto_launch.py` / `auto_launch_settings_window.py`: Auto-launching VOICEVOX/LM Studio
- `lang_detect.py`: Japanese-detection logic (no LLM, fast heuristic check)
- `translator.py`: Translation via Gemma4
- `voicevox_speak.py`: Text-to-speech playback via VOICEVOX
- `twitch_watcher.py` / `youtube_watcher.py`: Chat monitoring
- `overlay_server.py`: OBS overlay server
- `chat_logger.py`: Automatic chat log saving
- `start_app.bat`: Startup batch file
