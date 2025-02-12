from pathlib import Path
from typing import Optional, cast

from pynvim import Nvim

from ...registry import atomic
from ...shared.types import Doc
from ..parse import doc
from ..types import CompletionItem
from .request import async_request

_LUA = (Path(__file__).resolve().parent / "preview.lua").read_text("UTF-8")

atomic.exec_lua(_LUA, ())


async def request(nvim: Nvim, item: CompletionItem) -> Optional[Doc]:
    stream = async_request(nvim, "COQlsp_preview", item)
    async for reply in stream:
        if reply:
            break
    else:
        reply = None

    if reply:
        resp = cast(CompletionItem, reply)
        return doc(resp)
    else:
        return None
