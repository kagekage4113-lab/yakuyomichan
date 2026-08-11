====================================================
 Multilingual Chat Translation & Text-to-Speech Bot
====================================================

A tool that translates stream chat comments -- regardless of
language -- into natural Japanese, and reads them aloud using
VOICEVOX voices.

It aims for more natural, human-like translation than Twitch's
built-in machine translation, using only a local LLM. No cloud
API is used, so there are no monthly fees.

(日本語版は README_ja.txt をご覧ください)


----------------------------------------------------
 Features
----------------------------------------------------

- Chat monitoring
  Supports Twitch, YouTube, or both platforms simultaneously

- AI auto-translation
  A local LLM (Gemma4) translates comments into natural
  Japanese, regardless of the source language

- Text-to-speech
  Reads translated text aloud using VOICEVOX voices

- OBS overlay
  Displays translated text (optionally with the original) as a
  transparent overlay on your stream

- Voice selection
  Browse all VOICEVOX characters, filter by gender/genre,
  preview voices, and save favorites

- Advanced settings
  Adjust speed, pitch, intonation, and volume with sliders

- Hotkey
  Toggle mute at any time with a customizable key combination

- Chat log
  Automatically saves every processed comment, organized by date


----------------------------------------------------
 Installation
----------------------------------------------------

Run the included Install.exe. Follow the wizard to install
the main application.

After installation, a folder named "optional_installers" will
be created inside the install folder. It contains:

  - VoicevoxSetup.exe   -> Run to install VOICEVOX
  - LMStudioSetup.exe   -> Run to install LM Studio
  - download_model.bat  -> Run after installing LM Studio to
                           download the translation model (Gemma4)

Note: VOICEVOX and LM Studio are separate applications required
to run the main app. Each will take several minutes to tens of
minutes to download, depending on your connection speed.

Note: If you already have VOICEVOX or LM Studio installed, you
can skip the above steps.


----------------------------------------------------
 What to do on first launch
----------------------------------------------------

When you launch the app for the first time, a short tutorial
will appear. Please make sure to set up the following three
items.


[1] Choose a platform

  Select Twitch / YouTube / Both from the dropdown in the
  top-left of the main window.


[2] Configure tokens

  Go to "Stream" menu -> "Token Settings" and enter your
  Twitch and/or YouTube credentials.

  For Twitch:

    - OAuth token
      Get one with "chat:read" scope from a service like
      https://twitchtokengenerator.com

    - Channel name
      Your Twitch channel name


  For YouTube:

    Getting YouTube chat working requires an API key from
    Google Cloud Console. It's free and takes about 5 minutes.

    1. Go to https://console.cloud.google.com/ and sign in
       with your Google account

    2. Click "Select a project" at the top -> "New Project"
       and create one (any name works)

    3. Search for "YouTube Data API v3" in the search bar and
       open its page

    4. Click "Enable"
       Note: If you skip this, the next step may show
       "No APIs selected" with nothing to choose from.

    5. In the left menu, go to "Credentials" ->
       "+ Create Credentials" -> "API Key"

    6. Under "API restrictions," select "YouTube Data API v3"
       Note: If it doesn't appear, double-check step 4.
       Note: If it still doesn't work, you can select
       "Don't restrict key" instead -- fine for personal use.

    7. Copy the resulting key (starts with "AIzaSy...") and
       paste it into the app's token settings screen.

    Your stream's VIDEO_ID can be found in the URL of your
    YouTube Studio livestream management page.

    Example:
    https://studio.youtube.com/video/[THIS IS THE VIDEO_ID]/livestreaming

    It's the string right after "/video/", up to the next "/"
    (about 11 alphanumeric characters).

    Note: You don't need a new API key for every stream. The
    VIDEO_ID changes with every new stream, so update it each time.


[3] Check auto-launch settings

  Go to "File" menu -> "Auto-Launch Settings" to configure
  whether VOICEVOX and LM Studio should start automatically
  alongside this app.

  The executable locations are usually as follows (replace
  [USERNAME] with your actual Windows username):

    LM Studio : C:\Program Files\LM Studio\LM Studio.exe
    VOICEVOX  : C:\Users\[USERNAME]\AppData\Local\Programs\VOICEVOX\VOICEVOX.exe

  If you can't find them, right-click the desktop or Start Menu
  shortcut and select "Open file location."

  Note: LM Studio may not automatically load a model or start
  its server just from launching. If so, enable LM Studio's
  "start server automatically" option, or load/start it manually.


----------------------------------------------------
 Using it with OBS
----------------------------------------------------

1. When you launch the app, an overlay server starts
   automatically.

2. In OBS, add a "Browser" source.

3. Enter this URL:
   http://127.0.0.1:8765/overlay
   (You can also copy this from "View" -> "Copy Overlay URL"
   in the app menu.)

4. The background is transparent by default.

You can toggle what the overlay displays -- "No subtitles,"
"Translation only," or "Original + translation" -- from the
"View" menu.

You can also customize font size, colors, and background
transparency from "View" -> "Overlay Design Settings."


----------------------------------------------------
 FAQ
----------------------------------------------------

Q. I don't hear any audio at all.

A. Check that VOICEVOX is running, the volume slider in the
  main window isn't at 0, and mute (the speaker icon) isn't
  enabled.


Q. Comments are read out in the original language instead of
  being translated.

A. Check that LM Studio is running and the correct model is
  loaded. The "LM Studio" indicator at the top of the main
  window turns green once the model is loaded. If it's yellow
  or red, start the model in LM Studio.


Q. YouTube chat isn't responding.

A. You need to actually be live-streaming before the YouTube
  chat ID can be retrieved. Also, unlike Twitch, YouTube uses
  polling (checking every few seconds), so responses will be
  somewhat slower.


Q. I only want to use VOICEVOX. Do I need LM Studio?

A. No. Turn off the "Translation: ON/OFF" button on the main
  screen, and the app will read comments aloud as-is, in any
  language, without translation.


----------------------------------------------------
 About the Voice Assets
----------------------------------------------------

Some of the default voice samples use audio from the free
character "Tsukuyomi-chan."

  Tsukuyomi-chan Corpus:
  https://tyc.rei-yumesaki.net/material/corpus/

  Official Tsukuyomi-chan site:
  https://tyc.rei-yumesaki.net/

Tsukuyomi-chan's assets are used in accordance with the
Tsukuyomi-chan Character License.


----------------------------------------------------
 License & Notes
----------------------------------------------------

- This tool is released as free, open-source software. It is
  not intended for commercial distribution or for-profit use.

- Never share or publish configuration files containing
  personal information, such as token_config.json, which holds
  your Twitch/YouTube API tokens.

- When using VOICEVOX, please follow the license terms of each
  individual character.
