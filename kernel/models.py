from dataclasses import dataclass, field
from enum import Enum, auto
from pathlib import Path
from typing import Dict, List, Optional

from config import ALL_TAG_CATEGORIES


class TaskState(Enum):
    UNLOADED = auto()
    SCANNING = auto()
    LOADED = auto()
    PRELOADING = auto()
    PRELOADED = auto()
    QUEUED = auto()
    PROCESSING = auto()
    COMPLETED = auto()
    ERROR = auto()


TASK_STATE_LABELS = {
    TaskState.UNLOADED: "[..]",
    TaskState.SCANNING: "[Scan]",
    TaskState.LOADED: "[Load]",
    TaskState.PRELOADING: "[Preload]",
    TaskState.PRELOADED: "[Ready]",
    TaskState.QUEUED: "[Queue]",
    TaskState.PROCESSING: "[Process]",
    TaskState.COMPLETED: "[Done]",
    TaskState.ERROR: "[Error]",
}


@dataclass
class AITag:
    category: str
    value: str
    confidence: float = 1.0
    confirmed: bool = False

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "confidence": self.confidence,
            "confirmed": self.confirmed,
        }

    @classmethod
    def from_dict(cls, d: dict, category: str = "") -> "AITag":
        return cls(
            category=category,
            value=d.get("value", d) if isinstance(d, dict) else str(d),
            confidence=d.get("confidence", 1.0) if isinstance(d, dict) else 1.0,
            confirmed=d.get("confirmed", True) if isinstance(d, dict) else True,
        )


@dataclass
class PresetTag:
    id: str = ""
    slug: str = ""
    name: str = ""
    description: str = ""

    def to_dict(self) -> dict:
        d = {"id": self.id, "slug": self.slug, "name": self.name}
        if self.description:
            d["description"] = self.description
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "PresetTag":
        return cls(
            id=d.get("id", ""),
            slug=d.get("slug", ""),
            name=d.get("name", d.get("slug", "")),
            description=d.get("description", ""),
        )


@dataclass
class PresetTagSet:
    type: str
    groups: Dict[str, List[PresetTag]] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "type": self.type,
            "groups": {k: [t.to_dict() for t in v] for k, v in self.groups.items()},
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PresetTagSet":
        groups: Dict[str, List[PresetTag]] = {}
        for cat, tag_list in d.get("groups", {}).items():
            groups[cat] = [PresetTag.from_dict(t) for t in tag_list]
        return cls(type=d.get("type", ""), groups=groups)


@dataclass
class FolderTagData:
    version: str = "1.0"
    tags: Dict[str, List[AITag]] = field(default_factory=lambda: {c: [] for c in ALL_TAG_CATEGORIES})

    def to_dict(self) -> dict:
        result: dict = {}
        for cat, tag_list in self.tags.items():
            result[cat] = [t.to_dict() for t in tag_list]
        return {"version": self.version, "tags": result}

    @classmethod
    def from_dict(cls, d: dict) -> "FolderTagData":
        tags: Dict[str, List[AITag]] = {}
        for cat in ALL_TAG_CATEGORIES:
            raw_list = d.get("tags", {}).get(cat, [])
            tags[cat] = [AITag.from_dict(item, cat) for item in raw_list]
        return cls(version=d.get("version", "1.0"), tags=tags)


@dataclass
class Task:
    id: str
    path: Path
    name: str
    images: List[Path] = field(default_factory=list)
    state: TaskState = TaskState.UNLOADED
    tag_data: Optional[FolderTagData] = None
    info: Optional["GalleryInfo"] = None
    error_message: str = ""
