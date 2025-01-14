from enum import Enum, auto
from os import linesep
from pathlib import Path
from typing import AbstractSet, MutableSequence, MutableSet, Sequence, Tuple

from ..types import ParsedSnippet
from .parse import raise_err

_COMMENT_START = "#"
_EXTENDS_START = "extends"
_SNIPPET_START = "snippet"
_SNIPPET_END = "endsnippet"
_GLOBAL_START = "global"
_GLOBAL_END = "globalend"

_IGNORE_STARTS = {
    "priority",
    "iclearsnippets",
    "pre_expand",
    "post_expand",
    "post_jump",
}


class _State(Enum):
    normal = auto()
    snippet = auto()
    pglobal = auto()


def _start(line: str) -> Tuple[str, str, MutableSet[str]]:
    rest = line[len(_SNIPPET_START) :].strip()
    name, _, label = rest.partition(" ")
    if label.startswith('"') and label[1:].count('"') == 1:
        quoted, _, opts = label[1:].partition('"')
        options = {*opts.strip()}
        return name, quoted, options
    else:
        return name, label, set()


def parse(path: Path) -> Tuple[AbstractSet[str], Sequence[ParsedSnippet]]:
    snippets: MutableSequence[ParsedSnippet] = []
    extends: MutableSet[str] = set()

    current_name = ""
    state = _State.normal
    current_label: str = ""
    current_lines: MutableSequence[str] = []
    current_opts: AbstractSet[str] = frozenset()

    lines = path.read_text().splitlines()
    for lineno, line in enumerate(lines, 1):
        if state == _State.normal:
            if (
                not line
                or line.isspace()
                or line.startswith(_COMMENT_START)
                or any(line.startswith(ignore) for ignore in _IGNORE_STARTS)
            ):
                pass

            elif line.startswith(_EXTENDS_START):
                filetypes = line[len(_EXTENDS_START) :].strip()
                for filetype in filetypes.split(","):
                    extends.add(filetype.strip())

            elif line.startswith(_SNIPPET_START):
                state = _State.snippet

                current_name, current_label, current_opts = _start(line)

            elif line.startswith(_GLOBAL_START):
                state = _State.pglobal

            else:
                reason = "Unexpected line start"
                raise_err(path, lineno=lineno, line=line, reason=reason)

        elif state == _State.snippet:
            if line.startswith(_SNIPPET_END):
                state = _State.normal

                content = linesep.join(current_lines)
                snippet = ParsedSnippet(
                    grammar="snu",
                    content=content,
                    label=current_label,
                    doc="",
                    matches={current_name},
                    options=current_opts - {""},
                )
                snippets.append(snippet)
                current_lines.clear()

            else:
                current_lines.append(line)

        elif state == _State.pglobal:
            if line.startswith(_GLOBAL_END):
                state = _State.normal
            else:
                pass

        else:
            assert False

    return extends, snippets
