# Verification and design report

## Scope and evidence quality

Executed on macOS with Python 3.12.13 and real headless Chrome, against the actual class endpoints. Live evidence timestamps are in UTC (the work occurred on October 12 locally / October 13 UTC, 2026). No paid services or port 9000 were used. No external account, repository or remote configuration was modified.

There are two deliberately separate kinds of evidence:

- **Offline tests:** 34 Python tests and 16 JavaScript tests (13 playback, 3 voice-selection) pass. HTTP, DOM and audio doubles are labeled fixtures; their content is not a sample asset or proof of an actual model call. TDD tracer cycles were run for external configuration, service adapters, persistence, generation/retry, security, DJ requests, the UI shell and playback. Browser-discovered and independent-review regressions received failing tests before fixes. The latest offline-only rerun is recorded in [review-fixes-offline.json](evidence/review-fixes-offline.json); older quality-gate and live records remain historical, not reruns of these fixes.
- **Live tests:** actual Qwen, ACE-Step, FLUX and Chatterbox outputs were requested, downloaded, decoded and exercised in a real browser. Machine-readable records link below. Screenshots are real rendered app captures, not mockups. The speech checks establish playable output, not subjective voice-clone fidelity or human listening approval.

## Inputs → expected → actual

| Feature / input | Expected behavior | Actual observation and evidence |
|---|---|---|
| Three requested sample concepts, 30 seconds each | Original class audio, Qwen vocal lyrics, new matching FLUX covers bundled and ready to play | All three fully decoded: 1,440,000 frames each at 48 kHz, stereo, exactly 30.0 seconds. All covers decoded/displayed at 768×768. Nonzero measured peaks and SHA-256s are in [live-services.json](evidence/live-services.json). |
| Vocal custom song: “Window Seat — browser check,” train-window topic, custom acoustic style, custom peaceful mood, 12 seconds | Qwen lyrics first; user can edit; no audio job before explicit Generate; final lyrics unchanged | Browser drafted Qwen text, appended “Home is waiting past the rain.” and explicitly generated. Saved lyrics exactly equaled the edited textarea. ACE audio decoded to 12.0 seconds; FLUX cover saved and displayed. [browser.json](evidence/browser.json), [lyrics screenshot](screenshots/lyrics-review.png), [generation screenshot](screenshots/generating.png). |
| Instrumental custom song: “Sunday Coffee — instrumental check,” jazz, warm/relaxed, 10 seconds | Skip lyrics, create and play audio and new cover | `/api/lyrics` was never called by this browser flow. Saved lyrics empty; `instrumental=true`, duration 10.0, audio/cover ready; real browser playback advanced with DJ off. [instrumental-browser.json](evidence/instrumental-browser.json). |
| Amber After Hours, Warm & Laid-back DJ, pause while request pending | Keep paused after live response; Play resumes speech; then song starts without overlap | Browser preserved paused state after live speech arrived, resumed on Play, naturally transitioned from speech to the protected music URL with `paused=false`. [browser.json](evidence/browser.json), [DJ playback screenshot](screenshots/dj-playing.png). |
| Queue next Saturday Neon after Amber | Natural music end advances; skip pending intro plays that same next song | Observed automatic advance to Saturday Neon; Skip during pending DJ began its music and stale responses did not take over. [browser.json](evidence/browser.json). |
| Music Enthusiast default voice, The Long Way Home | Song-specific Qwen commentary spoken by default Chatterbox | HTTP 200; decoded 10.08-second, 24 kHz speech. Exact returned commentary recorded in [live-services.json](evidence/live-services.json). |
| Upbeat & Playful, synthetic reference from app-generated default speech | Reference speech request accepts MP3 and yields playable output without persisting uploaded reference | Backend HTTP 200, 6.48-second decoded output. A separate real-browser MP3 file-upload flow also reached speech playback; transmitted reference presence was checked without printing its data. [live-services.json](evidence/live-services.json), [browser-extra.json](evidence/browser-extra.json), [reference screenshot](screenshots/voice-reference.png). **Synthetic smoke test only; human-reference quality remains untested.** WAV parsing is covered by offline tests, not a live human WAV test. |
| Pause then Play during music | Audio clock freezes and resumes | Real browser clock stayed fixed during pause and advanced on resume. [browser-extra.json](evidence/browser-extra.json). |
| Independent second browser tab | A separate queue; refresh never retains reference file | Second tab had an empty queue while first retained queued tracks. Refresh cleared file input and preserved only its tab’s queued IDs. [browser-extra.json](evidence/browser-extra.json). |
| Invalid voice bytes in a file named `.wav` | Actionable error; no remote voice request; continue music | HTTP 422 with format/duration/size guidance; UI showed the error and real music played with `paused=false`. [browser-extra.json](evidence/browser-extra.json), [error screenshot](screenshots/recoverable-error.png). |
| Invalid 999-second duration | Reject before generation | HTTP 422; sanitized duration guidance. [live-services.json](evidence/live-services.json). |
| Image-service failure then cover retry (offline injection) | Audio retained; only image regeneration | Python test proved identical saved audio bytes, one music call, two cover calls and a valid recovered PNG. No real image-service outage is claimed. |
| Cross-origin, missing custom header, hostile Host, oversized body, returned off-host/port-9000 download URLs | Block side effects/downloads without exposing credentials | Offline parametrized tests return 403/413 or safe service errors; credentials never sent to returned third-party URLs, redirects never followed. |
| App restart / clean install | Persistent library; samples import once; missing config still allows offline playback | Store/API reopen test preserves generated audio. Agent fresh-copy pip install passes offline tests and serves all three samples/covers and UI with no credentials; see [portable-install.json](evidence/portable-install.json). Real-server restart results are recorded separately in [restart.json](evidence/restart.json). |
| 1440px desktop, 390px mobile | Readable library/controls, no horizontal overflow | All rendered image sizes verified; zero uncaught browser exceptions in main and extra runs. Mobile scroll width equals viewport width; player controls remain reachable. [desktop](screenshots/collection.png), [mobile](screenshots/mobile.png). |

