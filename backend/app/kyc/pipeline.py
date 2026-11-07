"""Bytes in, checked documents out: OCR (in memory) -> fields -> DocInput."""

from __future__ import annotations

from app.kyc.checks import DocInput
from app.kyc.extract import DOC_TYPES, extract
from app.kyc.ocr import OcrPool, OcrRefused, run_ocr


def read_document(data: bytes, declared_type: str, pool: OcrPool | None = None) -> tuple[DocInput, dict]:
    """Returns the document's fields (or a refusal) and its quality info. The bytes are not kept."""
    if declared_type not in DOC_TYPES:
        raise ValueError(f"unknown document type {declared_type!r}")
    try:
        result = pool.submit(data) if pool else run_ocr(data)
    except OcrRefused as exc:
        return DocInput(refused=exc.code), exc.detail
    fields, seen = extract(result.boxes, declared_type)
    return DocInput(fields, None, seen), result.quality
