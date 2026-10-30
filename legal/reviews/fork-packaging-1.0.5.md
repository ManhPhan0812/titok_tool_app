# HaizFlow fork 1.0.5 — scoped technical packaging review

Reviewer: Codex. Date: 2026-10-30 (Asia/Bangkok). This records this agent's
technical review, not independent legal, ownership or patent certification.

The user requested building and publishing a new fork release to
ManhPhan0812/titok_tool_app so their home installation can update. In this
conversation the user previously stated they have written author permission
to distribute their fork. That statement is retained as user-supplied
authorization; the permission document has not been independently examined.
Original author attribution, LICENSE and its restrictions remain unchanged.

Reviewed application baseline: 64b9352, with final resource archive pins and
release metadata bound to the final clean source commit in BUILD-INFO. Scope:
8 GiB installed / 6 GiB usable RAM admission, conservative CPU workloads and
warm-up policy below 12 GiB usable RAM, current CUDA architecture compatibility,
legacy Quadro K1000M CPU guidance, bilingual installation documentation and
installer requirement text. No dependency version, model checkpoint, voice
preview, font, artwork or media build recipe changes are introduced.

Rebuild CPU engine 18 so the worker policy is delivered. Existing pinned CUDA
19 and vision 9 remain unchanged. CPU protocol 1/runtime contract 7 and model
formats remain compatible. No GPU acceleration is claimed for K1000M; no
physical K1000M benchmark has been performed.

ThirdPartySources 1.0.5 is generated from the existing collected FFmpeg CLI,
engine and Qt/PySide source inputs. Verify the exact pinned source closures,
including the fork's existing locally built CLI FFmpeg binaries. Reused engine
media DLLs are individually checked against the pinned engine closure before
repackaging. Retain complete installed-wheel and bundled-component notices,
LGPL replacement instructions, original model restrictions, and public source
asset access. Do not package user projects, media, browser data or credentials.

Publication conditions: clean Core/bootstrap provenance; strict legal,
resource, lock and vulnerability gates; full source/QML tests; real new CPU
engine smoke/media/install acceptance; installer install/repair/uninstall/data
preservation acceptance; real 1.0.4-to-1.0.5 frozen update health/rollback/data
preservation; public asset digest and download checks. Conditions record work
to be completed before publication, not assertions that these tests have
already passed. Preserve previous immutable releases and the unsigned-build
caveat. Original/upstream installations need Setup once to join the fork
channel; existing fork 1.0.4 installations can use the in-app update.
