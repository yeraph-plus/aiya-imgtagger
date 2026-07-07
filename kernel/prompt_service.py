import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from config import DATA_DIR, FREE_FORM_TAG_CATEGORIES, ALL_TAG_CATEGORIES, TAGGING_RULES, CATEGORY_PURPOSES
from kernel.models import PresetTagSet, PresetTag
from utils.json_io import write_json_atomic
from utils.slug import sanitize_slug

CONSTRAINED_CATEGORIES = [c for c in ALL_TAG_CATEGORIES if c not in FREE_FORM_TAG_CATEGORIES]


class PresetService:
    _prompt_cache: Dict[str, str] = {}

    @classmethod
    def create(cls, name: str) -> PresetTagSet:
        return PresetTagSet(
            type=name,
            groups={cat: [] for cat in CONSTRAINED_CATEGORIES},
        )

    @classmethod
    def load(cls, type_name: str) -> Optional[PresetTagSet]:
        presets = cls.list_all()
        return presets.get(type_name)

    @classmethod
    def list_all(cls) -> Dict[str, PresetTagSet]:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        presets: Dict[str, PresetTagSet] = {}

        tag_files = list(DATA_DIR.glob("tags_*.json"))
        if tag_files:
            for tf in sorted(tag_files):
                try:
                    data = json.loads(tf.read_text(encoding="utf-8"))
                    ps = PresetTagSet.from_dict(data)
                    cls._ensure_ids(ps)
                    if ps.type:
                        presets[ps.type] = ps
                except (json.JSONDecodeError, KeyError, TypeError):
                    continue
            return presets

        return {}

    @classmethod
    def save(cls, preset: PresetTagSet):
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        filepath = cls._preset_path(preset.type)
        data = preset.to_dict()
        data["version"] = "2.0"
        write_json_atomic(filepath, data, ensure_ascii=False)

    @classmethod
    def delete(cls, preset_type: str):
        filepath = cls._preset_path(preset_type)
        if filepath.exists():
            filepath.unlink()

    @classmethod
    def add_tag(cls, preset: PresetTagSet, category: str, slug: str, name: str, description: str = "") -> Optional[PresetTag]:
        slug = sanitize_slug(slug)
        if not slug:
            return None
        if category not in preset.groups:
            return None
        for t in preset.groups[category]:
            if t.slug == slug:
                return None
        tag = PresetTag(id=uuid.uuid4().hex, slug=slug, name=name, description=description)
        preset.groups[category].append(tag)
        return tag

    @classmethod
    def update_tag(cls, preset: PresetTagSet, tag_id: str, slug: str = None, name: str = None, description: str = None):
        for cat in preset.groups:
            for t in preset.groups[cat]:
                if t.id == tag_id:
                    if slug is not None:
                        t.slug = slug
                    if name is not None:
                        t.name = name
                    if description is not None:
                        t.description = description
                    return True
        return False

    @classmethod
    def remove_tag(cls, preset: PresetTagSet, tag_id: str):
        for cat in preset.groups:
            preset.groups[cat] = [t for t in preset.groups[cat] if t.id != tag_id]

    @classmethod
    def get_preset_types(cls, presets: Dict[str, PresetTagSet]) -> List[str]:
        return sorted(presets.keys())

    @classmethod
    def compress_for_prompt(cls, preset: PresetTagSet) -> str:
        lines: List[str] = []
        for cat in ALL_TAG_CATEGORIES:
            if cat in FREE_FORM_TAG_CATEGORIES:
                lines.append(f"{cat}(freeform): (free input, use your knowledge)")
            else:
                tags = preset.groups.get(cat, [])
                slugs = [t.slug for t in tags if t.slug]
                if slugs:
                    lines.append(f"{cat}(fixed): {', '.join(slugs)}")
                else:
                    lines.append(f"{cat}(fixed): (use common tags based on your judgment)")
        return "\n".join(lines)

    @classmethod
    def build_tag_constraints(cls, preset: Optional[PresetTagSet] = None) -> str:
        if preset is None:
            lines: List[str] = []
            for cat in ALL_TAG_CATEGORIES:
                if cat in FREE_FORM_TAG_CATEGORIES:
                    lines.append(f"{cat}(freeform): (free input, use your knowledge)")
                else:
                    lines.append(f"{cat}(fixed): (use common tags based on your judgment)")
            lines.insert(0, (
                "## Predefined Tag Table\n"
                "Format per line: \"category(type): available options\"\n"
                "- type freeform = select from list or freely enter new values\n"
                "- type fixed = only select from list, no custom values allowed\n"
            ))
            return "\n".join(lines)

        compressed = cls.compress_for_prompt(preset)
        header = (
            "## Predefined Tag Table\n"
            "Format per line: \"category(type): available options\"\n"
            "- type freeform = select from list or freely enter new values\n"
            "- type fixed = only select from list, no custom values allowed\n"
        )
        return header + "\n" + compressed

    @classmethod
    def build_system_prompt(cls, preset: Optional[PresetTagSet] = None) -> str:
        role = f"You are an image tagging assistant for {preset.type} images." if preset is not None else "You are an image tagging assistant."
        format_instructions = (
            "Analyze ALL provided images as a set from the same folder. "
            "Output tags that represent the image set, one tag per line in format:\n"
            "category:value:confidence\n"
            "Output only categories that have at least one tag. Do not output empty lines. Each category:value pair must be unique."
        )
        constraints = cls.build_tag_constraints(preset)

        purpose_text = "\n".join(f"- {p}" for p in CATEGORY_PURPOSES)
        purpose_lines = "Category Purpose:\n" + purpose_text

        rules = "\n".join(f"{i}. {r}" for i, r in enumerate(TAGGING_RULES, 1))

        example = (
            "\nOutput format example:\n"
            "parody:source_series:0.95\n"
            "character:character_name:0.90\n"
            "artist:creator_name:0.95\n"
            "female:mature:0.92\n"
            "male:bishounen:0.88\n"
            "general:blonde_hair:0.92\n"
            "general:twintails:0.88\n"
            "general:blue_eyes:0.90\n"
            "general:school_uniform:0.85\n"
            "rating:safe:0.95\n"
            "other:highres:0.95\n"
            "other:outdoor:0.85"
        )

        return "\n\n".join([
            role,
            format_instructions,
            constraints,
            purpose_lines,
            "Rules:\n" + rules,
            example,
        ])

    @classmethod
    def get_system_prompt(cls, preset: Optional[PresetTagSet] = None) -> str:
        key = preset.type if preset else "__none__"
        if key not in cls._prompt_cache:
            cls._prompt_cache[key] = cls.build_system_prompt(preset)
        return cls._prompt_cache[key]

    @classmethod
    def clear_prompt_cache(cls):
        cls._prompt_cache.clear()

    @classmethod
    def resolve_tag_name(cls, preset: Optional[PresetTagSet], category: str, slug: str) -> str:
        if preset is not None:
            tags = preset.groups.get(category, [])
            for pt in tags:
                if pt.slug == slug:
                    return pt.name
        return slug.replace("_", " ").title()

    @classmethod
    def _ensure_ids(cls, preset: PresetTagSet):
        for tags in preset.groups.values():
            for tag in tags:
                if not tag.id:
                    tag.id = uuid.uuid4().hex

    @classmethod
    def _preset_path(cls, preset_type: str) -> Path:
        safe = sanitize_preset_name(preset_type)
        return DATA_DIR / f"tags_{safe}.json"
