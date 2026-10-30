# Optional Whisper DirectCompute component

Supplier: [Const-me/Whisper](https://github.com/Const-me/Whisper).
Version: 1.12.0.
Source: <https://github.com/Const-me/Whisper/tree/c5515ace19066e938854b4b99e0c2e9bbc2eeb65>.
Corresponding source archive:
<https://github.com/Const-me/Whisper/archive/c5515ace19066e938854b4b99e0c2e9bbc2eeb65.zip>.

The unmodified upstream `cli.zip` is an optional user download from the pinned
1.12.0 GitHub release. HaizFlow does not bundle or repackage these binaries.
The source is licensed under Mozilla Public License 2.0; the exact license from
the pinned revision is retained in `WHISPER-DIRECTCOMPUTE-MPL-2.0.txt`.
Upstream copyright and third-party notices remain applicable. In particular,
`lz4.txt` from the original CLI ZIP is preserved alongside the temporary native
executable and library. Original authors retain all their rights.

The additional multilingual Base model is the unmodified `ggml-base.bin` from
`ggerganov/whisper.cpp` on Hugging Face at revision
`5359861c739e955e79d9a303bcbc70fb988958b1`, derived from OpenAI Whisper.
See the supplier model card and [OpenAI Whisper MIT license](https://github.com/openai/whisper/blob/main/LICENSE).
The model is an optional direct supplier download; no model weights or native
executables are committed in this repository.

Payload URLs, sizes, hashes and native member hashes are pinned in
`src/haizflow/core/directcompute.py`. Integration and limitations are documented
in `docs/legacy-gpu.md`.
