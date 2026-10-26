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
from collections.abc import Sequence
from pathlib import Path
from typing import Protocol

logger = logging.getLogger(__name__)

NVIDIA_PACKAGES: tuple[str, ...] = ("nvidia.cublas", "nvidia.cudnn")


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
