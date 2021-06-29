from contextlib import suppress
from hashlib import md5
from json import dumps, loads
from pathlib import Path
from typing import AbstractSet, Iterable, Mapping, MutableSequence, Tuple, TypedDict

from ...consts import CLIENTS_DIR
from .parser import Tag, parse_lines, run

_TAGS_DIR = CLIENTS_DIR / "tags"


class _TagInfo(TypedDict):
    mtime: float
    tags: MutableSequence[Tag]


Tags = Mapping[str, _TagInfo]

_NIL_INFO = _TagInfo(mtime=0, tags=[])


def _mtimes(paths: Iterable[Path]) -> Mapping[str, float]:
    def cont() -> Iterable[Tuple[Path, float]]:
        for path in paths:
            with suppress(FileNotFoundError):
                stat = path.stat()
                yield path, stat.st_mtime

    return {str(key): val for key, val in cont()}


def reconciliate(cwd: Path, paths: AbstractSet[str]) -> Tags:
    _TAGS_DIR.mkdir(parents=True, exist_ok=True)
    tag_path = _TAGS_DIR / md5(str(cwd).encode()).hexdigest()

    try:
        json = tag_path.read_text("UTF-8")
    except FileNotFoundError:
        existing = {}
    else:
        existing: Tags = loads(json)

    mtimes = _mtimes(map(Path, existing.keys() | paths))
    query_paths = tuple(
        path
        for path, mtime in mtimes.items()
        if mtime > existing.get(path, _NIL_INFO)["mtime"]
    )
    raw = run(*query_paths) if query_paths else ""

    acc: Tags = {}
    for tag in parse_lines(raw):
        path = tag["path"]
        info = acc.setdefault(path, _NIL_INFO)
        info["tags"].append(tag)

    new = {**existing, **acc}
    json = dumps(new, check_circular=False, ensure_ascii=False, indent=2)
    return new
