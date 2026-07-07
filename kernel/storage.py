import json
import logging
from pathlib import Path
from typing import Optional

from config import AI_TAGS_FILENAME
from kernel.models import FolderTagData
from utils.json_io import write_json_atomic

_logger = logging.getLogger(__name__)


class Storage:

    @staticmethod
    def get_tags_path(folder: Path) -> Path:
        return folder / AI_TAGS_FILENAME

    @staticmethod
    def has_tags(folder: Path) -> bool:
        return Storage.get_tags_path(folder).exists()

    @staticmethod
    def load_tags(folder: Path) -> Optional[FolderTagData]:
        path = Storage.get_tags_path(folder)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return FolderTagData.from_dict(raw)
        except (json.JSONDecodeError, KeyError) as e:
            _logger.warning("Failed to parse %s: %s", path, e)
            return None

    @staticmethod
    def save_tags(folder: Path, data: FolderTagData):
        write_json_atomic(Storage.get_tags_path(folder), data.to_dict(), ensure_ascii=False)