The generated browser-check songs are in ignored runtime `data/`, not bundled as submission samples. Their screenshot/evidence references describe this development installation; a fresh installation correctly starts with only the three named samples.

## Bugs found and fixed, not hidden

### Bundled filename vs browser URL

The first end-to-end run reached real DJ speech but failed the assertion that music was playing. Browser inspection showed a `MEDIA_ELEMENT_ERROR` and a request for `/audio.mp3`. Root cause: sample provenance includes the relative filename `audio.mp3`; the player incorrectly preferred that field over the known-track API route.

A new regression test failed with `audio.mp3` versus `/api/songs/sample-amber-after-hours/audio`. The player now derives music URLs exclusively from the local track ID. The same real-browser scenario was rerun **without regenerating successful sample audio** and passed: speech → Amber music → natural queue advance → skip pending intro. The failure was neither disguised as a server outage nor “fixed” by weakening pause/resume expectations.

A related adversarial state-machine test found that a delayed rejected `play()` promise from a failed speech decoder could overwrite the newer music state. The player now checks the request token, phase **and source** before handling a late rejection. A second regression distinguishes unsupported media from an autoplay-policy block. Both new tests failed before the fix and pass afterward.

### Independent review: asynchronous intent and retry admission

Three independently reproduced issues were fixed with failing regressions first. Actual app voice handlers now invalidate pending reads on clear/new selection, discard stale completions and handle failed reads without retaining the previous reference or filename. Deferred file-read tests inspect the actual outbound DJ request body. New-song and retry routes share a synchronous admission/reservation/task helper: no event-loop yield separates the three-job check from queue mutation. Concurrent offline ASGI requests test both a full queue and contention for its final slot, including unchanged rejected records and no rejected background tasks. Playback attempts now have a generation independent of track/source identity; deferred AbortError tests verify successful same-source resume still advances the queue and intentional pause does not report a browser block.

Only offline tests were rerun for this review-fix pass. No credential file, live service, real-browser generation flow or credential scan was accessed/run; prior live evidence is unchanged. Restart the local Python server to load the admission fix and refresh browser tabs for the JavaScript fixes.

### Generated output is not exact art direction

The Saturday Neon cover visibly contains invented sign lettering even though the FLUX prompt asked for no lettering. The topic specifically requests a neon sign, which invites text-like artifacts. We preserved the genuine model output, documented the limitation, and did not replace it with third-party imagery or claim perfect typography. Amber’s cover depicts an ensemble rather than exact piano-focused instrumentation; the warm rainy cafe concept is visible. Qwen sample lyrics also contain awkward wording (“Saturday night feels like a boot”). Human editorial/listening review is still useful; the app’s vocal review step exists precisely to let users improve drafts before generation.

