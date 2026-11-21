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
- factory/main.py - run(): growth test (opening stop/fact by n%2; length now fixed "fast" 61-70s), Part 1/2
  (story slot n%7==3 -> Part 1; next video = Part 2, script kept in history), 5 rotating STRUCTURES,
  hook formulas rotate, no end card (ends on payoff, 0.35s tail), backup-run guard (skip if posted <5h ago).
- factory/script.py - Gemini writer (auto model discovery + 404 replacement learning), Groq backup writer
  (GROQ_API_KEY), retention formula prompt (paradox hook, "Wait,...?", "You see,", payoff last, loop ending,
  ~3.7 w/s = 214-249 words), trending_names() (Gemini search, 1 call/run), _problems hard + SOFT issues
  (soft = hook score/title/formula beats; accepted from try 3), _guarantee_shape (opener; question + FOLLOW/OFFER
  on the LESSON beat; payoff is last; Part 1 adds "Part 2 is next" line).
- factory/hooks.py - 21 hook formulas (factory/ytkit/hooks.json) + ported hookscore (reject <46) + title linter.
  MIT, Jake Schincariol (factory/ytkit/LICENSE).
- factory/sfx.py - numpy SFX (whoosh/pop/cash/impact/riser/ding) placed from beats; mixed in finish_video.
- factory/stickman.py - Cairo renderer: 47 actions (action()), fx, 10 places (draw_place), chairs/desks,
  9 camera moves, _prepare() no-repeat. Style = "marker" (21 Nov, owner's image 3): curved limbs, mitten hands,
  shoe feet, oval head, green/red mood glow. VFX: zoom punch on numbers/big-text words, confetti on
  celebrations, glow behind big text, light flash on reveals (You see / Wait / headline / payoff).
- factory/voice.py - edge-tts Andrew Multilingual (main, rate +35%), Andrew Neural, then Kokoro am_michael backup.
  Never female. fit_pace() -> ~3.7 words/s, 61-70 s (stays >60 s for TikTok rewards).
- factory/video.py captions/music; publish.py Buffer; notify.py Telegram/WhatsApp + advice() + share_messages().
- factory/health.py + .github/workflows/health.yml - Sunday weekly report.
- .github/workflows/factory.yml - crons 10:50/22:50 UTC (70 min early) + backups 12:45/00:45; inputs post, test_backup.

## Pending (do in order)
1-1f. DONE Sat 21 Nov (marker restyle, hooks/scorer/title linter, loops, Part 1/2, trending, SFX+VFX,
   retention formula). Voice clone (OmniVoice): REJECTED - model weights are CC-BY-NC (non-commercial; Monezic
   is monetised) + audio tokenizer under Boson Higgs licence. Keep Andrew. Owner's own recordings are fine.
2. Channel trailer: made from take 2 of owner's recording (0:51-1:30, no stumbles), 43 s incl. end card.
   Sent for approval 21 Nov - NOT published. Recording is NOT in the repo (privacy).
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
