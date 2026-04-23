from __future__ import annotations

import ctypes
import os
import platform
import subprocess
from pathlib import Path

import numpy as np

LIBDW_NAME = "libdw_uvc_camera.so"
STARLY_PREBUILT_ROOT = ("thirdparty", "prebuilt", "starry")


class UvcCamera:
    def __init__(self, width: int, height: int, fps: int, vendor_id: int = 0, product_id: int = 0):
        self.width = int(width)
        self.height = int(height)
        self.fps = int(fps)
        self.vendor_id = int(vendor_id)
        self.product_id = int(product_id)
        self._lib = None
        self._handle = None
        self._buffer = None
        self._frame_width = self.width
        self._frame_height = self.height

    def connect(self):
        if self._handle is not None:
            return

        self._lib = _load_native_library()
        self._handle = self._lib.dw_uvc_camera_create(
            self.width,
            self.height,
            self.fps,
            self.vendor_id,
            self.product_id,
        )
        if not self._handle:
            raise RuntimeError("Failed to create libuvc camera handle.")

        if self._lib.dw_uvc_camera_start(self._handle) != 0:
            error = self._last_error()
            self.disconnect()
            raise RuntimeError(f"Failed to start libuvc camera: {error}")

        frame_width = self._lib.dw_uvc_camera_frame_width(self._handle)
        frame_height = self._lib.dw_uvc_camera_frame_height(self._handle)
        if frame_width > 0:
            self._frame_width = frame_width
        if frame_height > 0:
            self._frame_height = frame_height

        buffer_size = self._lib.dw_uvc_camera_frame_buffer_size(self._handle)
        if buffer_size <= 0:
            error = self._last_error()
            self.disconnect()
            raise RuntimeError(f"Invalid libuvc frame buffer size: {error}")

        self._buffer = np.empty(buffer_size, dtype=np.uint8)

    def read(self, timeout_ms: int = 1000) -> np.ndarray:
        if self._handle is None or self._buffer is None:
            raise RuntimeError("Camera is not connected.")

        bytes_written = self._lib.dw_uvc_camera_wait_for_frame(
            self._handle,
            self._buffer.ctypes.data_as(ctypes.POINTER(ctypes.c_uint8)),
            int(self._buffer.nbytes),
            int(timeout_ms),
        )
        if bytes_written < 0:
            raise RuntimeError(f"Failed to read camera frame: {self._last_error()}")

        frame_width = self._lib.dw_uvc_camera_frame_width(self._handle)
        frame_height = self._lib.dw_uvc_camera_frame_height(self._handle)
        if frame_width <= 0 or frame_height <= 0:
            raise RuntimeError("Camera returned an invalid frame shape.")

        expected_size = frame_width * frame_height * 3
        if bytes_written != expected_size:
            raise RuntimeError(
                f"Unexpected frame size from libuvc camera: got {bytes_written}, expected {expected_size}."
            )

        return self._buffer[:bytes_written].reshape((frame_height, frame_width, 3)).copy()

    def disconnect(self):
        if self._handle is not None and self._lib is not None:
            self._lib.dw_uvc_camera_stop(self._handle)
            self._lib.dw_uvc_camera_destroy(self._handle)
        self._handle = None
        self._buffer = None

    def _last_error(self) -> str:
        if self._handle is None or self._lib is None:
            return "unknown error"

        raw_error = self._lib.dw_uvc_camera_last_error(self._handle)
        if not raw_error:
            return "unknown error"
        return raw_error.decode("utf-8", errors="replace")


