# Original assignment — text extraction with a required identifier redaction

The original language below is retained as extracted with pypdf, with limited security redactions marked explicitly. Every other extracted word is unchanged. Page delimiters are editorial. The original PDF remains outside the repository. The team must review the redactions against the original before submission without copying sensitive values into public files. The [product addendum](product-addendum.md) supplements, never replaces, these requirements.

## PDF page 1

```text
MBAX [REDACTED IDENTIFIER] Assignment 3
Build an AI Jukebox
Work with your teams. The starter prompt has been simplified to its essence. You must
retain all existing language, but are encouraged to critically review the prompt and
add instructions before beginning your build. Your team is responsible for turning the
requirements below into a complete, tested app, making design decisions, and checking
the agent's work.
Using Hermes: After reviewing the starter prompt and making any additions, paste or
attach your version. You may then need to say: "Build the app described in this prompt."
Starter Prompt
# Overarching Task: Build an AI Jukebox
Build an app that (1) generates customizable songs, (2) generates 
matching cover art, and (3) plays a song collection with AI-generated 
spoken DJ commentary between tracks.
# Required Class Services
- Qwen3.6-35B-A3B on port 9001 for text generation.
- FLUX.2 klein 4B on port 9006 for cover art.
- ACE-Step 1.5 XL Turbo on port 9007 for music.
- Chatterbox Multilingual V3 on port 9008 for DJ speech.
Use the supplied class-endpoints.txt for connection details, or ask our 
team if it is unavailable. Follow each service's documented request 
format. Use these class services for the required features. You may use 
other class endpoints for optional features, but the core app must work 
with class services and credentials alone. Do not use paid services for 
any app features, including optional features. Do not use port 9000 for 
app requests.
# Safeguards
- Keep credentials server-side and out of GitHub, submission archives, 
browser code, logs, and documentation. Use placeholders in configuration 
examples.
- Never commit user uploads or voice-reference recordings to GitHub or 
include them in submission archives.
- Do not bundle third-party music, lyrics, cover art, or voice samples 
with the app.
```

## PDF page 2

```text
Required Features
I must be able to deploy your app from the submitted ZIP and successfully test all
three core features using the class endpoints.
Core feature What I must be able to do
1. Custom 
song 
generation
Choose a song's style, mood, and duration; generate playable audio 
with ACE-Step; and add it to the library. Support instrumental and 
vocal tracks, with AI-generated lyrics for vocal tracks.
2. Matching 
cover art
Generate a new FLUX cover for each custom song and see it 
displayed with the correct track. The artwork should reflect the song's 
theme, style, or mood.
3. Integrated 
AI DJ
Hear song-specific commentary written by Qwen and spoken by 
Chatterbox between queued songs. Use the default voice without an 
upload, or upload an MP3 or WAV reference to customize the DJ's 
voice.
Include three ready-to-play sample songs with titles and covers, generated in advance
using the class endpoints. Any lyrics used in the sample songs must be AI-generated.
Include these assets with the app, following the safeguards above. Newly generated songs
must join the playable library and remain available during the session.
Provide play/pause and skip controls. After playback starts, the queue must advance
automatically, with DJ speech and music playing in sequence without overlap. Show
generation status and understandable errors, and allow users to recover from failed
requests.
Documentation and Evidence
Use README.md as the starting point for your documentation and report. Screenshots
should be included to illustrate the app's interface and core features. Include:
Setup and use: Dependencies, additional software, endpoint configuration, how to
supply credentials securely, launch instructions, and how to exercise the three core
features. Include configuration examples without credentials.
Test results: Record inputs, expected behavior, and actual results for the three core
features and at least one failure case. Identify unresolved problems and clearly
distinguish completed tests from unchecked claims.
Design judgment: Explain one important design choice and justify it with evidence
from your testing. Discuss one limitation or failure you investigated and what you
learned.
```

## PDF page 3

```text
Your team must verify the documentation against the finished app and explain its findings in
its own words.
Submit and Be Ready for Independent Testing
Submit one shared GitHub repository link, the commit ID being submitted, and a ZIP
downloaded from GitHub for that same version per team on Canvas. The repository
must be accessible to me when you submit and remain accessible through grading.
Private repositories are acceptable if you grant me access. I will grade the version identified
in your final submission before the assignment closes.
The ZIP must include all code, dependency information, configuration examples,
documentation, and the actual generated sample audio and image files needed to run the
app. Exclude credentials, user uploads, and voice-reference recordings from all
submitted files.
Have a teammate install and run the app from the extracted ZIP using only your
documentation and class credentials. Verify that all three core features work. Resolve
missing files, undocumented setup steps, and dependencies on files that exist only on your
development machine before submitting.
Use GitHub issues and pull requests to organize and review substantial work. Every
teammate must make a meaningful contribution and review a teammate's work.
Grading will consider factors such as:
Functionality is graded from what I can reproduce in the submitted app. Screenshots
and descriptions do not substitute for working features.
Sample generation: Explain how the sample songs, lyrics, and covers were
generated.
Independent deployment and working core features.
Usability and reliability.
Documentation, test evidence, and design judgment.
```