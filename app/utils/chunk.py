from typing import Iterable, List, TypeVar
T = TypeVar("T")

def chunked(items: Iterable[T], size: int):
    buf: List[T] = []
    for x in items:
        buf.append(x)
        if len(buf) >= size:
            yield buf
            buf = []
    if buf:
        yield buf
