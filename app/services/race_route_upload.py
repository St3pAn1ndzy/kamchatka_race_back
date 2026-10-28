"""Ограниченная загрузка общего маршрута и его сопоставления этапам"""

import json

from fastapi import HTTPException
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import Request

LIMIT = 8 * 1024 * 1024


async def read_race_upload(request: Request) -> tuple[bytes, str, list]:
    """Принимает один файл и необязательное JSON-сопоставление без неограниченного чтения"""
    if request.headers.get("content-type", "").split(";", 1)[0].lower() != "multipart/form-data":
        raise HTTPException(422, "Передайте файл в поле file")
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > LIMIT + 65536:
            raise HTTPException(413, "Общий маршрут не должен превышать 8 МиБ")
        body.extend(chunk)

    async def stream():
        yield bytes(body)

    try:
        form = await MultiPartParser(request.headers, stream(), max_files=1, max_fields=1).parse()
    except (MultiPartException, ValueError) as exc:
        raise HTTPException(422, "Некорректная загрузка маршрута") from exc
    try:
        file = form.get("file")
        keys = [key for key, _ in form.multi_items()]
        if (
            not isinstance(file, UploadFile)
            or keys.count("file") != 1
            or any(key not in {"file", "mapping"} for key in keys)
        ):
            raise HTTPException(422, "Нужен один файл и сопоставление этапам")
        content = await file.read(LIMIT + 1)
        if len(content) > LIMIT:
            raise HTTPException(413, "Общий маршрут не должен превышать 8 МиБ")
        try:
            mapping = json.loads(form.get("mapping", "[]"))
        except (TypeError, ValueError) as exc:
            raise HTTPException(422, "Некорректное сопоставление этапам") from exc
        if not isinstance(mapping, list) or len(mapping) > 32:
            raise HTTPException(422, "Допускается не более 32 этапов")
        return content, file.filename or "", mapping
    finally:
        await form.close()
