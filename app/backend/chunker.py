import re

DEFAULT_CHUNK_SIZE = 2200
DEFAULT_OVERLAP = 350


def _clean(s):
    return re.sub(r'\n{3,}', '\n\n', (s or '').replace('\x00', ' ')).strip()


def _cut(text, target):
    if len(text) <= target:
        return len(text)
    for sep in ('\n\n', '\n', '. ', '; ', ' '):
        pos = text.rfind(sep, 0, target)
        if pos >= int(target * 0.65):
            return pos + len(sep)
    return target


def create_chunks(pages, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP, **kwargs):
    if "chunk_overlap" in kwargs:
        overlap = kwargs["chunk_overlap"]
    chunks = []
    idx = 0
    for page in pages:
        text = _clean(page.get('text', ''))
        if not text:
            continue
        start = 0
        while start < len(text):
            end = _cut(text, min(len(text), start + chunk_size))
            part = text[start:end].strip()
            if part:
                chunks.append({
                    'text': part,
                    'page': int(page['page']),
                    'chunk_index': idx,
                    'chunk_id': f"chunk_{idx}",
                    'section': page.get('section', f"Page {page['page']}")
                })
                idx += 1
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks


def get_chunk_count(pages, chunk_size=DEFAULT_CHUNK_SIZE, overlap=DEFAULT_OVERLAP):
    return len(create_chunks(pages, chunk_size, overlap))

