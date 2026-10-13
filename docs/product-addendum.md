# Approved product addendum

This supplements and does not replace any language in [the original assignment](original-assignment.md). Implementation choices were approved before the build. Verification status belongs in [evidence](testing.md), not in this requirements document.

## Product and interaction

- Working title **Jukebox**. Local Python application, browser UI, usable on macOS and Windows. No login or hosted storage; each installation has its own persistent library. Each browser tab has its own playback queue.
- Cozy vintage conventional music app, not a literal jukebox machine: warm wood-like neutrals, cream labels, brass accents and restrained amber/pastel color. Clear Collection / Create a song / DJ booth navigation; no assignment language or numbered assignment steps in the UI.
- Topic as free text, style and mood presets plus custom text, instrumental or vocal, documented duration bounds and a user-editable title.
- Vocal flow: Qwen drafts lyrics → user reviews/edits → explicit Generate sends edited lyrics unchanged. Instrumental flow skips lyrics. Generate one actual ACE-Step audio track and a new matching FLUX cover; download and persist both, never rely on temporary server URLs.
- If art fails, preserve playable audio and offer cover-only retry. Show honest named states, not invented percentages. Errors must be understandable, sanitized and recoverable.
- Play/pause/skip, automatic queue advance, no overlapping DJ and music. DJ on/off, personalities **Warm & Laid-back**, **Upbeat & Playful**, **Music Enthusiast**. Qwen writes brief song-specific commentary, Chatterbox speaks it. Default voice requires no upload; support ephemeral MP3/WAV references with consent guidance.
- Skip during speech or pending speech starts the associated song; skip during music advances the queue. Pausing, skipping, delayed responses, playback failures and autoplay restrictions must not cause stale speech or overlapping playback. A failed DJ request must continue music with a notice.

## Exact bundled sample concepts

1. **Amber After Hours** — instrumental; warm relaxed jazz, piano, brushed drums, bass; amber cafe and rainy-street cover.
2. **Saturday Neon** — vocal; upbeat cheerful retro soul-pop, meeting friends and dancing; coral/turquoise diner-sign cover.
3. **The Long Way Home** — vocal; cozy reflective acoustic folk, taking the scenic route home; winding country road at sunset cover.

Use actual class outputs, modest durations (30 seconds selected after consulting the documented limits), Qwen-generated lyrics for every vocal sample, and sanitized provenance with prompts, models and real generation timestamps. Validate audio decoding/duration and image display. No bundled third-party recordings, lyrics, images or reference voices.

## Services, privacy and boundaries

Only the required class text/image/music/speech services on ports 9001/9006/9007/9008, with credentials loaded server-side from an external file via `JUKEBOX_ENDPOINTS_FILE`. Never request port 9000. No paid services, secrets in tracked files, secrets in browser code, secrets in logs or secrets in submission artifacts. Runtime songs and test-only synthetic speech stay in ignored data; original samples are tracked separately.

Use asynchronous jobs, validated bounded input, local SQLite plus files, an allowlisted generated-media route, bounded uploads, same-origin side-effect protection and constrained outbound downloads (including redirects). Reference uploads must never be persisted by the app or included in a repository/ZIP. Synthetic app-generated speech may be used for a labeled test-only reference check; do not claim a human-reference quality test from it.

## Delivery and team obligations

README is the starting point: both-platform venv/pip setup, secure external configuration, launch/use, genuine browser screenshots, real feature/failure evidence, significant design choice justified by tests, investigated limitation, sample-generation explanation, reproducible dependency information and honest unchecked claims.

All **five teammates** must contribute meaningfully, review another teammate's work, organize substantial work through GitHub issues/PRs, and verify documentation in their own words. A teammate must install from the extracted GitHub ZIP using only its documentation and class credentials. Repository URL, submitted commit ID and GitHub-downloaded ZIP must refer to the same final version. Those human and submission steps are not satisfied by agent implementation or local tests. They remain pending until the team supplies evidence.

No commit/push, GitHub write or unrelated project modification is authorized in this implementation pass.
