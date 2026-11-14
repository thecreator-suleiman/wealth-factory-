# Wealth Factory

This makes **2 short videos every day, by itself**, and posts each one to
**TikTok, Instagram Reels and YouTube Shorts**. It costs $0.

Every video is a 65–80 second true money story told with stickman drawings
(black figures on white, green highlights), a calm storyteller voice, soft original
piano music, big captions and a progress bar.

**Your only job:** read the message in your Telegram channel after each video.
- ✅ = posted (tap "open" to see it)
- ❌ = something went wrong (the message says what)

Videos go out at about **12:00 (noon) and 00:00 (midnight) Kigali time**. GitHub can be up to an
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

Optional - WhatsApp alerts with the YouTube link:
1. Save **+34 684 78 37 08** in your phone contacts (CallMeBot).
2. Send it this WhatsApp message: `I allow callmebot to send me messages`
3. It replies with your API key. Add two secrets: `WHATSAPP_PHONE` (your number with
   country code, e.g. `+2507xxxxxxxx`) and `CALLMEBOT_API_KEY` (the key it sent you).

### 2. Run a test
**Actions → Wealth Factory → Run workflow → Run workflow** (leave the box unticked).
After about 5 minutes, a test video arrives in your Telegram channel.
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
