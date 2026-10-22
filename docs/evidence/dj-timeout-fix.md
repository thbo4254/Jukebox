# Bounded DJ deadline fix — execution evidence

AI-assisted implementation and verification, 2026-10-18. This is execution evidence, not independent human peer review. GitHub publication/PR/comments are delegated to the parent agent; this implementation session did not commit, push, or create a PR.

## Scope and baseline

- Initial `git status --short --branch`: `## main...origin/main` (clean).
- `git switch -c fix/dj-timeout`: `Switched to a new branch 'fix/dj-timeout'`. No existing branch overwritten.
- Starting commit: `bd4e51c Merge PR #5: polish`.
- Baseline command: `.venv/bin/python -m pytest -q && node --test tests/*.test.mjs`.
- Baseline output: `34 passed in 0.42s`; Node `tests 16`, `pass 16`, `fail 0`, `cancelled 0`, `duration_ms 58.019042`.

### Diagnosis, not a new live outage claim

User reported successful **Rainy Sunday** generation followed by DJ preparation stuck for **more than three minutes**. Prior diagnostic session reported:

| Prior live probe | Observed result |
| --- | --- |
| Qwen brief DJ intro | No usable response before cancellation at **44.002s** |
| Qwen `/v1/models` | No usable response before cancellation at **44.002s** |
| Chatterbox default voice | Completed in **1.252s**; decoded audio duration **2.360s** |

Those are prior live observations, not fixtures or fresh probes in this change. They support a problem on the observed text-service path, not proof of a global or permanent Qwen outage. Endpoint/network/proxy/server causes cannot be distinguished from this evidence. The precise cause of the historical user request is not known.

Code trace: `Services.dj` awaits text then speech. Its shared HTTPX timeout is 300 seconds per operation/inactivity, not a DJ-wide wall-clock budget. The API previously awaited the whole DJ call without a total deadline; the player awaited the request without a timer. Existing music fallback ran only when that request rejected. `/api/status` reports configuration, not upstream health.

Ranked explanations: (1) absent DJ deadline lets an upstream stall keep the player loading; (2) stalled local fetch can independently do the same; (3) playback-state races could suppress fallback. Offline tests below isolate (1)/(2) and preserve race guards for (3). No new live upstream requests were made.

## Narrow implementation

- `jukebox/app.py`: `DJ_TIMEOUT_SECONDS=15`; one `asyncio.timeout` surrounds the **entire** `service.dj` call, including text plus speech. Timeout returns HTTP **504** with only `DJ preparation timed out. Continue with music or retry playback.`
- `jukebox/static/player.js`: a **20,000 ms** DJ preparation budget surrounds the existing callback (fetch, response body, audio conversion). Race the request against cancellation/deadline, abort the request on expiry, and use the existing music fallback. Racing ensures even a non-cooperative never-settling callback cannot hold the player forever.
- Timer and abort listener are removed in `finally`, before awaiting audio playback. Skip/next/DJ-off cancel promptly. Existing token and pause guards remain intact. Late private speech blob URLs are revoked, including same-turn resolution/cancellation races.
- No change to `services.py`, global HTTPX timeout, music/image/lyrics generation deadlines, voice selection handling, saved library, or existing media.
- Browser deadlines run when the browser event loop is scheduled (background-tab throttling or a frozen event loop can delay JavaScript timers); this is not a hard real-time guarantee.

## RED → GREEN execution record

Commands below ran in the repository root. Output excerpts are verbatim meaningful assertions/summaries from actual runs; timings are observed, not targets. No result is simulated as if it were live service success.

### 1. Server: never-settling DJ must return safe 504

Test added **before** server implementation: `test_dj_deadline_cancels_stalled_service_and_returns_safe_504` in `tests/test_dj.py`. ASGI request uses a never-resolving asynchronous DJ fixture, a 10 ms injected DJ budget, and a 200 ms outer watchdog so the old bug fails fast. Also asserts cancellation reaches the fixture and no files other than the library database are persisted.

RED command (exit **1**):

```sh
.venv/bin/python -m pytest -q tests/test_dj.py -k deadline --tb=short
```

