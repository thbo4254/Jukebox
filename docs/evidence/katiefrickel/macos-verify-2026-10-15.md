# macOS Independent-Verification Report (katiefrickel)

**Date:** 2026-10-15
**Tester:** katiefrickel
**Platform:** macOS (Apple silicon, Python 3.14.7 via `python3`)
**How installed:** GitHub "Download ZIP" of the repository, extracted to a clean folder — no files from any development machine. Only the README and class credentials were used.
**Version tested:** ZIP of `feat/jukebox-mvp` (code identical to `main`; the only difference is main's merge commit). Local library `data/` and `class-endpoints.txt` kept outside the project folder per the README.

All three core features were tested **live against the class endpoints** (`class-endpoints.txt`). Timestamps in this report are local time (MDT).

---

## Feature 1 — Custom song generation

### Test 1a: Vocal track with AI lyrics
| | |
|---|---|
| **Input** | Topic: "A raccoon DJ spinning records on a midnight rooftop while neighborhood cats dance below"; Title: "Rooftop Raccoon Radio"; Style: Lo-fi beats; Mood: Dreamy & mellow; Duration: 12 s; Track type: **With vocals** |
| **Expected** | Qwen drafts lyrics for review; ACE-Step returns playable ~12 s audio; record added to the library; lyrics reviewed/editable before generation |
| **Actual** | ✅ Qwen returned a 277-character lyric draft within seconds (verse + chorus, matched the topic). I reviewed it in the editable text area, then clicked Generate. ACE-Step returned a **12.0 s stereo 48 kHz MP3 (192,812 bytes, ID3 header)**. The record appeared in the collection as `ready`, played immediately, and **survived a full server restart** (5 records still present). |

### Test 1b: Instrumental track
| | |
|---|---|
| **Input** | Topic: "First snow of the season falling on a quiet small-town main street"; Title: "First Snow on Main Street"; Style: Acoustic folk; Mood: Cozy & reflective; Duration: 10 s; Track type: **Instrumental** |
| **Expected** | No lyrics step; ACE-Step returns ~10 s playable audio marked instrumental |
| **Actual** | ✅ Generated in ~10 s; **10.0 s stereo 48 kHz MP3**; record flagged `instrumental: true`; added to library; plays correctly. |

## Feature 2 — Matching cover art

| | |
|---|---|
| **Input** | Same song concept as Test 1a (topic + style + mood); no custom cover prompt |
| **Expected** | A **new** FLUX cover reflecting the song's theme, displayed with the correct track |
| **Actual** | ✅ FLUX returned a 1,166,184-byte PNG (768×768 class of output). The collection card shows the cover beside the correct track. Visual review of the cover: a raccoon DJ at turntables on a rooftop, cats gathered around, city skyline, moon and stars — the lo-fi/dreamy vibe of the concept came through clearly. The instrumental track received its own distinct cover. |

## Feature 3 — Integrated AI DJ

| | |
|---|---|
| **Input** | DJ enabled in the DJ booth, persona "Upbeat & Playful", **default voice (no upload)**; queued the two generated tracks; Play |
| **Expected** | Qwen writes a song-specific intro and Chatterbox speaks it **before** each song; speech and music never overlap; the queue advances automatically |
| **Actual** | ✅ Full sequence observed and logged (2 s sampling of the audio element): `YOUR DJ IS GETTING READY` → `ON AIR · DJ INTRO` (**6.4 s / 7.5 s of spoken intro — each intro named its song**: "Drop it to the dreamy lo-fi…" / "Get cozy with 'First Snow…'") → `NOW SPINNING` (music) → auto-advance → next intro → next music. Speech and music were never playing at the same time — the app serializes both through one audio element, exactly as the README describes. |

### Player controls
- **Play/Pause:** works; pause preserved playback intent (an intro stayed loaded while paused, no loss of state).
- **Skip during a DJ intro:** pressed Skip ~3 s into an intro → the associated song started immediately (README says this is the intended behavior). ✅
- **Skip during music / queue auto-advance:** after a song finished, the next queued record started automatically with its own intro. ✅
- **Autoplay policy:** true to the README, a scripted (non-gesture) Play is held back by the browser, showing the actionable notice; a real mouse click plays immediately. The README documents this — confirmed in practice.

## Failure case: out-of-range duration

| | |
|---|---|
| **Input** | Duration set to **5 s** (below the documented 10–120 s range), then Generate |
| **Expected** | Client-side rejection; no job submitted; no record created |
| **Actual** | ✅ The UI rejected it with "Duration 10–120 seconds"; no server request; library count stayed at 5. |

---

## Documentation verification (findings, in my own words)

I followed the README from a cold machine and it held up:

1. **Setup on macOS was exactly as documented.** The ZIP install, venv creation, `pip install -r requirements.txt`, the `JUKEBOX_ENDPOINTS_FILE` env var, and `python -m jukebox` worked first try. Python 3.14.7 was accepted (README says 3.12+). The app binds only to `127.0.0.1:8765`.
2. **The README's player/DJ description is accurate.** Every status text it mentions ("waiting / creating music / painting the cover", "YOUR DJ IS GETTING READY", "ON AIR · DJ INTRO", "NOW SPINNING") is what actually appears. Skip semantics matched too.
3. **Bundled samples check out.** All three samples play and decode to the documented **30.0 s, stereo, 48 kHz**; covers display; metadata JSONs document their generation (Qwen lyrics passed unchanged to ACE-Step, seeds, timestamps).
4. **One data-consistency gap I noticed:** `GET /api/songs` reports `lyrics_model` / `image_model` for the bundled samples but **null for newly generated records**, even though those models were used (my generated records' lyrics clearly came from Qwen and covers from FLUX). Music provenance (model, seed, server time) is stored on generated records, but the lyric/cover model names aren't. It doesn't break anything, but persisting the model names at generation time would make the library metadata uniform — worth a small follow-up.
5. **Credentials stayed out of everything.** `class-endpoints.txt` lived in my home folder, not the project; `.gitignore` already blocks `class-endpoints*`, `data/`, `voice-references/`.

## Evidence artifacts

Screenshots, media and machine-readable logs for the tests above are in this folder:

- `01-collection-start.png` … `12-invalid-duration-rejected.png` — UI evidence for each step (form, lyrics review, generating, post-generation collection, player, DJ booth, skip, validation error)
- `generated-audio.mp3`, `generated-cover.png` — the actual generated media (SHA-256 of audio: `18b8c8c384e76531…`, 192,812 bytes; cover 1,166,184 bytes)
- `dj-sequence.json`, `skip-test.json` — timestamped audio-element state logs proving the DJ sequence and skip behavior

## Not tested by me (and why)

| Item | Who/what covers it |
|---|---|
| Windows install & run | Teammate (Maranda) — PR #3 reports a live Windows run of all three features |
| Voice-reference upload path | UI present and functional-looking; a teammate tested it with a permitted recording (screenshot in `docs/testing.md`); I used the required default-voice path |
| Durations beyond 30 s | README notes tested lengths are 10/12/30 s; the app caps at 120 s by design |
| Failure-recovery retries (Retry song / Retry cover) | Documented with screenshots in `docs/testing.md`; not specifically exercised in this session |
