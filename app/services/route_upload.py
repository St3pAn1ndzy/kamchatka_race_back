"""Ограниченное чтение файлов маршрута из HTTP-запроса"""

from fastapi import HTTPException
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException, MultiPartParser
from starlette.requests import Request

from app.schemas.admin_stage_route import StageRouteReplaceRequest
from app.services.route_file import MAX_ROUTE_FILE_BYTES, RouteFileError, parse_route_file


async def read_route_request(request: Request) -> bytes:
    """Ограничивает весь поток запроса, включая загрузки без Content-Length"""
    body = bytearray()
    async for chunk in request.stream():
        if len(body) + len(chunk) > MAX_ROUTE_FILE_BYTES + 65536:
            raise HTTPException(413, "Запрос слишком большой, максимальный размер файла — 2 МиБ")
        body.extend(chunk)
    return bytes(body)


async def read_route_upload(request: Request) -> StageRouteReplaceRequest:
    """Принимает ровно один файл и закрывает временные файлы после разбора"""
    content_type = request.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
    if content_type != "multipart/form-data":
        raise HTTPException(422, "Передайте файл как multipart/form-data")
    body = await read_route_request(request)

    async def stream():
        yield body

    try:
        form = await MultiPartParser(request.headers, stream(), max_files=1, max_fields=0).parse()
    except (MultiPartException, ValueError) as exc:
        raise HTTPException(422, "Передайте один файл KML или GPX в поле file") from exc

    try:
        uploaded = form.get("file")
        if len(form.multi_items()) != 1 or not isinstance(uploaded, UploadFile):
            raise HTTPException(422, "Передайте один файл KML или GPX в поле file")
        content = await uploaded.read(MAX_ROUTE_FILE_BYTES + 1)
        if len(content) > MAX_ROUTE_FILE_BYTES:
            raise HTTPException(413, "Максимальный размер файла — 2 МиБ")
        try:
            return parse_route_file(content, uploaded.filename or "")
        except RouteFileError as exc:
            raise HTTPException(422, str(exc)) from exc
    finally:
        await form.close()
