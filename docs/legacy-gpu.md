# Whisper on Quadro K1000M and older GPUs

Available starting with 1.0.6. The 1.0.5 installer does not include this feature.
This release provides an explicit legacy-GPU recognition option, not automatic
hybrid routing for every AI task.

The optional **Whisper Base · GPU cũ (DirectCompute)** recognition choice uses
Direct3D 11 compute shaders instead of CUDA. It can be selected while the
application's processing device remains **CPU**. Translation, language detection,
timestamp alignment, speech recovery and voice synthesis continue using CPU.
The existing CPU engine 18 is sufficient; the modern CUDA engine is not required.

K1000M is a candidate for this backend even if its old NVIDIA driver cannot
answer `nvidia-smi` queries. The installed driver must expose the actual NVIDIA
adapter to Direct3D 11. The native CLI enumerates adapters and selects the exact
matching name, so an Optimus laptop cannot silently use its Intel adapter or
Microsoft's software renderer instead. Driver/device-creation failures explain
how to switch back to Whisper Small CPU.

## Using the mode

1. In **Cài đặt → Chung**, keep **Bộ xử lý → CPU → Áp dụng**.
2. In **Gói tài nguyên**, install **Whisper Base · GPU cũ (DirectCompute)**.
   Its install plan also includes Whisper Small and the CPU engine, needed for
   automatic language detection and alignment. Existing verified files are reused.
   The additional Base model and CLI download is about 148 MB.
3. Select **Whisper Base · GPU cũ (DirectCompute)** for speech recognition in the
   automatic, manual or batch project. Use **HY-MT2 CPU · Q4** and a CPU voice.

Base is a smaller model than Small and may be less accurate. This is an explicit
model selection, not a change to existing projects or their Small/Turbo defaults.
There is no speed guarantee on K1000M. For short clips, CPU language detection,
model loading and alignment may outweigh any GPU benefit. At least 8 GiB installed
RAM and 6 GiB usable RAM are still required, together with the existing live RAM
and commit headroom for each CPU stage.

Whisper Turbo, full HY-MT2 GPU and GPU voices still require the modern CUDA
engine's supported architecture and memory. DirectCompute does not enable those
models on K1000M.

## Execution and resume

Core decodes the source media to a private PCM WAV using the bundled FFmpeg.
The CPU recognizer detects language from at most the first 30 seconds. The native
DirectCompute process transcribes the full recording in that language. Its SRT
is validated and stored only as a **transcribed** phase checkpoint. The existing
CPU worker then aligns the recognized text, checks language switches and applies
the normal timestamp invariants before publishing the final transcript. There is
no claim that the native SRT alone is aligned output. Clips with no recognizable
speech in the opening language sample can fail detection; use Whisper Small CPU
for those clips.

Checkpoints are bound to source file state, model choice and policy. Resuming a
transcribed/recognized/aligned/complete checkpoint skips GPU recognition. Native children use
the application's cancellation and Windows kill-on-close process ownership.
Temporary audio, binaries and SRT remain in the task's private temporary folder.

## Pinned suppliers and validation

- [Const-me/Whisper 1.12.0](https://github.com/Const-me/Whisper/releases/tag/1.12.0),
  source `c5515ace19066e938854b4b99e0c2e9bbc2eeb65`.
  CLI ZIP SHA-256 `baa9b70c824e50fe91f1858006a24b870b7637135659f17fc42beb1af57bd447`.
  Requires Windows x64, a Direct3D 11 GPU and a CPU with AVX/F16C.
- [Whisper Base GGML](https://huggingface.co/ggerganov/whisper.cpp/tree/5359861c739e955e79d9a303bcbc70fb988958b1),
  model SHA-256 `60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe`.
- Model and ZIP are downloaded by the existing resource manager and verified
  against their sizes and SHA-256 hashes. Only the three pinned CLI members are
  extracted; executable and DLL bytes are checked independently before launch.
  There is no download or Python package installation when processing starts.
- A real native recognition smoke test passed on Intel UHD Graphics 630 with
  the pinned Base model (about 327 MB GPU allocations reported by the backend).
  The complete GPU-to-CPU hand-off also passed using the unmodified frozen CPU
  engine 18, with a final English transcript carrying the existing validated
  alignment timing contract. The final test took about 74 seconds for the
  11-second JFK sample, including two fresh CPU worker startups; this is a
  compatibility check, not evidence of a speed improvement.
  This validates the DirectCompute route, **not physical K1000M performance**.
  K1000M routing, rejection of software/other adapters, payload corruption,
  timestamp validation and phase-resume behavior have automated regression tests.

## Distribution

The unmodified CLI ZIP and model are optional downloads directly from their
upstream suppliers. They are not embedded in the application or CPU engine.
Retain [the MPL-2.0 license](../licenses/WHISPER-DIRECTCOMPUTE-MPL-2.0.txt),
[supplier notice](../licenses/WHISPER-DIRECTCOMPUTE-NOTICE.md) and the `lz4.txt`
notice inside the original archive. Whisper model licensing is independent of
the application license.
