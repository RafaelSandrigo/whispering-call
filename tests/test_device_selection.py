import pytest

from fakes import FakeCudaProbe
from whispering_call.config import TranscriptionSettings
from whispering_call.device_selection import resolve_runtime


def settings(device: str, compute_type: str = "auto") -> TranscriptionSettings:
    return TranscriptionSettings(
        model="small",
        language="pt",
        device=device,
        compute_type=compute_type,
        beam_size=5,
        vad_filter=True,
    )


def test_auto_uses_gpu_when_cuda_is_available() -> None:
    choice = resolve_runtime(settings("auto"), FakeCudaProbe(available=True))

    assert choice.settings.device == "cuda"
    assert choice.settings.compute_type == "int8_float16"
    assert "GPU" in choice.message


@pytest.mark.parametrize("requested", ["auto", "cuda"])
def test_missing_cuda_falls_back_to_cpu_with_reason(requested: str) -> None:
    probe = FakeCudaProbe(available=False, reason="sem driver NVIDIA")

    choice = resolve_runtime(settings(requested), probe)

    assert choice.settings.device == "cpu"
    assert choice.settings.compute_type == "int8"
    assert "sem driver NVIDIA" in choice.message


def test_explicit_cpu_never_probes_the_gpu() -> None:
    probe = FakeCudaProbe(available=True)

    choice = resolve_runtime(settings("cpu"), probe)

    assert choice.settings.device == "cpu"
    assert probe.calls == 0


@pytest.mark.parametrize("gpu_only", ["int8_float16", "float16"])
def test_gpu_only_compute_type_is_replaced_on_cpu(gpu_only: str) -> None:
    choice = resolve_runtime(settings("cpu", gpu_only), FakeCudaProbe(available=False))

    assert choice.settings.compute_type == "int8"
    assert gpu_only in choice.message


def test_explicit_compute_type_is_kept_when_valid() -> None:
    gpu = resolve_runtime(settings("cuda", "float16"), FakeCudaProbe(available=True))
    cpu = resolve_runtime(settings("cpu", "int8_float32"), FakeCudaProbe(False))

    assert gpu.settings.compute_type == "float16"
    assert cpu.settings.compute_type == "int8_float32"
