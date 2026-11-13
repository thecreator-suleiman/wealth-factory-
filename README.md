# Wealth Factory

This makes **2 short videos every day, by itself**, and posts each one to
**TikTok, Instagram Reels and YouTube Shorts**. It costs $0.

Every video is a 65–80 second true money story with a strong hook, a natural AI
voice, 15 cinematic AI images, moving camera, big captions and a progress bar.

**Your only job:** read the message in your Telegram channel after each video.
- ✅ = posted (tap "open" to see it)
- ❌ = something went wrong (the message says what)

Videos go out at about **08:17 and 18:17 Kigali time**. GitHub can be up to an
hour late at busy times; that's normal.

---

## One-time setup (about 10 minutes)

### 1. Add your 3 keys
Open this page on GitHub (in the browser, not the app):
**Settings → Secrets and variables → Actions → New repository secret**

Add these **exactly** with these names (capital letters, underscores):

| Name | What to paste |
|---|---|
| `GEMINI_API_KEY` | your key from aistudio.google.com/apikey |
| `BUFFER_API_KEY` | your key from publish.buffer.com/settings/api |
| `TELEGRAM_BOT_TOKEN` | your new bot token from BotFather |

Optional: `POLLINATIONS_API_KEY` (free from enter.pollinations.ai) makes images
faster and removes any watermark. Without it the system still works.

### 2. Run a test
**Actions → Wealth Factory → Run workflow → Run workflow** (leave the box unticked).
After about 10 minutes, a test video arrives in your Telegram channel.
Nothing is posted to social media in a test.

### 3. Go live
Nothing to do. From now on it runs twice a day by itself.
To post one right now: run the workflow again and **tick the box**.

---

## If something goes wrong
- **❌ Buffer … not connected / disconnected**: open Buffer and reconnect that account.
- **❌ Missing secret …**: the name in step 1 is misspelled - delete it and add it again.
- **No Telegram message at all**: the bot must be an admin of your Telegram channel.
- Anything else: send a screenshot of the Telegram message to Claude.

## Where things are (you don't need to touch these)
- `config.yaml` - the channel's topic, voice, video length, posting times
- `data/history.json` - every video posted so far (prevents repeats)
- `factory/` - the program
