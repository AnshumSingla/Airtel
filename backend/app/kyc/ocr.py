"""Local OCR for KYC documents (DECISIONS.md D8; evidence/ocr_spike/).

Images are decoded from request bytes and never written to disk. Before OCR:
the red channel only (washes out the red watermark), a blur gate, and deskew.
OCR runs in a small worker pool so a burst of uploads can't block the API
(ARCHITECTURE.md §4.3: 2 workers, 20 s timeout, at most 4 in flight).
"""

from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from dataclasses import dataclass, field

import cv2
import numpy as np

BLUR_MIN_SHARPNESS = 100.0   # specimens score >= 832; K04's blurry GST certificate scores 0.9
SKEW_MIN_DEGREES = 0.5
MAX_SIDE = 2000
MAX_BYTES = 8 * 1024 * 1024


class OcrRefused(Exception):
    """The quality gate or input checks refused the image; ``code`` says why."""

    def __init__(self, code: str, detail: dict | None = None):
        super().__init__(code)
        self.code, self.detail = code, detail or {}


class OcrBusy(Exception):
    pass


@dataclass(frozen=True)
class Box:
    x: float
    y: float
    text: str
    score: float


@dataclass
class OcrResult:
    boxes: list[Box]
    quality: dict = field(default_factory=dict)


def decode(data: bytes) -> np.ndarray:
    if len(data) > MAX_BYTES:
        raise OcrRefused("FILE_TOO_LARGE", {"bytes": len(data)})
    if not (data[:8] == b"\x89PNG\r\n\x1a\n" or data[:3] == b"\xff\xd8\xff"):
        raise OcrRefused("UNSUPPORTED_TYPE")
    img = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise OcrRefused("UNREADABLE_IMAGE")
    h, w = img.shape[:2]
    scale = MAX_SIDE / max(h, w)
    if scale < 1:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
    return img


def sharpness(gray: np.ndarray) -> float:
    return float(cv2.Laplacian(gray, cv2.CV_64F).var())


def skew_degrees(gray: np.ndarray) -> float:
    edges = cv2.Canny(gray, 50, 150)
    lines = cv2.HoughLinesP(edges, 1, np.pi / 1800, 200, minLineLength=gray.shape[1] // 3, maxLineGap=10)
    if lines is None:
        return 0.0
    angles = [np.degrees(np.arctan2(y2 - y1, x2 - x1)) for x1, y1, x2, y2 in np.asarray(lines).reshape(-1, 4)]
    angles = [a for a in angles if abs(a) < 20]
    return float(np.median(angles)) if angles else 0.0


def prepare(img: np.ndarray) -> tuple[np.ndarray, dict]:
    red = img[:, :, 2]
    quality = {"sharpness": round(sharpness(red), 1), "skew": round(skew_degrees(red), 2)}
    if quality["sharpness"] < BLUR_MIN_SHARPNESS:
        raise OcrRefused("TOO_BLURRY", quality)
    if abs(quality["skew"]) > SKEW_MIN_DEGREES:
        h, w = red.shape
        m = cv2.getRotationMatrix2D((w / 2, h / 2), quality["skew"], 1.0)
        red = cv2.warpAffine(red, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)
        quality["deskewed"] = True
    return cv2.cvtColor(red, cv2.COLOR_GRAY2BGR), quality


_local = threading.local()


def _engine():
    if not hasattr(_local, "engine"):
        from rapidocr_onnxruntime import RapidOCR  # loaded lazily: about 1 s and ~100 MB
        _local.engine = RapidOCR()
    return _local.engine


def run_ocr(data: bytes) -> OcrResult:
    img, quality = prepare(decode(data))
    try:
        res, _ = _engine()(img)
    except Exception as exc:  # noqa: BLE001 - ONNX Runtime raises its own types, e.g. "bad allocation"
        # Seen once in a long local run (evidence/kyc_pipeline/README.md): tell the owner to retry
        # instead of returning a server error.
        raise OcrRefused("OCR_ERROR", {"error": type(exc).__name__}) from exc
    boxes = [Box(float(b[0][0]), float(b[0][1]), t, float(s)) for b, t, s in (res or [])]
    return OcrResult(boxes, quality)


class OcrPool:
    def __init__(self, workers: int = 2, max_in_flight: int = 4, timeout_s: float = 20.0):
        self._pool = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="ocr")
        self._slots = threading.BoundedSemaphore(max_in_flight)
        self.timeout_s = timeout_s

    def submit(self, data: bytes) -> OcrResult:
        if not self._slots.acquire(blocking=False):
            raise OcrBusy()
        try:
            future = self._pool.submit(run_ocr, data)
            try:
                return future.result(timeout=self.timeout_s)
            except FutureTimeout:
                future.cancel()
                raise OcrRefused("TIMEOUT")
        finally:
            self._slots.release()

    def shutdown(self) -> None:
        self._pool.shutdown(wait=False, cancel_futures=True)
