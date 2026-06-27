## ̐Join my telegram channel ␐  https://t.me/cipher_attacks

<p align="center">
  <a href="README.md">
    <img src="https://img.shields.io/static/v1?label=&message=ENGLISH&color=212121&style=flat-square&logo=google-translate&logoColor=blue" alt="English" height="28"/>
  </a>
  <a href="README_AM.md">
    <img src="https://img.shields.io/static/v1?label=&message=AMHARIC&color=212121&style=flat-square&logo=google-translate&logoColor=red" alt="Amharic" height="28"/>
  </a>
</p>

<p align="center">
  <img src="./hero/akasha_hero.png" width="100%" alt="Project Akasha Hero" />
</p>

<h1 align="center">PROJECT AKASHA</h1>

<p align="center">
  A modular Telegram UserBot built on telethon. integrates Gemini for context-aware automation, Edge-TTS for localized voice synthesis, and a custom media stack.
</p>

<p align="center">
  <a href="#-installation">Installation</a> ·
  <a href="#system-core">System Core</a> ·
  <a href="#-modules-manual">Modules Manual</a> ·
  <a href="#-troubleshooting">Troubleshooting</a>
</p>

<p align="center">
  <img src="./hero/image.png" width="50%" alt="Project Akasha Tools" />
</p>

## 𓏵 Overview

**Project Akasha** is a userbot that actually understands context. instead of static replies, it reads the last few messages and writes something that fits — mimicking your tone and style.

it also includes a TTS wrapper for Amharic/English voice notes, a two-stage music downloader that goes easy on RAM, and a set of group management tools. runs on local machines or cloud (Heroku/Railway).

## ➜ Project Structure

make sure your directory matches this layout. the bot uses relative paths for fonts and database files.

```text
.
├── .env
├── config.py
├── main.py
├── requirements.txt
├── docker-compose.yml
├── Dockerfile
├── Procfile
├── setup.sh
├── LICENSE
├── core
│   └── database.py
└── plugins
    ├── admin_tools.py
    ├── ai.py
    ├── creative.py
    ├── master_voice.py
    ├── music.py
    ├── security.py
    ├── growth.py
    └── system.py
```

## ⚙ Installation

<details open>
<summary><strong>1. Prerequisites</strong></summary>
<br/>

requires **Python 3.9+** and **FFmpeg**.

**Ubuntu/Debian:**
```bash
sudo apt update && sudo apt install python3 python3-pip ffmpeg -y
```

**Windows:**
1. install Python from python.org.
2. install FFmpeg and add it to system PATH.
</details>

<details>
<summary><strong>2. Dependencies</strong></summary>
<br/>

```bash
pip install -r requirements.txt
```
</details>

<details>
<summary><strong>3. Configuration (.env)</strong></summary>
<br/>

create a `.env` file in the root directory.

```ini
# telegram
API_ID=123456
API_HASH=your_api_hash
SESSION=1BVts...

# gemini keys — separate with commas
GEMINI_KEYS=AIzaSy1...,AIzaSy2...,AIzaSy3...

# or individually
GEMINI_KEY1=AIzaSyD...
GEMINI_KEY2=AIzaSyF...
GEMINI_API_KEY=AIzaSy...

# database — leave empty for local json
MONGO_URL=
```

> **⚠︎** never commit your `.env` or session string to any public repo.

</details>

<details>
<summary><strong>4. Run</strong></summary>
<br/>

```bash
python main.py
```

validates keys on startup via `Config.check_integrity()`.
</details>

## ☁︎ Cloud Deployment

for Render, Railway, or Heroku — skip the `.env` and inject these directly into the dashboard:

- `API_ID`
- `API_HASH`
- `SESSION`
- `GEMINI_KEYS` (comma separated: `Key1,Key2,Key3`)

<div id="system-core"></div>

## 𖡎 System Core

managed by `plugins/system.py`. handles the away-state logic.

### Auto-Pilot (`.auto`)

| Command | Logic |
| :--- | :--- |
| `.auto ai` | reads the last 5 messages and writes a reply that fits the conversation. |
| `.auto static` | replies with a fixed string (e.g., "Busy"). |
| `.auto off` | disables all automation. |
| `.auto [text]` | updates the static reply text. |

### Context Modes (`.mode`)
changes the tone of replies.
- `sleep` - short, groggy responses.
- `work` - professional, concise.
- `gaming` - dismissive/short.
- `default` - standard conversational style.

### Latency Simulation
keeps replies from looking automated:
1. **read delay:** random `1-3s` pause before marking as read.
2. **typing:** calculates `len(response) * 0.1s` to match realistic typing speed.

---

## ⊞ Modules Manual

### 1. Admin Tools (`plugins/admin_tools.py`)

- **Whois:** `.whois @user`. pulls a user profile card (ID, DC, scam status, bio).
- **Translator:** `Text //lang_code`. replaces the message with the translation (e.g., `Hey //am` → `ሰላም`).
- **Moderation:**
  - `.purge` — deletes messages recursively.
  - `.ban / .mute` — standard user restrictions.
  - `.zombies` — scans for deleted accounts and removes them to fix member counts.

