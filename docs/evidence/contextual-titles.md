# Contextual automatic titles — issue #10

## Scope and architecture

Implemented on `feat/contextual-song-titles`, branched from a clean `fix/dj-timeout` working tree. No commits or pushes were made by the implementation agent.

The browser previously substituted the first 60 topic characters for a blank title, while `SongSpec` rejected an empty title. The form now sends blank titles unchanged; the API permits an omitted/blank title while retaining its 100-character maximum and all other field validation.

Only new tracks with blank/whitespace titles receive `title_status=pending`. Admission still reserves one of the existing three queued/generating slots synchronously, then returns HTTP 202. The existing serialized background generation job changes title state to `generating` and requests a title from the class Qwen text adapter before music. One overall `asyncio.timeout(15)` bounds the title request, independently of music/image timeouts. No new blocking endpoint, background task pool, or provider was added.

Qwen receives topic/style/mood/type and, for vocals only, the exact approved lyrics. The prompt requests an original concise title, not a copied description, with no clarification question. Generated title text must be nonblank, at most 100 characters, printable single-line text without HTML/Markdown delimiters. Explicit titles bypass this operation. Approved lyrics are not rewritten. Existing records are not renamed, including music retries after a title was already resolved.

Title-specific provenance is `title_source=Qwen class endpoint`, set only on title success. No new lyrics provenance is inferred from the title request. **Existing unrelated behavior remains unchanged:** admission already labels nonempty vocal lyrics as Qwen-generated when configured services are present, regardless of whether those lyrics were manually authored. Correcting that pre-existing metadata issue is outside this feature's scope; the new title operation does not add to it.

## RED → GREEN evidence

Each production behavior was introduced after executing its focused failing regression:

1. Contextual adapter: 2 failures (`Contextual title adapter missing`) → 2 passes.
2. Job integration: 4 failures (blank title HTTP 422; whitespace title not prepared) → 8 passes, including explicit-name compatibility.
3. Deadline/fallback: 2 failures (missing title deadline) → 10 passes. A never-completing async title request is cancelled using a shortened test deadline; the production constant is asserted to equal 15 seconds.
4. Output validation: 5 failures (`DID NOT RAISE ServiceError`) for oversized, HTML, Markdown, multiline, and control-character output → 16 passes. Blank output was already rejected by the shared text adapter.
5. Form submission: actual `spec()` returned the description instead of an empty title → 1 JavaScript pass after removing substitution.
6. Collection UI/copy: 4 failures for missing title preparation/fallback messages and outdated form copy → all 5 title JavaScript tests pass.

Additional compatibility coverage verifies three-slot admission while Qwen is blocked, unchanged field/vocal-lyrics validation, existing-record preservation, exact edited lyrics passed into music, instrumental/vocal behavior, explicit titles, and no re-titling during music retry.

Tests use temporary databases, offline service doubles and `httpx.MockTransport`; they never read endpoint credentials or call live class services. New JavaScript suite is explicitly included in the cross-platform CI file list.

## Final local verification

Executed from the repository:

```text
.venv/bin/python -m pytest -q
60 passed in 0.48s

node --test tests/player.test.mjs tests/voice.test.mjs tests/dj-deadline.test.mjs tests/titles.test.mjs
33 tests, 33 pass, 0 fail

git diff --check
exit 0
```

## Expected failure recovery

- Qwen transport failure, timeout, empty/invalid response: save `Untitled track`, mark `title_status=fallback`, and persist a fixed safe warning: “Automatic title unavailable. Using ‘Untitled track’; music generation continues.” No upstream body or generated markup is echoed.
- Audio generation continues normally after title failure. The warning remains visible in the collection even once audio and cover are ready.
- Title generation underway: collection says “Qwen is preparing your title…” rather than claiming music is already generating. Pending jobs show title preparation queued.
- Music fails after a successful title: existing Retry song reuses the chosen title. Cover-only retry never regenerates the title.
- Interrupted jobs retain the existing explicit restart-failure handling; retry can resume unresolved title preparation. No background migration renames existing library tracks.

## Remaining verification / handoff

No live Qwen call or real music regeneration was performed. The running server and user preview were not restarted or driven, and the user's library was not opened or modified. Parent should perform a title-only live Qwen check and rendered-browser review at a safe time, then handle server restart and the stacked PR against `fix/dj-timeout`. Contextual quality is model-dependent; the offline tests establish the prompt, bounded behavior, data flow and safe rendering, not live title quality.
