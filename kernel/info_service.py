import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

from config import ALL_TAG_CATEGORIES, GALLERY_INFO_FILENAME
from utils.json_io import write_json_atomic


@dataclass
class GalleryInfo:
    title: str = ""
    category: str = ""
    language: str = ""
    file_count: dict = field(default_factory=lambda: {"image": 0, "video": 0})
    file_size: int = 0
    thumbnail: str = "./.thumb"
    tags: Dict[str, List[str]] = field(default_factory=lambda: {c: [] for c in ALL_TAG_CATEGORIES})

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "category": self.category,
            "language": self.language,
            "file_count": dict(self.file_count),
            "file_size": self.file_size,
            "thumbnail": self.thumbnail,
            "tags": {k: list(v) for k, v in self.tags.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "GalleryInfo":
        tags: Dict[str, List[str]] = {}
        raw_tags = d.get("tags", {})
        for cat in ALL_TAG_CATEGORIES:
            tags[cat] = [str(v) for v in raw_tags.get(cat, [])]
        return cls(
            title=d.get("title", ""),
            category=d.get("category", ""),
            language=d.get("language", ""),
            file_count=d.get("file_count", {"image": 0, "video": 0}),
            file_size=d.get("file_size", 0),
            thumbnail=d.get("thumbnail", "./.thumb"),
            tags=tags,
        )


class InfoService:

    @staticmethod
    def create() -> GalleryInfo:
        return GalleryInfo()

    @staticmethod
    def path(folder: Path) -> Path:
        return folder / GALLERY_INFO_FILENAME

    @staticmethod
    def exists(folder: Path) -> bool:
        return InfoService.path(folder).exists()

    @staticmethod
    def load(folder: Path) -> Optional[GalleryInfo]:
        p = InfoService.path(folder)
        if not p.exists():
            return None
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            return GalleryInfo.from_dict(data)
        except (json.JSONDecodeError, KeyError, TypeError):
            return None

    @staticmethod
    def save(folder: Path, info: GalleryInfo):
        write_json_atomic(InfoService.path(folder), info.to_dict(), ensure_ascii=False)