> [!CAUTION]
> heavy purges or zombie cleaning can trigger telegram's `floodWait`. use sparingly.

---

### 2. TTS Engine (`plugins/master_voice.py`)
wrapper for **Microsoft Edge TTS**. supports SSML tags for pitch and rate control.

**Command:** `.say [text] [flags]`
- auto-switches between `Mekdes` (Amharic) and `Jenny` (English) based on script.

| Flag | Effect |
| :--- | :--- |
| `.f / .m` | force female/male voice. |
| `.echo` | hall effect. |
| `.radio` | high-pass/low-pass filter chain. |
| `.demon` | pitch shift `-400Hz`. |
| `.kid` | pitch shift `+400Hz`. |

`.whisper` — shortcut for `.slow` + low volume.

---

### 3. Image Utils (`plugins/creative.py`)
pillow based image manipulation.

- **Meme Gen:** `.meme [Top];[Bottom]`.
  - auto-fetches `NotoSansEthiopic-Bold` or `NotoSansArabic` based on script. caches fonts locally.
- **Sticker Kang:** `.kang`. converts media to `512px` WebP and appends to your sticker pack.
  - skips files >5MB to avoid memory issues on VPS.

---

### 4. Music Loader (`plugins/music.py`)
uses `yt-dlp` for SoundCloud/YouTube extraction.

1. `.song [Query]` — fetches metadata only. caches in RAM.
2. reply `1 to 5` to select.
3. downloads → converts to **MP3 192kbps** → writes id3 tags → uploads.

> [!NOTE]
> files >50MB are rejected to avoid upload timeouts.

---

### 5. Vision & Generative (`plugins/ai.py`)

- `.ai [prompt]` — uses the rotated key pool.
- reply to an image with `.ai explain` — downloads to memory buffer, sends to vision API.
- `.img` / `.imgs` — pulls images from DuckDuckGo.

---

### 6. Security Modules (`plugins/security.py`)

#### TTL Capture (anti-view-once)
disabled by default. hooks into `MessageMedia` events - if `ttl_period > 0`:
1. downloads media to temp.
2. forwards to Saved Messages.
3. tags with "ꗃ vault capture".

#### Fake Terminal
- `.hack @user` — edits a message repeatedly to simulate a terminal sequence. prank only.

---

### 7. Growth Engine (`plugins/growth.py`)

session-based tool for moving users between groups. handles dedup, filtering, and rate limits automatically.

- **Collect:** `.scrape @group` - pulls users into local session.
  - multi-source: `.scrape @g1 @g2 @g3` - merges and dedupes across all.
  - ranks by last-seen activity (`online > recently > last_week > last_month`).
- **Move:** `.addmembers @dest` - processes the list into a destination group.
  - skips anyone already there. most-active users go first.
  - adaptive sleep - shortens on clean runs, extends after rate limit hits. jitter on every pause.
- **Status:** `.gstatus` - live progress bar, eta, and per-result breakdown.
- **Stop:** `.gstop` - graceful cancel. session stays intact.
- **Filters:** `.gfilter` - set before collecting.
  - `max_last_seen` - activity cutoff (`online | recently | last_week | last_month | any`).
  - `require_username`, `require_phone`, `exclude_premium`, `max_count`.
  - *example:* `.gfilter max_last_seen=recently require_username=true max_count=1000`
- **Data:** `.gexport` / `.gimport` - save and restore session as json.
- **Clear:** `.gclear` - resets session. filters and rejected cache are kept.

> **note:** invites go out from your account. telegram restricts accounts that move too fast. use a secondary account you don't mind losing - not your main.

---

## 🔧 Troubleshooting

**FFmpeg not found:**
make sure FFmpeg is in your system PATH or install via `apt`.

**API key errors:**
keys auto-rotate, but if all are exhausted `.ai` will return an error. check your key quota.

**Dependency issues:**
```bash
pip install --force-reinstall -r requirements.txt
```

<br/>

<p align="center">
  <a href="https://t.me/cipher_attacks">
    <img src="https://img.shields.io/badge/TELEGRAM-CHANNEL-000000?style=for-the-badge&logo=telegram&logoColor=white" alt="Telegram">
  </a>
  <a href="https://github.com/Cipher-attack">
    <img src="https://img.shields.io/badge/SOURCE-CODE-000000?style=for-the-badge&logo=github&logoColor=white" alt="GitHub">
  </a>
  <a href="#">
    <img src="https://img.shields.io/badge/STATUS-ACTIVE-00FF00?style=for-the-badge&logo=statuspage&logoColor=black" alt="Status">
  </a>
</p>

<p align="center">
  Licensed under the <a href="./LICENSE">MIT License</a>.
</p>

<p align="center">
  <b>Project Akasha v1.0</b><br>
  <i>Built for the Unknown purpose ☕︎.</i>
</p>