def _load_native_library():
    project_root = Path(__file__).resolve().parents[2]
    native_root = project_root / "src" / "native" / "uvc_camera"
    build_dir = native_root / "build"
    build_lib_path = build_dir / LIBDW_NAME

    lib_path = _find_prebuilt_library(project_root)
    if lib_path is None:
        if _should_build_locally(build_lib_path):
            if _should_rebuild(native_root, build_lib_path):
                _build_native_library(native_root, build_dir)
            lib_path = build_lib_path
        elif build_lib_path.exists():
            lib_path = build_lib_path
        else:
            raise RuntimeError(
                "No prebuilt UVC runtime library was found. "
                "Expected a prebuilt library under thirdparty/prebuilt/starry/<arch>/lib "
                "or set DW_UVC_PREBUILT_DIR / DW_UVC_CAMERA_LIB_PATH."
            )

    _preload_runtime_dependencies(lib_path.parent)
    lib = ctypes.CDLL(str(lib_path), mode=ctypes.RTLD_GLOBAL)
    lib.dw_uvc_camera_create.argtypes = [
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib.dw_uvc_camera_create.restype = ctypes.c_void_p
    lib.dw_uvc_camera_start.argtypes = [ctypes.c_void_p]
    lib.dw_uvc_camera_start.restype = ctypes.c_int
    lib.dw_uvc_camera_stop.argtypes = [ctypes.c_void_p]
    lib.dw_uvc_camera_stop.restype = None
    lib.dw_uvc_camera_destroy.argtypes = [ctypes.c_void_p]
    lib.dw_uvc_camera_destroy.restype = None
    lib.dw_uvc_camera_wait_for_frame.argtypes = [
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_uint8),
        ctypes.c_int,
        ctypes.c_int,
    ]
    lib.dw_uvc_camera_wait_for_frame.restype = ctypes.c_int
    lib.dw_uvc_camera_frame_width.argtypes = [ctypes.c_void_p]
    lib.dw_uvc_camera_frame_width.restype = ctypes.c_int
    lib.dw_uvc_camera_frame_height.argtypes = [ctypes.c_void_p]
    lib.dw_uvc_camera_frame_height.restype = ctypes.c_int
    lib.dw_uvc_camera_frame_buffer_size.argtypes = [ctypes.c_void_p]
    lib.dw_uvc_camera_frame_buffer_size.restype = ctypes.c_int
    lib.dw_uvc_camera_last_error.argtypes = [ctypes.c_void_p]
    lib.dw_uvc_camera_last_error.restype = ctypes.c_char_p
    return lib


def _find_prebuilt_library(project_root: Path) -> Path | None:
    explicit_lib = os.environ.get("DW_UVC_CAMERA_LIB_PATH")
    if explicit_lib:
        path = Path(explicit_lib).expanduser().resolve()
        if path.exists():
            return path

    search_dirs = []
    explicit_dir = os.environ.get("DW_UVC_PREBUILT_DIR")
    if explicit_dir:
        search_dirs.append(Path(explicit_dir).expanduser().resolve())

    machine = platform.machine().lower()
    search_dirs.extend(
        [
            project_root.joinpath(*STARLY_PREBUILT_ROOT, machine, "lib"),
            project_root.joinpath(*STARLY_PREBUILT_ROOT, "aarch64", "lib"),
        ]
    )

    for search_dir in search_dirs:
        lib_path = search_dir / LIBDW_NAME
        if lib_path.exists():
            return lib_path

    return None


def _should_build_locally(build_lib_path: Path) -> bool:
    if os.environ.get("DW_UVC_DISABLE_BUILD") == "1":
        return False
    if os.environ.get("DW_UVC_ALLOW_BUILD") == "1":
        return True

    machine = platform.machine().lower()
    return machine not in {"aarch64", "arm64"}


def _preload_runtime_dependencies(lib_dir: Path):
    for prefix in ("libusb-1.0.so", "libuvc.so"):
        dependency = _pick_matching_library(lib_dir, prefix)
        if dependency is not None:
            ctypes.CDLL(str(dependency), mode=ctypes.RTLD_GLOBAL)


def _pick_matching_library(lib_dir: Path, prefix: str) -> Path | None:
    matches = sorted(lib_dir.glob(f"{prefix}*"))
    if not matches:
        return None

    # Prefer the most versioned file first so the loader sees the real SONAME owner.
    return sorted(matches, key=lambda path: (len(path.name), path.name), reverse=True)[0]


def _should_rebuild(native_root: Path, lib_path: Path) -> bool:
    if not lib_path.exists():
        return True

    lib_mtime = lib_path.stat().st_mtime
    source_paths = (
        list((native_root / "include").glob("**/*"))
        + list((native_root / "src").glob("**/*"))
        + [native_root / "CMakeLists.txt"]
    )
    return any(path.is_file() and path.stat().st_mtime > lib_mtime for path in source_paths)


def _build_native_library(native_root: Path, build_dir: Path):
    build_dir.mkdir(parents=True, exist_ok=True)

    subprocess.run(
        ["cmake", "-S", str(native_root), "-B", str(build_dir), "-DCMAKE_BUILD_TYPE=Release"],
        check=True,
    )
    subprocess.run(
        ["cmake", "--build", str(build_dir), "--config", "Release"],
        check=True,
    )
