# Monezic pipeline - context for Claude

Owner: Suleiman (Kigali, UTC+2). Wants SHORT answers, honesty, minimal token use, only Monezic topics.
Never ask for or accept secret keys in chat (they live in GitHub Secrets).

## What it is
Free, automatic GitHub Actions pipeline: 2 stickman Shorts/day (02:00 + 14:00 Kigali, 12 h apart) to YouTube, TikTok,
Instagram (via Buffer API), report to Telegram + WhatsApp (Whatabot), IG reels auto-shared to FB Page "Monezic".
Repo: thecreator-suleiman/wealth-factory- (public). Free plans site: GitHub Pages /docs (branded).
Claude is NOT used by the pipeline - only for fixes/upgrades.

## Key files
- config.yaml - channel, rules, mix [story x7, business, tool, news], formats, posting times.
- factory/main.py - run(): growth test (opening stop/fact by n%2, length long 97s/short 70s by (n//2)%2),
  5 rotating STRUCTURES, Gemini-busy waits, sources in caption, backup-run guard (skip if posted <5h ago).
- factory/script.py - Gemini writer (auto model discovery + 404 replacement learning), Groq backup writer
  (GROQ_API_KEY), _guarantee_shape (opener, closing question + "Comment below, and follow Monezic so you can
  find us again.", "The lesson:" beat), place + pose schema.
- factory/stickman.py - Cairo renderer: 47 actions (action()), fx, 10 places (draw_place), chairs/desks,
  9 camera moves, _prepare() no-repeat. Style = "clean round" (style 6).
- factory/voice.py - edge-tts Andrew Multilingual (main), Andrew Neural, then Kokoro am_michael backup. Never female.
- factory/video.py captions/music; publish.py Buffer; notify.py Telegram/WhatsApp + advice() + share_messages().
- factory/health.py + .github/workflows/health.yml - Sunday weekly report.
- .github/workflows/factory.yml - crons 10:50/22:50 UTC (70 min early) + backups 12:45/00:45; inputs post, test_backup.

## Pending (do in order)
1. Sat 21 Nov: restyle stickmen like owner's "image 3" (hand-drawn marker look: curved limbs, mitten hands,
   shoe feet, oval head, soft green/red mood glow behind figure). Keep all actions/places/cameras.
1b. Borrow from github.com/Jakeschincariol/youtube-agent-skill (MIT, offline Python): 21 hook formulas
   (skills/yt-script/hooks.json) into the Gemini prompt, hookscore.py to reject weak hooks automatically,
   title.py linter for titles. Credit MIT license. Do NOT install as Claude skills (costs tokens, manual).
1c. Also Saturday: loop endings (last line flows into first), Part 1/Part 2 cliffhanger stories
   (some videos), trending names this week (Gemini search). Owner approved all three.
1d. Also Saturday: SOUND EFFECTS + 2D VFX. Generate own SFX with numpy (no licence issues, like
   tools/make_music.py): whoosh on scene change, pop on big text, cash register on money, impact on fall/shock,
   riser into hook, ding on lesson. Mix in finish_video under voice. VFX in Cairo: zoom punch on key words,
   particles/confetti, glow, light flash on reveals. No Blender (too slow/fragile on free GitHub runners).
1e. Voice test (owner asked): github.com/debpalash/VoiceStudio (AGPL-3.0 app, too heavy for the pipeline).
   Its default engine k2-fsa/OmniVoice (GGUF, runs on CPU) could CLONE the owner's own voice from his trailer
   recording. Test speed + quality on a GitHub CPU runner (90 s narration must take < ~15 min) and check the
   model weights' licence. Only switch if clearly better than Andrew; keep Andrew as fallback.
1f. Retention formula from github.com/mromidev/claude-animated-shorts STYLE_BIBLE (MIT; measured on 20 viral
   shorts): narration 3.5-4.1 words/s (ours ~2.5 - too slow: raise rate / fit to ~3.7 w/s), hook = paradox stated
   as fact in sentence 1 with no setup, one mystery beat ("Wait...?"), pivot "You see,", ironic payoff in last
   1-2 lines, video ENDS on the payoff (shorten outro/end card), 55-70 s. Their 3D Remotion pipeline is too heavy
   for free runners - borrow the formula only.
2. Channel trailer from owner's own voice recording (re-attached in chat; pick the cleaner take; ~40s script).
   Send for approval before publishing.
3. Sun 22 Nov: compare growth test (history.json "variant") with owner's YouTube Studio screenshots
   (Viewed vs swiped away; start: 39% stayed). Keep the winner.
4. Next week: weekly long YouTube video (6-10 min, hand-drawn whiteboard style, ideally owner's voice).
   Check if Buffer can post long videos; else YouTube API (owner does one-time OAuth).
5. ~29 Nov: TikTok review (stuck ~115 views) - if <200 avg, new TikTok account in Buffer.
6. Buffer API key expires 14 Nov 2027.

## Notes
- YouTube "inauthentic content" policy: keep originality (lesson line, varied structures, sources, research).
- Instagram DM bot: Zorcha free, keywords PLAN/GUIDE, link to Pages site. IG handle @monezic_, YT @monezic.
- Owner's weekly Claude limit resets Fri 23:00 Kigali; office computer use Tue-Fri - keep work light then.