```text
E   asyncio.exceptions.CancelledError
E   TimeoutError
E   AssertionError: DJ request stayed pending beyond its total deadline
E   assert False
FAILED tests/test_dj.py::test_dj_deadline_cancels_stalled_service_and_returns_safe_504
1 failed, 1 deselected in 0.47s
```

After adding the server deadline, same command GREEN (exit **0**):

```text
.                                                                        [100%]
1 passed, 1 deselected in 0.23s
```

### 2. Browser player: never-resolving request must abort and start music

Added `tests/dj-deadline.test.mjs` before browser implementation. It runs the real player in a VM with a manual timer queue, checking the production delay is exactly 20,000 ms. The initial test checks abort, music phase/source, one play attempt, timeout notice, and zero remaining timers. No real 20-second wait.

RED command (exit **1**):

```sh
node --test tests/dj-deadline.test.mjs
```

```text
✖ never-resolving DJ aborts at 20 seconds and starts music exactly once (2.413958ms)
ℹ tests 1
ℹ pass 0
ℹ fail 1
ℹ cancelled 0
ℹ duration_ms 40.385333
AssertionError [ERR_ASSERTION]: Expected values to be strictly deep-equal:
+ []
- [
-   20000
- ]
```

After adding the deadline/race/finally cleanup, same command GREEN (exit **0**):

```text
✔ never-resolving DJ aborts at 20 seconds and starts music exactly once (2.096458ms)
ℹ tests 1
ℹ pass 1
ℹ fail 0
ℹ cancelled 0
ℹ duration_ms 36.591375
```

### 3. Late results, Skip, pause, queue advance, cleanup

Next tests added before late-result cleanup. The initial deadline implementation correctly kept music playing but leaked a late-created speech blob. This is a regression induced by racing away from the original callback, caught before completion.

Command: `node --test tests/dj-deadline.test.mjs`.

RED (exit **1**):

```text
✖ late DJ resolution after timeout cannot replace music and releases its blob (2.473583ms)
✖ late DJ resolution after skip cannot replace music and releases its blob (0.738667ms)
✖ late DJ resolution after pause-timeout cannot replace music and releases its blob (0.469834ms)
✖ late DJ resolution after timeout-skip-next cannot replace music and releases its blob (0.954667ms)
✔ DJ timer is cleaned up on success (0.420042ms)
✔ DJ timer is cleaned up on failure (1.56475ms)
✔ DJ timer is cleaned up on skip (0.477708ms)
✔ DJ timer is cleaned up on next (0.267167ms)
✔ DJ timer is cleaned up on disable (0.303917ms)
✔ never-resolving DJ aborts at 20 seconds and starts music exactly once (0.444834ms)
ℹ tests 10
ℹ pass 6
ℹ fail 4
ℹ cancelled 0
ℹ duration_ms 45.236666
```

Each failed assertion expected `['blob:late-private-speech']` to have been revoked; actual was `[]`. Supplemental success/failure/Skip/next/DJ-off cleanup assertions passed immediately, verifying behavior already introduced in step 2 rather than representing separate RED cycles.

After revoking abandoned late result URLs, GREEN (exit **0**):

```text
ℹ tests 10
ℹ pass 10
ℹ fail 0
ℹ cancelled 0
ℹ duration_ms 44.163666
```

Intermediate full-suite command: `node --test tests/dj-deadline.test.mjs && .venv/bin/python -m pytest -q && node --test tests/*.test.mjs` (exit **0**). Output: `35 passed in 0.40s`; Node `tests 26`, `pass 26`, `fail 0`, `cancelled 0`, `duration_ms 53.304125`.

### 4. Same-event-loop-turn resolution vs timeout/Skip

Added two tests before strengthening the late-result guard. A callback can resolve immediately before cancellation, queuing its continuation before `finally` marks the request settled. The guard must also inspect the aborted signal.

RED command (exit **1**):

```sh
node --test --test-name-pattern='same turn' tests/dj-deadline.test.mjs
```

```text
✖ DJ resolving in same turn as timeout releases its blob (2.352042ms)
✖ DJ resolving in same turn as skip releases its blob (0.523417ms)
ℹ tests 2
ℹ pass 0
ℹ fail 2
ℹ cancelled 0
ℹ duration_ms 42.531917
```

