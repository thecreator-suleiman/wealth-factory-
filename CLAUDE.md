# Monezic pipeline - context for Claude

Owner: Suleiman (Kigali, UTC+2). Wants SHORT answers, honesty, minimal token use, only Monezic topics.
Never ask for or accept secret keys in chat (they live in GitHub Secrets).

## What it is
Free, automatic GitHub Actions pipeline: 2 stickman Shorts/day (02:00 + 14:00 Kigali, 12 h apart) to TikTok + Instagram;
YouTube gets only the 02:00 video (owner chose 1/day: YouTube refused 3 uploads in ~24 h). All (via Buffer API), report to Telegram + WhatsApp (Whatabot), IG reels auto-shared to FB Page "Monezic".
Repo: thecreator-suleiman/wealth-factory- (public). Free plans site: GitHub Pages /docs (branded).
Claude is NOT used by the pipeline - only for fixes/upgrades.

## Key files
- config.yaml - channel, rules, mix [story x7, business, tool, news], formats, posting times.
- factory/main.py - run(): opening = "hook" ALWAYS (owner 21 Nov: no "stop scrolling"; stop/fact test ended),
  61-70 s, Part 1/2
  (story slot n%7==3 -> Part 1; next video = Part 2, script kept in history), 5 rotating STRUCTURES,
  hook formulas rotate, no end card (ends on payoff, 0.35s tail), backup-run guard (skip if posted <5h ago).
- factory/script.py - Gemini writer (auto model discovery + 404 replacement learning), Groq backup writer
  (GROQ_API_KEY), retention formula prompt (paradox hook, "Wait,...?", "You see,", payoff last, loop ending,
  ~2.5 w/s = 150-172 words - owner 21 Nov: 2.95 w/s still too fast), _better_hook() (6 alternative
  first lines from Gemini, hook scorer keeps the best), trending_names() (Gemini search, 1 call/run), _problems hard + SOFT issues
  (soft = hook score/title/formula beats; accepted from try 3), _guarantee_shape (opener; question + FOLLOW/OFFER
  on the LESSON beat; payoff is last; Part 1 adds "Part 2 is next" line).
- factory/hooks.py - 21 hook formulas (factory/ytkit/hooks.json) + ported hookscore (reject <46) + title linter.
  MIT, Jake Schincariol (factory/ytkit/LICENSE).
- factory/sfx.py - numpy SFX (whoosh/pop/cash/impact/riser/ding) placed from beats; mixed in finish_video.
- factory/stickman.py - Cairo renderer: 47 actions (action()), fx, 10 places (draw_place), chairs/desks,
  9 camera moves, _prepare() no-repeat. Style = "sample" (approved 21 Nov, owner's sample video): solid black
  round head + white face, straight thick limbs, round fists, green name-tag bubble, green floor shadow, grey
  chair / black desk+laptop, light outline places (clouds, road lane, clock, plant), figures ~0.8 scale.
  VFX: zoom punch on numbers, dash confetti, floating $ / code symbols, big green text fades out,
  scenes fade in from white. Captions + top banner: Archivo Black (video.py), white caps, green banner.
- factory/voice.py - edge-tts Andrew Multilingual (main, rate +4%), Andrew Neural, then Kokoro am_michael backup.
  Never female. fit_pace() -> ~2.5 words/s (config words_per_second), 61-70 s (>60 s for TikTok rewards).
- factory/video.py captions/music; publish.py Buffer (_existing(): never posts the same text twice on a channel
  within 3 h - fixes 23 Nov TikTok double post after a slow Buffer reply + retry); notify.py Telegram/WhatsApp + advice() + share_messages().
- factory/health.py + .github/workflows/health.yml - Sunday weekly report.
- tools/buffer_audit.py + buffer_audit.yml - daily 17:30 Kigali: lists Buffer posts, Telegram alert ONLY if a
  duplicate or failed post (manual run = print only). trailer.yml can also push ONE made video to YouTube.
- .github/workflows/factory.yml - crons 10:50/22:50 UTC (70 min early) + backups 12:45/00:45; inputs post, test_backup.

## Pending (do in order)
1-1f. DONE Sat 21 Nov (marker restyle, hooks/scorer/title linter, loops, Part 1/2, trending, SFX+VFX,
   retention formula). Voice clone (OmniVoice): REJECTED - model weights are CC-BY-NC (non-commercial; Monezic
   is monetised) + audio tokenizer under Boson Higgs licence. Keep Andrew. Owner's own recordings are fine.
2. Channel trailer: made from take 2 of owner's recording (0:51-1:30, no stumbles), 43 s incl. end card.
   APPROVED 21 Nov. Scheduled YouTube-only via Buffer for Sun 22 Nov 12:00 UTC (14:00 Kigali), post
   6b013ab25e993799d8589f92. File: media branch trailer/monezic_trailer.mp4. Tool: workflow trailer.yml +
   factory/trailer_post.py; extra uploads logged in data/youtube_extra.json; main.py skips YouTube if
   >=2 uploads in last 26 h (uses posted_at = real upload time). 23 Nov: 02:00 YouTube refused (trailer + guard
   bug, fixed); 14:00 Bezos video sent to YouTube by hand.
2b. DONE 21 Nov: renderer matched to owner's sample video (approved, merged from branch sample-style).
3. Sun 22 Nov: compare old growth test (history.json "variant" stop/* vs fact/*) with owner's YouTube Studio
   screenshots (Viewed vs swiped away; start: 39% stayed). Hook-first is already live (owner's call).
4. Next week: weekly long YouTube video (6-10 min, hand-drawn whiteboard style, ideally owner's voice).
   Check if Buffer can post long videos; else YouTube API (owner does one-time OAuth).
5. ~29 Nov: TikTok review (stuck ~115 views) - if <200 avg, new TikTok account in Buffer.
6. Buffer API key expires 14 Nov 2027.

## Notes
- YouTube "inauthentic content" policy: keep originality (lesson line, varied structures, sources, research).
- Instagram DM bot: Zorcha free, keywords PLAN/GUIDE, link to Pages site. IG handle @monezic_, YT @monezic.
- Owner's weekly Claude limit resets Fri 23:00 Kigali; office computer use Tue-Fri - keep work light then.
