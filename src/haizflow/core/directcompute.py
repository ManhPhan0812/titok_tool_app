"""Pinned Direct3D 11 Whisper payload; independent of the CUDA engine."""

from __future__ import annotations

import os
from pathlib import Path

PACK_ID = "model-whisper-directcompute"
MODEL_CHOICE = "base-directcompute"
CLI_VERSION = "1.12.0"
CLI_REVISION = "c5515ace19066e938854b4b99e0c2e9bbc2eeb65"
MODEL_REVISION = "5359861c739e955e79d9a303bcbc70fb988958b1"
CLI_FILES = {
    "main.exe": (206336, "c0acc438b28b9911f2b6d68a0998b6c96a7a3d509842b441d4f0616f32eecdd3"),
    "Whisper.dll": (576512, "41de3af338d54ab09a85f6e94a688b1b2a18f486188b10cd16157ac47897f1be"),
    "lz4.txt": (1311, "8b58c446121a109ccf32edc094bba3010a3d85e4ee3702950db55e4d3e87736c"),
}


def assets():
    from haizflow.services.model_bootstrap import ModelAsset

    return (
        ModelAsset("whisper-directcompute", "Whisper DirectCompute",
                   f"https://github.com/Const-me/Whisper/releases/download/{CLI_VERSION}/cli.zip",
                   "whisper-directcompute/cli.zip", 377919,
                   "baa9b70c824e50fe91f1858006a24b870b7637135659f17fc42beb1af57bd447"),
        ModelAsset("whisper-directcompute", "Whisper Base",
                   f"https://huggingface.co/ggerganov/whisper.cpp/resolve/{MODEL_REVISION}/ggml-base.bin?download=true",
                   "whisper-directcompute/ggml-base.bin", 147951465,
                   "60ed5bc3dd14eea856493d334349b405782ddcaf0028d4b5df4088345fba2efe"),
    )


def verify_payload(root: Path) -> Path:
    from haizflow.core.model_integrity import verify_pack_assets

    verify_pack_assets(root, PACK_ID, CLI_VERSION + ":" + MODEL_REVISION, assets())
    return root / "whisper-directcompute"


def adapter_hint(capabilities) -> str:
    """A candidate only; the native D3D11 adapter list must confirm it later.

    Old drivers can expose the adapter through CIM but not nvidia-smi/CUDA.
    Never use CUDA availability or the modern engine's VRAM floor here.
    """
    if capabilities is None:
        return ""
    names = (getattr(capabilities, "cuda_name", ""),
             *getattr(capabilities, "detected_graphics", ()),
             getattr(capabilities, "active_display_gpu_name", ""))
    candidates = [str(name).strip() for name in names
                  if "nvidia" in str(name).lower() or "quadro" in str(name).lower()]
    return next((name for name in candidates if "k1000m" in name.lower()), next(iter(candidates), ""))


def validate_hardware(capabilities, *, language="vi") -> tuple[bool, str]:
    from haizflow.core.hardware import validate_processing_device

    if os.name != "nt" or not adapter_hint(capabilities):
        return False, ("Whisper DirectCompute cần Windows và GPU NVIDIA hỗ trợ Direct3D 11."
                       if language == "vi" else "Whisper DirectCompute requires Windows and an NVIDIA Direct3D 11 GPU.")
    # All remaining stages use CPU. Native device creation, not the adapter
    # name alone, establishes whether the installed driver actually works.
    return validate_processing_device("cpu", capabilities, language=language)