Both expected `['blob:same-turn']`; actual was `[]`. After checking `settled || controller.signal.aborted`, same command GREEN (exit **0**):

```text
✔ DJ resolving in same turn as timeout releases its blob (2.766583ms)
✔ DJ resolving in same turn as skip releases its blob (0.51325ms)
ℹ tests 2
ℹ pass 2
ℹ fail 0
ℹ cancelled 0
ℹ duration_ms 38.23325
```

## Real browser, controlled stalled HTTP request

This is an **offline failure injection**, not an upstream Qwen recovery or outage probe. Chrome was launched headlessly with a fresh temporary profile on CDP port 9231 and autoplay allowed. The existing debugging port 9227 was unavailable (`curl` exit 7), so no existing browser session was reused. The script creates and closes its own tab, leaving the user's preview untouched.

Reproduction setup:

```sh
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --disable-gpu --remote-debugging-port=9231 --user-data-dir="$(mktemp -d /tmp/jukebox-dj-timeout-chrome.XXXXXX)" --autoplay-policy=no-user-gesture-required about:blank
# Run Chrome as a managed background process, then in another shell:
node scripts/browser_dj_timeout.mjs
```

Browser observed: **Chrome/155.0.8059.80**. Script intercepts `/api/dj/*` at the browser request stage and deliberately never forwards it; the server/upstream never receive the DJ request. It loads the actual UI, clicks a bundled sample's Play button, manually fires only the 20-second timer, and checks the real media element is playing with advancing time. Audio is muted. No generated records or voice references are written. Full output (exit **0**):

```json
{
  "test": "controlled stalled DJ fetch; manually fired 20s timer",
  "intercepted": 1,
  "before": {
    "phase": "loading",
    "label": "YOUR DJ IS GETTING READY",
    "delays": [
      20000
    ]
  },
  "after": {
    "phase": "music",
    "label": "NOW SPINNING",
    "aborted": true,
    "timers": 0,
    "notice": "DJ unavailable: DJ preparation timed out. Continuing with music.",
    "playing": true,
    "advanced": true
  },
  "uncaughtErrors": []
}
```

No screenshots or unrelated JSON evidence were overwritten. The existing local server was not restarted for this test: static JavaScript is served from disk, while server timeout verification used fresh in-process ASGI apps.

## Final full regression run and limitations

Command:

```sh
.venv/bin/python -m pytest -q && node --test tests/*.test.mjs && git diff --check && .venv/bin/python scripts/security_scan.py
```

Actual test results before the final optional scanner invocation:

```text
...................................                                      [100%]
35 passed in 0.38s
ℹ tests 28
ℹ suites 0
ℹ pass 28
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 54.388
```

`git diff --check` succeeded with no output. The combined command then exited **1** because the optional scanner invocation failed at import:

```text
ModuleNotFoundError: No module named 'jukebox'
```

The scanner did **not** run its scan. Inspection showed its main function loads configured credential values; it was intentionally **not** retried with a corrected Python path, respecting the task's no-credential-read scope. This is not a claimed successful credential scan. No credential values were read or printed during this implementation.

A final clean verification (without the optional scanner) also passed, exit **0**:

```sh
git diff --check && git status --short --branch && git diff -- jukebox/app.py jukebox/static/player.js tests/test_dj.py && .venv/bin/python -m pytest -q && node --test tests/*.test.mjs
```

```text
35 passed in 0.40s
ℹ tests 28
ℹ suites 0
ℹ pass 28
ℹ fail 0
ℹ cancelled 0
ℹ skipped 0
ℹ todo 0
ℹ duration_ms 47.693792
```

Coverage includes the original privacy tests, playback-attempt/version guards, queue behavior, DJ-off, autoplay/decode fallback, server validation, admission control and the new stalled-request/deadline/race cases. New browser fixture output is separate from prior live endpoint observations.

**Deployment handoff:** restart the local Python app after review to activate the new server-side 15-second deadline; reload the page to load the new player code. The existing running process and the user's Rainy Sunday/library were left untouched. No live post-fix upstream success is claimed.
