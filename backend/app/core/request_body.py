from fastapi import HTTPException, Request, status


async def read_limited_body(request: Request, max_bytes: int, detail: str) -> bytes:
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > max_bytes:
            raise HTTPException(status_code=status.HTTP_413_CONTENT_TOO_LARGE, detail=detail)
    return bytes(body)
