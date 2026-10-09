import sqlite3
from pathlib import Path
import hashlib
from collections import OrderedDict
from threading import Lock

DB = Path(__file__).resolve().parent.parent / 'data' / 'ai_cache.db'
DB.parent.mkdir(exist_ok=True)

_mem_cache = OrderedDict()
_mem_lock = Lock()
_MAX_MEM_CACHE = 256


def _init_db():
    try:
        with sqlite3.connect(DB, timeout=10.0) as conn:
            conn.execute('PRAGMA journal_mode=WAL')
            conn.execute('PRAGMA synchronous=NORMAL')
            conn.execute(
                'CREATE TABLE IF NOT EXISTS answer_cache ('
                'cache_key TEXT PRIMARY KEY, '
                'doc_hash TEXT, '
                'query TEXT, '
                'mode TEXT, '
                'answer TEXT, '
                'created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                ')'
            )
    except Exception:
        pass

_init_db()


def make_cache_key(doc_hash, query, mode):
    return hashlib.sha256(f'{doc_hash}\0{mode}\0{query.strip().lower()}'.encode()).hexdigest()


def get_cached_answer(doc_hash, query, mode):
    key = make_cache_key(doc_hash, query, mode)
    with _mem_lock:
        if key in _mem_cache:
            val = _mem_cache.pop(key)
            _mem_cache[key] = val
            if val and ("couldn't find" in val.lower() or "unavailable" in val.lower()):
                return None
            return val
    try:
        with sqlite3.connect(DB, timeout=5.0) as conn:
            row = conn.execute('SELECT answer FROM answer_cache WHERE cache_key=?', (key,)).fetchone()
            if row:
                ans = row[0]
                if ans and ("couldn't find" in ans.lower() or "unavailable" in ans.lower()):
                    return None
                with _mem_lock:
                    _mem_cache[key] = ans
                    if len(_mem_cache) > _MAX_MEM_CACHE:
                        _mem_cache.popitem(last=False)
                return ans
    except Exception:
        pass
    return None


def save_cached_answer(doc_hash, query, mode, answer):
    # Rule 39: Zero-history mode must not accidentally reintroduce chat persistence through cache
    if not doc_hash or doc_hash in ["none", "", "general", "chat"]:
        return
    if not answer or not answer.strip():
        return
    lowered = answer.lower()
    if any(err in lowered for err in ["couldn't find", "unavailable", "traceback", "error", "failed", "could not"]):
        return
    key = make_cache_key(doc_hash, query, mode)
    with _mem_lock:
        _mem_cache[key] = answer
        if len(_mem_cache) > _MAX_MEM_CACHE:
            _mem_cache.popitem(last=False)
    try:
        with sqlite3.connect(DB, timeout=5.0) as conn:
            conn.execute(
                'INSERT OR REPLACE INTO answer_cache(cache_key, doc_hash, query, mode, answer) VALUES(?,?,?,?,?)',
                (key, doc_hash, query, mode, answer)
            )
    except Exception:
        pass