### API contract differences investigated

- The music docs show a wrapper with `data.models`, but this live class instance returns an OpenAI-style `data` array with model IDs. The adapter handles both, and actual returned audio provenance identifies `acestep-v15-xl-turbo`.
- The endpoint file’s speech model is a human-friendly name. Live OpenAPI and authenticated `/info` specify the exact API model `chatterbox-v3`; the app uses that documented ID.
- Public speech `/info` initially returned HTTP 401; retry with the external class credentials succeeded. No upstream secret body or key was recorded.
- The generic browser harness requested user-profile debugging consent. Verification used a separate headless Chrome session instead, without granting that permission or driving the user’s existing profile.

## Design judgment

1. **Persist audio before cover work.** A cover outage should not destroy a successful recording. The cover-retry test confirms the exact audio bytes survive and music is not regenerated. The UI offers a neutral placeholder and an explicit art-only retry.
2. **One audio element plus invalidation tokens.** Speech and music cannot physically overlap within a tab. Explicit playback intent distinguishes “paused by user while loading” from “not yet received.” Request cancellation and stale-response/source/attempt guards are justified by 13 focused playback tests and previously observed real pause/skip/advance behavior.
3. **SQLite/files, local-only single worker.** This avoids an external database and keeps installation portable. Jobs are serialized locally and tracked by named states; restarts surface interruptions as retryable rather than leaving endless spinners. It is intentionally not a hosted, authenticated multi-user platform. No remote cancellation/recovery guarantee is made.
4. **A bounded local input/download boundary.** IDs map to media files; browser-provided paths are never read. Same-origin POST checks, loopback Host checks, a custom header, CSP, size limits, constrained class URLs and no redirects reduce the risk of a local browser app accidentally becoming a file reader or credential-forwarding proxy.

Visual self-audit: Explore composition, genuine album sleeves, conventional library/navigation/player, no feature-tile marketing grid, monument statistics, glass effects, accent rails or blue/purple tech gradients. Georgia headings and intentionally selected humanist system fonts support the warm/quiet brief. Small metadata is secondary; forms/buttons use labeled, keyboard-focusable controls. This is not a formal WCAG certification.

## Reproduce

Offline:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
node --test tests/*.test.mjs
```

Live service evidence (requires running configured app; generates brief speech, not replacement samples):

```bash
python -m scripts.live_smoke
```

Developer browser checks use system Chrome + Node’s native WebSocket, no Playwright download. Start a separate browser with `--headless=new --disable-gpu --remote-debugging-port=9227 --user-data-dir=<temporary-directory> http://127.0.0.1:8765`, then run:

```bash
node scripts/browser_verify.mjs
node scripts/browser_extra.mjs
node scripts/browser_instrumental.mjs
```

These are **live generation tests**: the main test creates a 12-second vocal record and the instrumental test a 10-second record in local runtime data. To rerun only playback after the main test, set `REUSE_GENERATED=1` before `node scripts/browser_verify.mjs` (PowerShell: `$env:REUSE_GENERATED='1'`). Browser evidence files are overwritten by each run. `browser_extra.mjs` creates clearly named synthetic/invalid reference files under `/tmp`, removes them in `finally`, and excludes them from the repo; this developer harness is macOS/Linux-oriented even though the application supports Windows paths.

`scripts/security_scan.py` reads the real external keys into memory, checks prospective Git files, prints only counts/paths and fails on literal matches. It does not copy keys into scan reports. Run it before every archive/release. The saved assignment contains explicitly marked security redactions, noted in README. The team must review these against the original before submission without publishing sensitive values.

## Outstanding, honestly unchecked

- Teammate installation from the **GitHub-downloaded ZIP**, meaningful contributions/reviews by all five teammates, issues/PR workflow, final commit/ZIP alignment, and the team’s own written findings.
- Native Windows installation/playback and hosted CI runs; macOS results do not establish either. CI is configured but not remotely executed in this pass.
- Human voice-reference quality, subjective musical/lyrical accuracy, listening-quality review of all samples, every duration/preset combination, Firefox/Safari/Edge behavior and formal accessibility audit.
- Unencrypted HTTP on the provided class endpoints, remote service retention, remote work continuing after local cancellation/restart and busy shared-server availability. These are not solved by localhost binding.
