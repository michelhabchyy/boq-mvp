"""Safe file-upload reading.

`read_upload_capped` streams the upload in chunks and aborts as soon as it
exceeds the limit, so a malicious huge file can't exhaust server memory (memory
stays bounded at ~the limit, not the file size).
"""

from fastapi import HTTPException, UploadFile

from .config import settings

_CHUNK = 1024 * 1024  # 1 MB


def max_upload_bytes() -> int:
    return max(1, settings.max_upload_mb) * 1024 * 1024


async def read_upload_capped(file: UploadFile, max_bytes: int | None = None) -> bytes:
    """Read an UploadFile fully, but reject (413) once it passes the cap."""
    limit = max_bytes if max_bytes is not None else max_upload_bytes()
    chunks: list[bytes] = []
    total = 0
    while True:
        chunk = await file.read(_CHUNK)
        if not chunk:
            break
        total += len(chunk)
        if total > limit:
            raise HTTPException(
                status_code=413,
                detail=f"File too large (max {limit // (1024 * 1024)} MB).",
            )
        chunks.append(chunk)
    return b"".join(chunks)
