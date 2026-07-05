from pathlib import Path
from typing import List

from config import SUPPORTED_EXTENSIONS


def scan_images(folder: Path) -> List[Path]:
    images = []
    if folder.is_dir():
        for f in sorted(folder.iterdir()):
            if f.is_file() and f.suffix.lower() in SUPPORTED_EXTENSIONS:
                images.append(f)
    return images


def scan_entry(root: Path) -> List[Path]:
    folders = []
    if not root.is_dir():
        return folders
    for entry in sorted(root.iterdir()):
        if entry.is_dir():
            images = scan_images(entry)
            if images:
                folders.append(entry)
    return folders
