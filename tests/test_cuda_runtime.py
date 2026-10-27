from collections.abc import Callable
from pathlib import Path

from fakes import FakeNativeLibraryLoader
from whispering_call.cuda_runtime import (
    SystemCudaProbe,
    load_until_stable,
    register_nvidia_libraries,
)


def make_package(root: Path, subfolder: str, library_names: list[str]) -> Path:
    library_folder = root / subfolder
    library_folder.mkdir(parents=True)
    for name in library_names:
        (library_folder / name).write_bytes(b"")
    return root


def test_linux_preloads_every_shared_object(tmp_path: Path) -> None:
    cublas = make_package(
        tmp_path / "cublas", "lib", ["libcublas.so.12", "libcublasLt.so.12"]
    )
    loader = FakeNativeLibraryLoader({"nvidia.cublas": [cublas]})

    folders = register_nvidia_libraries(loader, "linux")

    assert folders == [cublas / "lib"]
    assert sorted(loader.loaded) == ["libcublas.so.12", "libcublasLt.so.12"]
    assert loader.dll_folders == []


def test_windows_registers_bin_folder_without_loading(tmp_path: Path) -> None:
    cudnn = make_package(tmp_path / "cudnn", "bin", ["cudnn64_9.dll"])
    loader = FakeNativeLibraryLoader({"nvidia.cudnn": [cudnn]})

    register_nvidia_libraries(loader, "win32")

    assert loader.dll_folders == [cudnn / "bin"]
    assert loader.loaded == []


def test_missing_packages_register_nothing() -> None:
    loader = FakeNativeLibraryLoader({})

    assert register_nvidia_libraries(loader, "linux") == []


def test_load_until_stable_retries_out_of_order_dependencies() -> None:
    # libcudnn_adv vem antes alfabeticamente, mas depende de libcudnn_ops.
    loader = FakeNativeLibraryLoader(
        {}, requires={"libcudnn_adv.so.9": "libcudnn_ops.so.9"}
    )

    never_loaded = load_until_stable(
        loader, [Path("libcudnn_adv.so.9"), Path("libcudnn_ops.so.9")]
    )

    assert never_loaded == []
    assert loader.loaded == ["libcudnn_ops.so.9", "libcudnn_adv.so.9"]


def test_load_until_stable_returns_libraries_that_never_load() -> None:
    loader = FakeNativeLibraryLoader({}, broken=frozenset({"libquebrada.so"}))

    never_loaded = load_until_stable(loader, [Path("libok.so"), Path("libquebrada.so")])

    assert never_loaded == [Path("libquebrada.so")]
    assert loader.loaded == ["libok.so"]


def counting(value: int) -> Callable[[], int]:
    return lambda: value


def failing_count() -> int:
    raise OSError("cudart64_12.dll não encontrada")


def test_probe_reports_gpu_when_driver_sees_devices(tmp_path: Path) -> None:
    cudnn = make_package(tmp_path / "cudnn", "bin", ["cudnn64_9.dll"])
    loader = FakeNativeLibraryLoader({"nvidia.cudnn": [cudnn]})

    status = SystemCudaProbe(loader, "win32", counting(1)).status()

    assert status.available
    assert loader.dll_folders == [cudnn / "bin"]


def test_probe_on_windows_requires_pip_nvidia_packages() -> None:
    status = SystemCudaProbe(FakeNativeLibraryLoader({}), "win32", counting(1)).status()

    assert not status.available
    assert "uv sync --extra gpu" in status.reason


def test_probe_on_linux_accepts_system_cuda_without_pip_packages() -> None:
    status = SystemCudaProbe(FakeNativeLibraryLoader({}), "linux", counting(1)).status()

    assert status.available


def test_probe_without_nvidia_device_is_unavailable(tmp_path: Path) -> None:
    cudnn = make_package(tmp_path / "cudnn", "bin", ["cudnn64_9.dll"])
    loader = FakeNativeLibraryLoader({"nvidia.cudnn": [cudnn]})

    status = SystemCudaProbe(loader, "win32", counting(0)).status()

    assert not status.available
    assert "NVIDIA" in status.reason


def test_probe_turns_driver_errors_into_unavailable() -> None:
    status = SystemCudaProbe(
        FakeNativeLibraryLoader({}), "linux", failing_count
    ).status()

    assert not status.available
    assert "cudart64_12.dll" in status.reason
