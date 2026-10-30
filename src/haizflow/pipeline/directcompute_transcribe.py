"""Legacy-GPU ASR followed by the existing CPU alignment/timing pipeline.

The CPU engine's transcribed-phase checkpoint is the bridge. This works with
engine 18: no obsolete CUDA/Python stack and no AI packages in Core. Raw GPU
SRT is never published as timestamp-aligned output.
"""

from __future__ import annotations

import hashlib
import subprocess
import tempfile
import wave
import zipfile
from pathlib import Path

import srt

from haizflow.core.directcompute import CLI_FILES, adapter_hint, verify_payload
from haizflow.pipeline.process_registry import check_cancellation, communicate_process
from haizflow.services.recognition_progress import RecognitionProgress


def _run(command, video_id, *, timeout=None):
    check_cancellation(video_id)
    process = subprocess.Popen(command, stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    # The app's media deadline and kill-on-close job also cover this child.
    options = {"timeout_seconds": timeout} if timeout is not None else {}
    stdout, stderr = communicate_process(video_id, process, label="Whisper DirectCompute", **options)
    check_cancellation(video_id)
    return process.returncode, stdout, stderr


def _extract_cli(payload: Path, directory: Path) -> Path:
    # Never extract arbitrary archive paths or trust an executable from PATH.
    with zipfile.ZipFile(payload / "cli.zip") as archive:
        for name, (size, digest) in CLI_FILES.items():
            info = archive.getinfo(name)
            if info.file_size != size:
                raise RuntimeError("Whisper DirectCompute: invalid CLI payload.")
            data = archive.read(info)
            if hashlib.sha256(data).hexdigest() != digest:
                raise RuntimeError("Whisper DirectCompute: CLI checksum mismatch.")
            (directory / name).write_bytes(data)
    return directory / "main.exe"


def _adapter(executable: Path, hint: str, video_id: str) -> str:
    # Upstream returns 1 for --list-adapters, including successful enumeration.
    _code, output, errors = _run([str(executable), "--list-adapters"], video_id, timeout=20)
    names = [line.strip()[1:-1] for line in output.splitlines()
             if line.strip().startswith('"') and line.strip().endswith('"')]
    def normalized(name):
        return name.lower().replace("nvidia", "").replace("(r)", "").strip()
    selected = next((name for name in names if normalized(name) == normalized(hint)), "")
    if not selected:
        raise RuntimeError(f"DirectCompute không khởi tạo được GPU '{hint}'. "
                           "Kiểm tra driver NVIDIA hoặc chọn Whisper Small · CPU. " + errors[-400:])
    return selected


def _segments(path: Path, duration: float, language: str) -> list[dict]:
    result = []
    previous_end = 0.0
    for row in srt.parse(path.read_text(encoding="utf-8-sig")):
        start, end = row.start.total_seconds(), row.end.total_seconds()
        text = row.content.strip()
        if not text:
            continue
        if not (0 <= start < min(end, duration) and end <= duration + 0.5) or start < previous_end:
            raise RuntimeError("Whisper DirectCompute trả về mốc thời gian không hợp lệ.")
        result.append({"start": start, "end": min(end, duration), "text": text,
                       "language": language, "language_confidence": 1.0})
        previous_end = end
    if not result:
        raise RuntimeError("Whisper DirectCompute không nhận dạng được lời thoại.")
    return result


def _language_probe(audio_path: str, directory: Path, video_id: str, cpu_transcribe) -> tuple[str, float]:
    # The legacy D3D11 backend has no language detector. Run the existing CPU
    # recognizer on at most 30 s, then use that language for the full GPU pass.
    # The caller supplies a normalized mono 16 kHz PCM WAV; stream, don't load a
    # full movie's audio into Core memory. Preserve every WAV format parameter.
    probe = directory / "language.wav"
    with wave.open(audio_path, "rb") as source, wave.open(str(probe), "wb") as target:
        target.setparams(source.getparams())
        target.writeframes(source.readframes(min(source.getnframes(), source.getframerate() * 30)))
        duration = source.getnframes() / source.getframerate()
    _rows, language = cpu_transcribe(str(probe), str(directory / "language.json"), "auto", video_id,
                                    model_name="small-cpu")
    if not language or not language.isascii() or not language.isalpha() or len(language) > 3:
        raise RuntimeError("Không nhận diện được ngôn ngữ cho Whisper DirectCompute. Chọn Whisper Small · CPU.")
    return language, duration


def transcribe(audio_path, output_json_path, source_language, video_id, progress_callback=None,
               *, checkpoint_path=None, checkpoint_key="", cpu_transcribe):
    from haizflow.config import TMP_DIR
    from haizflow.core.hardware import detect_hardware_capabilities
    from haizflow.core.paths import models_dir
    from haizflow.services.video_store import log_to_video

    check_cancellation(video_id)
    checkpoint_key = "directcompute-base-v1:" + checkpoint_key
    Path(TMP_DIR).mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="directcompute-", dir=TMP_DIR) as temporary:
        directory = Path(temporary)
        checkpoint_path = checkpoint_path or str(directory / "recognition.json")
        # Same checkpoint format/model expected by the unmodified CPU worker;
        # the caller's key still includes the user's selected GPU model.
        checkpoint = RecognitionProgress(checkpoint_path, audio_path, model="small",
                                         language=source_language, key=checkpoint_key)
        if not checkpoint.reached("transcribed"):
            payload = verify_payload(models_dir())
            hint = adapter_hint(detect_hardware_capabilities())
            if not hint:
                raise RuntimeError("Không tìm thấy GPU NVIDIA cho Whisper DirectCompute. Chọn Whisper Small · CPU.")
            executable = _extract_cli(payload, directory)
            selected = _adapter(executable, hint, video_id)
            from haizflow.utils.ffmpeg import _binary

            audio = directory / "speech.wav"
            code, _stdout, errors = _run([_binary("ffmpeg"), "-hide_banner", "-loglevel", "error",
                "-nostdin", "-y", "-i", str(audio_path), "-vn", "-ac", "1", "-ar", "16000",
                "-c:a", "pcm_s16le", str(audio)], video_id)
            if code:
                raise RuntimeError("Không chuẩn bị được âm thanh cho Whisper DirectCompute. " + errors[-800:])
            if progress_callback:
                progress_callback("detecting_languages", "Đang nhận diện ngôn ngữ trên CPU")
            language, duration = _language_probe(str(audio), directory, video_id, cpu_transcribe)
            check_cancellation(video_id)
            # Outputs belong only to this disposable directory, never beside
            # the user's input or an earlier project's existing SRT.
            log_to_video(video_id, f"Whisper Base · DirectCompute GPU: {selected}; language: {language}. "
                         "Language detection and alignment use CPU.")
            if progress_callback:
                progress_callback("transcribing", f"Whisper Base · GPU {selected} (DirectCompute)")
            code, _stdout, errors = _run([str(executable), "--model", str(payload / "ggml-base.bin"),
                "--language", language, "--use-gpu", selected, "--threads", "2",
                "--output-srt", "--file", str(audio)], video_id)
            if code or not audio.with_suffix(".srt").is_file():
                raise RuntimeError("Whisper DirectCompute không chạy được trên GPU này. "
                                   "Kiểm tra driver NVIDIA hoặc chọn Whisper Small · CPU. " + errors[-1200:])
            rows = _segments(audio.with_suffix(".srt"), duration, language)
            check_cancellation(video_id)
            checkpoint.save("transcribed", rows, language)
        # Engine 18 skips the initial ASR pass, then applies the same CPU
        # speech recovery, alignment, language-switch and timestamp checks as
        # the existing pipeline. It alone publishes the final transcript.
        return cpu_transcribe(audio_path, output_json_path, source_language, video_id,
            progress_callback=progress_callback, model_name="small-cpu",
            checkpoint_path=checkpoint_path, checkpoint_key=checkpoint_key)
