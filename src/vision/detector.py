from __future__ import annotations

import ctypes
import subprocess
from pathlib import Path

import numpy as np


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
    lib_path = build_dir / "libdw_uvc_camera.so"

    if _should_rebuild(native_root, lib_path):
        _build_native_library(native_root, build_dir)

    lib = ctypes.CDLL(str(lib_path))
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
