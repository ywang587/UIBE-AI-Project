"""Simplify reading copies; identifiers, source files and downloads stay original."""
from functools import lru_cache
from opencc import OpenCC

_converter = OpenCC('t2s')
_text_fields = {
    'title', 'video_title', 'name', 'author_name', 'author', 'summary', 'statement', 'quote', 'text',
    'reason', 'limitation', 'limitations', 'conditions', 'time_horizon',
    'classification_note', 'draft_statement', 'suspect', 'note', 'assets',
    'event', 'left_title', 'right_title', 'scope', 'kind', 'method',
}


@lru_cache(maxsize=4096)
def simplify(text):
    return _converter.convert(text)


def reading_copy(value, field=''):
    if isinstance(value, dict):
        return {key: reading_copy(item, key) for key, item in value.items()}
    if isinstance(value, list):
        return [reading_copy(item, field) for item in value]
    if isinstance(value, str) and field in _text_fields:
        return simplify(value)
    return value
