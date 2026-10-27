"""Deixa as bibliotecas CUDA dos pacotes pip ``nvidia-*`` visíveis ao CTranslate2.

O CTranslate2 (motor do faster-whisper) carrega cuBLAS/cuDNN pelo loader do
sistema operacional, mas os wheels ``nvidia-cublas-cu12``/``nvidia-cudnn-cu12``
instalam essas libs dentro do site-packages, fora do caminho de busca. Sem isto
seria preciso instalar o CUDA Toolkit no sistema ou exportar
``LD_LIBRARY_PATH``/``PATH`` antes de cada execução.

- Linux: pré-carrega cada ``lib*.so*`` com ``RTLD_GLOBAL``; o ``dlopen`` posterior
  do CTranslate2 encontra a lib já carregada pelo soname.
- Windows: registra a pasta ``bin`` com ``os.add_dll_directory`` e no ``PATH``.
"""

from __future__ import annotations

import ctypes
import importlib.util
import logging
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

NVIDIA_PACKAGES: tuple[str, ...] = ("nvidia.cublas", "nvidia.cudnn")

GPU_EXTRA_HINT = "com GPU NVIDIA, rode `uv sync --extra gpu`"


@dataclass(frozen=True)
class CudaStatus:
    """Se há GPU CUDA utilizável; ``reason`` explica o resultado ao usuário."""

    available: bool
    reason: str


class CudaProbe(Protocol):
    def status(self) -> CudaStatus: ...


class NativeLibraryLoader(Protocol):
    def find_package_folders(self, package: str) -> list[Path]: ...

    def load_shared_object(self, library_file: Path) -> bool: ...

    def add_dll_folder(self, folder: Path) -> None: ...


def register_nvidia_libraries(loader: NativeLibraryLoader, platform: str) -> list[Path]:
    """Registra as libs CUDA encontradas e devolve as pastas registradas.

    Sem os pacotes ``nvidia-*`` instalados (ex.: uso só em CPU) não faz nada.

    Exemplo::

        register_nvidia_libraries(SystemNativeLibraryLoader(), sys.platform)
    """
    folders = [
        folder
        for package in NVIDIA_PACKAGES
        for folder in _library_folders(loader, package, platform)
    ]
    for folder in folders:
        _register_folder(loader, folder, platform)
    return folders


def _library_folders(
    loader: NativeLibraryLoader, package: str, platform: str
) -> list[Path]:
    subfolder = "bin" if platform == "win32" else "lib"
    candidates = [root / subfolder for root in loader.find_package_folders(package)]
    return [candidate for candidate in candidates if candidate.is_dir()]


def _register_folder(loader: NativeLibraryLoader, folder: Path, platform: str) -> None:
    if platform == "win32":
        loader.add_dll_folder(folder)
        return
    load_until_stable(loader, sorted(folder.glob("lib*.so*")))


def load_until_stable(
    loader: NativeLibraryLoader, library_files: Sequence[Path]
) -> list[Path]:
    """Carrega as libs repetindo as que falharam enquanto houver progresso.

    As sub-libs do cuDNN dependem umas das outras e a ordem alfabética nem
    sempre respeita essa dependência; uma nova passada resolve. Devolve as libs
    que nunca carregaram.

    Exemplo::

        load_until_stable(loader, [Path("libcudnn_ops.so.9"), Path("libcudnn.so.9")])
    """
    pending = list(library_files)
    while pending:
        still_pending = [
            library for library in pending if not loader.load_shared_object(library)
        ]
        if len(still_pending) == len(pending):
            logger.warning(
                "cuda_libraries_not_loaded", extra={"fields": {"files": still_pending}}
            )
            return still_pending
        pending = still_pending
    return []


class SystemNativeLibraryLoader:
    """Implementação real sobre ``importlib``, ``ctypes`` e ``os``."""

    def find_package_folders(self, package: str) -> list[Path]:
        try:
            spec = importlib.util.find_spec(package)
        except ModuleNotFoundError:
            return []
        if spec is None or spec.submodule_search_locations is None:
            return []
        return [Path(location) for location in spec.submodule_search_locations]

    def load_shared_object(self, library_file: Path) -> bool:
        try:
            ctypes.CDLL(str(library_file), mode=ctypes.RTLD_GLOBAL)
        except OSError:
            return False
        return True

    def add_dll_folder(self, folder: Path) -> None:
        if sys.platform == "win32":
            os.add_dll_directory(str(folder))
        # Algumas DLLs são carregadas via LoadLibrary sem as flags que consultam
        # add_dll_directory; o PATH cobre esse caso.
        os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")


def ctranslate2_cuda_device_count() -> int:
    """Quantas GPUs CUDA o CTranslate2 enxerga (0 em Intel/AMD ou sem driver NVIDIA)."""
    # Importação tardia: carregar o CTranslate2 custa segundos.
    import ctranslate2

    return int(ctranslate2.get_cuda_device_count())


class SystemCudaProbe:
    """Registra as libs CUDA dos pacotes pip e consulta se há GPU NVIDIA utilizável.

    Exemplo::

        SystemCudaProbe(SystemNativeLibraryLoader(), sys.platform).status().available
    """

    def __init__(
        self,
        loader: NativeLibraryLoader,
        platform: str,
        count_devices: Callable[[], int] = ctranslate2_cuda_device_count,
    ) -> None:
        self._loader = loader
        self._platform = platform
        self._count_devices = count_devices

    def status(self) -> CudaStatus:
        folders = register_nvidia_libraries(self._loader, self._platform)
        # No Windows não há CUDA de sistema para o cuDNN: sem os wheels nvidia-*
        # o CTranslate2 acharia a GPU e falharia só na primeira inferência.
        # No Linux o CUDA pode vir do sistema, então a ausência dos wheels não conta.
        if self._platform == "win32" and not folders:
            return CudaStatus(False, f"pacotes nvidia-* ausentes ({GPU_EXTRA_HINT})")
        return self._device_status()

    def _device_status(self) -> CudaStatus:
        try:
            count = self._count_devices()
        except Exception as error:  # driver/DLL quebrados vêm como erros variados
            return CudaStatus(False, f"falha ao consultar a GPU: {error}")
        if count <= 0:
            return CudaStatus(False, "nenhuma GPU NVIDIA com driver CUDA encontrada")
        return CudaStatus(True, f"{count} GPU(s) CUDA")
