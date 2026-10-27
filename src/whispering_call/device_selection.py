"""Escolhe dispositivo e ``compute_type`` reais a partir da config e da máquina.

Só GPUs NVIDIA aceleram o CTranslate2; Intel integrada e AMD (no Windows) caem
em CPU. Por isso ``device = "auto"`` (padrão) tenta CUDA e, se não houver, usa
CPU em vez de falhar.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from whispering_call.config import TranscriptionSettings
from whispering_call.cuda_runtime import CudaProbe, CudaStatus

AUTO = "auto"
GPU_COMPUTE_TYPE = "int8_float16"
CPU_COMPUTE_TYPE = "int8"
# Tipos com "float16" só existem em GPU; em CPU o CTranslate2 recusa.
GPU_ONLY_MARKER = "float16"


@dataclass(frozen=True)
class RuntimeChoice:
    settings: TranscriptionSettings
    message: str


def resolve_runtime(settings: TranscriptionSettings, probe: CudaProbe) -> RuntimeChoice:
    """Devolve as settings com ``device``/``compute_type`` concretos e um aviso.

    Exemplo::

        choice = resolve_runtime(config.transcription, probe)
        choice.settings.device  # "cuda" ou "cpu"
    """
    if settings.device == "cpu":
        return _choose_cpu(settings, cuda=None)
    cuda = probe.status()
    if cuda.available:
        return _choose_gpu(settings, cuda)
    return _choose_cpu(settings, cuda)


def _choose_gpu(settings: TranscriptionSettings, cuda: CudaStatus) -> RuntimeChoice:
    compute_type = (
        GPU_COMPUTE_TYPE if settings.compute_type == AUTO else settings.compute_type
    )
    resolved = replace(settings, device="cuda", compute_type=compute_type)
    message = (
        f"Transcrição na GPU ({cuda.reason}): modelo {settings.model}, {compute_type}."
    )
    return RuntimeChoice(resolved, message)


def _choose_cpu(
    settings: TranscriptionSettings, cuda: CudaStatus | None
) -> RuntimeChoice:
    compute_type = _cpu_compute_type(settings.compute_type)
    resolved = replace(settings, device="cpu", compute_type=compute_type)
    message = f"Transcrição na CPU: modelo {settings.model}, {compute_type}."
    if cuda is not None:
        message += f" GPU CUDA indisponível: {cuda.reason}."
    if compute_type != settings.compute_type and settings.compute_type != AUTO:
        message += (
            f" compute_type {settings.compute_type!r} não existe em CPU;"
            f" usando {compute_type!r}."
        )
    return RuntimeChoice(resolved, message)


def _cpu_compute_type(requested: str) -> str:
    if requested == AUTO or GPU_ONLY_MARKER in requested:
        return CPU_COMPUTE_TYPE
    return requested
