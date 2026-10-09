from collections import OrderedDict
from threading import Lock
from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

_embedding = DefaultEmbeddingFunction()
_cache = OrderedDict()
_lock = Lock()
_MAX_CACHE = 128


def create_embedding(text):
    key = str(text)
    with _lock:
        if key in _cache:
            value = _cache.pop(key)
            _cache[key] = value
            return value
    value = _embedding([key])[0]
    with _lock:
        _cache[key] = value
        while len(_cache) > _MAX_CACHE:
            _cache.popitem(last=False)
    return value


def create_embeddings_batch(texts):
    return _embedding([str(x) for x in texts])


def clear_embedding_cache():
    with _lock:
        _cache.clear()
