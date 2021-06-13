from concurrent.futures import CancelledError, Future, InvalidStateError
from contextlib import suppress
from json import loads
from threading import Lock
from typing import Any, Iterator, MutableMapping, Sequence, Tuple
from uuid import UUID, uuid4

from pynvim import Nvim
from std2.pickle import DecodeError, decode

from ...consts import ARTIFACTS_DIR
from ...shared.runtime import Supervisor
from ...shared.runtime import Worker as BaseWorker
from ...shared.types import Completion, Context, Edit, NvimPos, RangeEdit
from .runtime import LSP
from .types import CompletionItem, CompletionList, Resp, TextEdit

_LSP_ARTIFACTS = ARTIFACTS_DIR / "lsp.json"

_LSP: LSP = decode(LSP, loads(_LSP_ARTIFACTS.read_text("UTF-8")))


def _req(nvim: Nvim, token: UUID, pos: NvimPos) -> Resp:
    nvim.api.exec_lua("")


def _range_edit(edit: TextEdit) -> RangeEdit:
    begin = edit.range.start.line, edit.range.end.character
    end = edit.range.end.line, edit.range.end.character
    return RangeEdit(new_text=edit.newText, begin=begin, end=end)


def _primary(item: CompletionItem) -> Edit:
    if isinstance(item.textEdit, TextEdit):
        return _range_edit(item.textEdit)
    elif item.insertText:
        return Edit(new_text=item.insertText)
    else:
        return Edit(new_text=item.label)


def _parse_item(pos: NvimPos, item: CompletionItem) -> Completion:
    primary = _primary(item)
    secondaries = tuple(map(_range_edit, item.additionalTextEdits or ()))

    label = item.label
    short_label = _LSP.cmp_item_kind.lookup.get(item.kind, _LSP.cmp_item_kind.default) if item.kind else ""

    doc = item.detail or ""
    doc_type = "markdown"

    cmp = Completion(
        position=pos,
        primary_edit=primary,
        secondary_edits=secondaries,
        label=label,
        short_label=short_label,
        doc=doc,
        doc_type=doc_type,
    )
    return cmp


def _parse(pos: NvimPos, reply: Any) -> Tuple[bool, Sequence[Completion]]:
    try:
        resp: Resp = decode(Resp, reply, strict=False)
    except DecodeError:
        raise
    else:
        if isinstance(resp, CompletionList):
            return resp.isIncomplete, tuple(
                _parse_item(pos, item=item) for item in resp.items
            )
        elif isinstance(resp, Sequence):
            return False, tuple(_parse_item(pos, item=item) for item in resp)
        else:
            return False, ()


class Worker(BaseWorker[None]):
    def __init__(self, supervisor: Supervisor, misc: None) -> None:
        self._lock = Lock()
        self._pending: MutableMapping[UUID, Future] = {}
        super().__init__(supervisor, misc=misc)

    def notify(self, token: UUID, msg: Sequence[Any]) -> None:
        with self._lock:
            if token in self._pending:
                reply, *_ = msg
                with suppress(InvalidStateError):
                    self._pending[token].set_result(reply)

    def work(self, context: Context) -> Iterator[Sequence[Completion]]:
        yield ()

        token = uuid4()
        fut: Future = Future()

        def cont(fut: Future) -> None:
            with self._lock:
                if token in self._pending:
                    self._pending.pop(token)
            try:
                ret = fut.result()
            except CancelledError:
                pass

        fut.add_done_callback(cont)
        with self._lock:
            self._pending[token] = fut

        _req(self._supervisor.nvim, token=token, pos=context.position)

