# HaizFlow fork 1.0.6 — scoped technical packaging review

Reviewer: Codex. Date: 2026-10-30 (Asia/Bangkok). This records a technical
packaging review, not independent legal, ownership or patent certification.

The user explicitly requested publishing this version to their fork. Their
earlier statement of written author permission for fork distribution persists;
the permission document has not been independently examined. Original author
attribution, LICENSE and its restrictions remain unchanged.

Scope: source changes following 45bf3e0 for optional Whisper Base DirectCompute
recognition on legacy GPUs. The final clean commit is bound in BUILD-INFO.
The UI requires an explicit Base model selection and explains its accuracy
tradeoff. GPU processing uses the native Direct3D 11 backend; language detection,
speech recovery, alignment, translation and voices use existing CPU backends.
This is not automatic hybrid routing for every task or support for running
all existing CUDA models on K1000M. No physical K1000M benchmark is claimed.

The unmodified Const-me/Whisper 1.12.0 CLI ZIP and pinned Whisper Base GGML model
are optional direct supplier downloads. They are not embedded or redistributed
inside Core or the engine packs. Payload sizes, SHA-256 and executable/DLL
member hashes are pinned. The exact upstream MPL-2.0 license and supplier/source
notice are included in licenses/; the CLI's original LZ4 notice is preserved.
Original model and third-party rights remain independent of HaizFlow's license.

No Python dependency version, existing model checkpoint, voice preview, font,
artwork or media build recipe is changed. Reuse the verified CPU 18, CUDA 19
and vision 9 archives at their existing pinned URLs. Existing CPU engine 18
consumes the transcribed-phase checkpoint and validates the final timing.

ThirdPartySources 1.0.6 uses the same collected FFmpeg CLI, engine and Qt/PySide
source closures, with the updated license inventory. Retain original source
access, LGPL replacement instructions, model restrictions and unsigned-build
caveats. No user projects, media, browser data or credentials enter packaging.

Publication conditions: full source and QML checks, dependency/resource/legal
gates, native frozen Core-to-CPU DirectCompute acceptance on the available
hardware with the adapter recorded, real 1.0.5-to-1.0.6 Full and Delta update
health/rollback/data preservation, installer acceptance with a private test
AppId, exact release asset digests and anonymous public update access. These
are conditions to complete before publication, not claims of completed tests.
Preserve previous immutable releases and the fork's own update channel.
