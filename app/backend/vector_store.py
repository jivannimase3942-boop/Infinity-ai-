import hashlib
import json
import re
import shutil
import time
from pathlib import Path
from typing import Optional, Dict, Any

import chromadb

from backend.embeddings import create_embedding, create_embeddings_batch

BASE_DIR = Path(__file__).resolve().parent.parent
CHROMA_DIR = BASE_DIR / "chroma_db"
COLLECTION_NAME = "infinity_ai_documents"
_client = chromadb.PersistentClient(path=str(CHROMA_DIR))
_collection = _client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def verify_and_isolate_chroma(current_device_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Verifies that the ChromaDB vector store belongs to the current machine.
    If the collection is from another computer:
    - Quarantines the foreign chroma_db directory to chroma_db_quarantined_<foreign_id>_<timestamp>/.
    - Initializes a fresh, empty collection for this computer.
    """
    global _client, _collection, _keyword_cache
    from backend.security import get_device_id, get_workspace_id
    dev_id = current_device_id or get_device_id()
    ws_id = get_workspace_id()
    marker_file = CHROMA_DIR / ".chroma_workspace_identity.json"

    if CHROMA_DIR.exists() and marker_file.exists():
        try:
            with open(marker_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            foreign_id = data.get("device_id")
            if foreign_id and foreign_id != dev_id:
                # FOREIGN CHROMADB DETECTED!
                ts = time.strftime("%Y%m%d_%H%M%S")
                quarantine_dir = BASE_DIR / f"chroma_db_quarantined_{foreign_id[:8]}_{ts}"
                _client = None
                _collection = None
                _keyword_cache.clear()
                shutil.move(str(CHROMA_DIR), str(quarantine_dir))
                CHROMA_DIR.mkdir(parents=True, exist_ok=True)
                with open(marker_file, "w", encoding="utf-8") as f:
                    json.dump({"device_id": dev_id, "workspace_id": ws_id, "created_at": ts}, f, indent=2)
                _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
                _collection = _client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})
                return {"status": "quarantined_foreign_chroma", "foreign_device_id": foreign_id, "quarantine_path": str(quarantine_dir)}
            else:
                return {"status": "valid", "device_id": dev_id}
        except Exception:
            pass

    # If chroma_db exists without marker file (current machine baseline)
    if CHROMA_DIR.exists():
        try:
            with open(marker_file, "w", encoding="utf-8") as f:
                json.dump({"device_id": dev_id, "workspace_id": ws_id, "created_at": time.strftime("%Y%m%d_%H%M%S")}, f, indent=2)
        except Exception:
            pass
    return {"status": "bound", "device_id": dev_id}


def document_hash(path):
    h = hashlib.sha256()
    with open(path, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def make_chunk_id(doc_id, chunk_index):
    return f"{doc_id}:{chunk_index}"


_STOP_WORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and",
    "any", "are", "aren't", "as", "at", "be", "because", "been", "before", "being",
    "below", "between", "both", "but", "by", "can", "can't", "cannot", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't", "down",
    "during", "each", "few", "for", "from", "further", "had", "hadn't", "has",
    "hasn't", "have", "haven't", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "isn't", "it",
    "its", "itself", "let's", "me", "more", "most", "mustn't", "my", "myself",
    "no", "nor", "not", "of", "off", "on", "once", "only", "or", "other", "ought",
    "our", "ours", "ourselves", "out", "over", "own", "same", "shan't", "she",
    "should", "shouldn't", "so", "some", "such", "than", "that", "the", "their",
    "theirs", "them", "themselves", "then", "there", "these", "they", "this",
    "those", "through", "to", "too", "under", "until", "up", "very", "was",
    "wasn't", "we", "were", "weren't", "what", "when", "where", "which", "while",
    "who", "whom", "why", "with", "won't", "would", "wouldn't", "you", "your",
    "yours", "yourself", "yourselves"
}


def _tokens(value):
    tokens = set(re.findall(r"[a-zA-Z0-9]{2,}", (value or "").lower()))
    content_tokens = tokens - _STOP_WORDS
    return content_tokens if content_tokens else tokens


def document_exists(doc_id):
    data = _collection.get(where={"doc_id": doc_id}, include=[])
    return bool(data.get("ids"))


def get_document_hash(doc_id):
    data = _collection.get(where={"doc_id": doc_id}, include=["metadatas"], limit=1)
    metas = data.get("metadatas") or []
    return metas[0].get("document_hash") if metas else None


def document_needs_indexing(doc_id, file_path):
    return get_document_hash(doc_id) != document_hash(file_path)


_keyword_cache = {}


def _populate_keyword_cache_for_doc(doc_id):
    where = {"doc_id": doc_id} if doc_id else None
    data = _collection.get(where=where, include=["documents", "metadatas"])
    docs = data.get("documents") or []
    metas = data.get("metadatas") or []
    for text, meta in zip(docs, metas):
        did = meta.get("doc_id", "default")
        if did not in _keyword_cache:
            _keyword_cache[did] = []
        _keyword_cache[did].append({
            "text": text,
            "page": meta.get("page", 1),
            "filename": meta.get("filename", meta.get("document_name", "")),
            "doc_id": did,
            "document_id": meta.get("document_id", did),
            "chunk_id": meta.get("chunk_id", ""),
            "source": meta.get("source", meta.get("document_name", "")),
            "tokens": _tokens(text),
        })


def remove_document_chunks(doc_id):
    _collection.delete(where={"doc_id": doc_id})
    _keyword_cache.pop(doc_id, None)


def add_chunks(chunks, doc_id, document_name, source_path=None, doc_hash=None):
    if not chunks:
        return 0
    remove_document_chunks(doc_id)
    dh = doc_hash or (document_hash(source_path) if source_path else "")
    ids, texts, metadatas = [], [], []
    cached_entries = []
    for index, chunk in enumerate(chunks):
        chunk_index = int(chunk.get("chunk_index", index))
        cid = make_chunk_id(doc_id, chunk_index)
        ids.append(cid)
        text = chunk["text"]
        page = int(chunk.get("page", 1))
        texts.append(text)
        metadatas.append({
            "doc_id": doc_id,
            "document_id": doc_id,
            "document_name": document_name,
            "filename": document_name,
            "source": document_name,
            "document_hash": dh,
            "page": page,
            "page_number": page,
            "chunk_index": chunk_index,
            "chunk_id": cid,
        })
        cached_entries.append({
            "text": text,
            "page": page,
            "filename": document_name,
            "doc_id": doc_id,
            "document_id": doc_id,
            "chunk_id": cid,
            "source": document_name,
            "tokens": _tokens(text),
        })
    _keyword_cache[doc_id] = cached_entries

    for start in range(0, len(ids), 64):
        end = start + 64
        _collection.add(
            ids=ids[start:end],
            documents=texts[start:end],
            metadatas=metadatas[start:end],
            embeddings=create_embeddings_batch(texts[start:end]),
        )
    return len(ids)


def index_document(chunks, doc_id, document_name, source_path):
    return add_chunks(chunks, doc_id, document_name, source_path)


def vector_search(query, n_results=5, doc_id=None, query_embedding=None):
    if _collection.count() == 0:
        return []
    where = {"doc_id": doc_id} if doc_id else None
    emb = query_embedding if query_embedding is not None else create_embedding(query)
    result = _collection.query(
        query_embeddings=[emb],
        n_results=max(1, min(n_results, 8)),
        where=where,
        include=["documents", "metadatas", "distances"],
    )
    docs = result.get("documents", [[]])[0]
    metas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    return [
        {
            "text": text,
            "page": meta.get("page", meta.get("page_number", 1)),
            "filename": meta.get("filename", meta.get("document_name", "")),
            "doc_id": meta.get("doc_id", meta.get("document_id", "")),
            "document_id": meta.get("document_id", meta.get("doc_id", "")),
            "chunk_id": meta.get("chunk_id", ""),
            "source": meta.get("source", meta.get("document_name", "")),
            "score": round(1 - float(distance), 4)
        }
        for text, meta, distance in zip(docs, metas, distances)
    ]



def keyword_search(query, n_results=5, doc_id=None):
    if _collection.count() == 0:
        return []
    if doc_id:
        if doc_id not in _keyword_cache:
            _populate_keyword_cache_for_doc(doc_id)
        candidates = _keyword_cache.get(doc_id, [])
    else:
        if not _keyword_cache:
            _populate_keyword_cache_for_doc(None)
        candidates = [item for items in _keyword_cache.values() for item in items]

    query_tokens = _tokens(query)
    if not query_tokens:
        return []
    query_len = len(query_tokens)
    scored = []
    for item in candidates:
        text_tokens = item["tokens"]
        common = len(query_tokens & text_tokens)
        if common:
            score = common / query_len
            scored.append((score, {
                "text": item["text"],
                "page": item["page"],
                "filename": item["filename"],
                "doc_id": item.get("doc_id", ""),
                "document_id": item.get("document_id", item.get("doc_id", "")),
                "chunk_id": item.get("chunk_id", ""),
                "source": item.get("source", item.get("filename", "")),
                "score": score,
            }))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [x[1] for x in scored[:n_results]]


def search_documents(query, n_results=5, doc_id=None, query_embedding=None):
    # Hybrid retrieval: vector candidates + keyword candidates, without a reranker.
    if query_embedding is None:
        query_embedding = create_embedding(query)
    vector = vector_search(query, n_results, doc_id, query_embedding=query_embedding)
    keyword = keyword_search(query, n_results, doc_id)
    merged = []
    seen = set()
    for result in vector + keyword:
        key = (result.get("page"), result.get("text", ""))
        if key in seen:
            continue
        seen.add(key)
        merged.append(result)
    merged.sort(key=lambda item: item.get("score", 0), reverse=True)
    return merged[:n_results]


def search(query, n_results=5, doc_id=None):
    return search_documents(query, n_results, doc_id)


search_chunks = search_documents


def get_all_doc_ids():
    """Return a set of every distinct doc_id stored in the collection."""
    if _collection.count() == 0:
        return set()
    if _keyword_cache:
        return set(_keyword_cache.keys())
    data = _collection.get(include=["metadatas"])
    return {m.get("doc_id") for m in (data.get("metadatas") or []) if m.get("doc_id")}


def search_documents_per_doc(query, chunks_per_doc=3, doc_ids=None):
    """Retrieve top-N chunks *per document* so every document is represented.

    Args:
        query: the user question.
        chunks_per_doc: how many chunks to pull from each document (default 3).
        doc_ids: explicit list/set of doc_ids to search. If None, searches all.

    Returns:
        list of result dicts sorted by (doc_id, page).
    """
    ids = doc_ids if doc_ids else get_all_doc_ids()
    all_results = []
    query_emb = create_embedding(query)
    for did in ids:
        results = search_documents(query, n_results=chunks_per_doc, doc_id=did, query_embedding=query_emb)
        all_results.extend(results)
    # Sort by document name then page for stable, readable context
    all_results.sort(key=lambda r: (r.get("filename", ""), r.get("page", 0)))
    return all_results



def get_collection_count():
    return _collection.count()


def get_document_chunk_count(doc_id):
    return len(_collection.get(where={"doc_id": doc_id}, include=[]).get("ids") or [])


def clear_database():
    global _collection
    try:
        _client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    _collection = _client.get_or_create_collection(name=COLLECTION_NAME, metadata={"hnsw:space": "cosine"})


def get_all_document_text(doc_id: Optional[str] = None) -> str:
    """Retrieves all chunk texts for a document or entire collection in page/chunk order."""
    try:
        if _collection.count() == 0:
            return ""
        where = {"doc_id": doc_id} if doc_id else None
        data = _collection.get(where=where, include=["documents", "metadatas"])
        docs = data.get("documents") or []
        metas = data.get("metadatas") or []
        if not docs:
            return ""
        paired = list(zip(docs, metas))
        paired.sort(key=lambda p: (int(p[1].get("page", 1)), int(p[1].get("chunk_index", 0))))
        return "\n\n".join(t.strip() for t, _ in paired if t.strip())
    except Exception:
        return ""

