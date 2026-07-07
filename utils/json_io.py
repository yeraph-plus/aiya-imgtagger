import json
import logging
import os
from pathlib import Path
from typing import Any

_logger = logging.getLogger(__name__)

_TMP_SUFFIX = ".tmp"


def write_json_atomic(path: Path, obj: Any, indent: int = 2, ensure_ascii: bool = False) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + _TMP_SUFFIX)
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=ensure_ascii, indent=indent)
        os.replace(tmp, path)
    except Exception:
        try:
            if tmp.exists():
                tmp.unlink()
        except OSError:
            pass
        raise


def read_json(path: Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))