"""Локальное хранилище для загружаемых файлов.

Файлы лежат в `media/{folder}/{prefix}_{uuid}.{ext}`.
В БД храним публичный URL (`/media/participants/5_a1b2.jpg`).
"""

import logging
import uuid
from pathlib import Path

from fastapi import UploadFile

logger = logging.getLogger(__name__)

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB


class MediaStorage:
    def __init__(self, root: str = "media", url_prefix: str = "/media"):
        self.root = Path(root)
        self.url_prefix = url_prefix
        self.root.mkdir(parents=True, exist_ok=True)

    async def save_image(self, file: UploadFile, folder: str, prefix: str = "") -> str:
        """Сохраняет картинку и возвращает публичный URL для БД.

        Args:
            file: файл из формы.
            folder: подпапка внутри media (например, "participants").
            prefix: префикс имени (например, номер участника).

        Raises:
            ValueError: если формат не разрешён или файл слишком большой.
        """
        if not file or not file.filename:
            raise ValueError("Пустой файл")

        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_IMAGE_EXTENSIONS:
            raise ValueError(
                f"Формат {ext} не поддерживается. "
                f"Разрешены: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
            )

        content = await file.read()
        if len(content) > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"Файл больше {MAX_FILE_SIZE_BYTES // (1024 * 1024)} MB")
        if len(content) == 0:
            raise ValueError("Файл пустой")

        target_dir = self.root / folder
        target_dir.mkdir(parents=True, exist_ok=True)

        name = f"{prefix}_{uuid.uuid4().hex[:8]}{ext}" if prefix else f"{uuid.uuid4().hex}{ext}"
        target = target_dir / name
        target.write_bytes(content)

        logger.info("Сохранён файл: %s (%d bytes)", target.resolve(), len(content))

        return f"{self.url_prefix}/{folder}/{name}"

    def delete(self, url: str) -> None:
        logger.debug("delete() вызван с url=%r", url)
        if not url or not url.startswith(self.url_prefix + "/"):
            logger.debug("delete: пропуск (url не наш)")
            return
        rel = url[len(self.url_prefix) + 1 :]
        path = self.root / rel
        logger.debug("delete: путь=%s, существует=%s", path, path.is_file())
        try:
            path.resolve().relative_to(self.root.resolve())
        except ValueError:
            logger.warning("delete: обнаружен path traversal для url=%r", url)
            return
        if path.is_file():
            path.unlink(missing_ok=True)
            logger.info("Удалён старый файл: %s", path)
        else:
            logger.warning("delete: файла нет на диске: %s", path)


media_storage = MediaStorage()
