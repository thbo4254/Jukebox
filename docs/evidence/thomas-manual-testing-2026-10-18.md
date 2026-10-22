# Thomas — manual testing and fixes, 2026-10-18

Assistant-recorded results from Thomas's actual feedback, not a formal GitHub peer-review approval. Testing began on merged main and continued locally with PR #9 (DJ deadlines) and PR #11 (contextual titles). These PRs remain subject to teammate review. Detailed contemporaneous comments are on issues #1, #8 and #10.

## Manual results

| Scenario | Expected | User-reported result |
|---|---|---|
| Instrumental creation: Rainy Sunday | Generate instrumental audio and cover, playable in library | Successful generation. Initial DJ-enabled Play then stalled (see failure below). |
| Initial DJ preparation | Intro then music automatically | Failed: remained “Your DJ is getting ready” for more than three minutes; Skip started music. |
| DJ timeout recovery after fix | Notice and automatic music fallback without Skip | Passed: music started after about 15 seconds with a DJ timeout notice. |
| Music-only Play/Pause/Resume | Immediate music without DJ delay; pause/resume | All three actions successful. |
| Queue advancement, DJ off | Finishing first song automatically starts next without overlap | Went as expected. |
| Skip during music, DJ off | Stop first song and start queued song without overlap | Successful. |
| Duration 5 seconds | Reject below minimum | Message: “Value must be greater than or equal to 10”. Network/library-count inspection was not separately performed. |
| Duration 121 seconds | Reject above maximum | Message: “Value must be less than or equal to 120”. Network/library-count inspection was not separately performed. |
| Page refresh | Saved Rainy Sunday and cover persist; song plays | Cover appeared and song played successfully. DJ reset to on; DJ also worked in this attempt. |
| Vocal lyrics | Qwen lyrics appear and are editable | Lyrics appeared and could be edited. |
| Edited vocal generation | Saved/generated song uses edited lyrics | Song included updated lyrics; Thomas reported every word sung correctly for this example. Not a general fidelity guarantee. |
| Contextual title | Blank title yields concise contextual name | Cabin/rain/fireplace/book/tea topic produced a title reported as “Ember and Tea”; direct library inspection found the actual saved title **Embers and Tea**. Song completed with a cover and played successfully. |
| Explicit title | Keep “Cabin Lights” rather than replace it | Title preserved. |
| Full server restart | Saved tracks, covers and playback survive | Cabin Lights cover and playback successful after restart, with DJ off. |
| DJ transition after restart | Upbeat & Playful intro for Cabin Lights, then music automatically, no overlap | Thomas reported “Successful”. This is user-reported default-voice DJ success, not a human-reference voice test. |

## Diagnosed failure and correction

Live diagnostic observations at the time of the DJ stall: a brief Qwen intro and model-list request each exceeded a 44.002-second diagnostic deadline. Chatterbox responded in 1.252 seconds with 2.360 seconds of decoded audio. These do not establish a global/permanent outage or isolate the underlying remote network/server cause.

PR #9 adds a 15-second total server DJ budget and a 20-second browser fallback, without shortening music/image generation timeouts. A post-fix real app request returned HTTP 504 at 15.002951 seconds. Thomas then confirmed automatic fallback manually. Later successful DJ playback shows success in that later attempt, not guaranteed future service availability.

## Requested improvement

PR #11 replaces description-copying for blank titles with Qwen contextual naming. Explicit titles remain unchanged; title generation has its own 15-second deadline and visible “Untitled track” fallback that does not block music generation. Existing songs are not renamed. A live title-only probe returned “Rainy Sunday Cafe Jazz” in 0.331 seconds. Thomas then tested the complete contextual-title flow and explicit-title preservation.

## Automated and independent checks

- PR #9: 35 Python and 28 JavaScript tests passed locally. Independent scoped code review passed. GitHub offline CI passed Windows/macOS/Ubuntu: https://github.com/thbo4254/Jukebox/actions/runs/39163663416
- PR #11: 60 Python and 33 JavaScript tests passed locally. Independent scoped code review passed. GitHub offline CI passed Windows/macOS/Ubuntu: https://github.com/thbo4254/Jukebox/actions/runs/39169628367
- DJ failure injection used a real Chrome browser with an intercepted stalled request and manually fired timer. Music playback advanced with no uncaught errors. This is controlled failure testing, not live upstream success evidence.
- Full server restart: all 10 track IDs and titles, and SHA-256 hashes of every served audio/cover file, matched before and after. No active generation jobs were interrupted.
- Credential-aware scans passed before code publication. No credentials, voice references or local runtime library files are included in these reports.

Detailed regression evidence: [DJ timeout](dj-timeout-fix.md), [contextual titles](contextual-titles.md).

## Remaining work / observations

- Teammate review and merge of PR #9, followed by retargeting/review/merge of stacked PR #11. Do not treat assistant review as teammate participation.
- Refresh resets DJ preference to on; recorded usability observation, not fixed here.
- Human-reference voice quality, final-version independent ZIP installation, final documentation reconciliation, and team contribution/review obligations remain separate tasks.
- Pre-existing lyric-provenance wording can misattribute edited/manually supplied lyrics; recorded limitation, not changed in these fixes.
- Local user-generated songs remain in ignored `data/`. They survive local restarts but are not automatically part of GitHub or submission archives. Bundled sample assets remain in `samples/`.

## GitHub records

- Team tests: https://github.com/thbo4254/Jukebox/issues/1
- DJ failure: https://github.com/thbo4254/Jukebox/issues/8
- DJ fix: https://github.com/thbo4254/Jukebox/pull/9
- Title request: https://github.com/thbo4254/Jukebox/issues/10
- Title implementation: https://github.com/thbo4254/Jukebox/pull/11
