"""A tiny, dependency-free TF-IDF retriever over the published knowledge base.

V1 uses pure-Python TF-IDF so the coach can ground its answers with no external
embedding service. Swap point: replace `KnowledgeIndex` with a vector store later.
The index is rebuilt whenever knowledge changes (see admin routes / seed).
"""
import math
import re
from collections import Counter
from threading import Lock

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOP = set(
    "the a an and or of to in is it for on with as at by from that this be are was "
    "you your i we they he she his her its our their not no do does did how what when "
    "where why which who will would can could should into than then them out up down "
    "if so but about over under more most some any all just like get got".split()
)


def tokenize(text):
    return [w for w in _WORD_RE.findall((text or "").lower()) if w not in _STOP and len(w) > 1]


def _chunk(text, target_words=160, max_words=240):
    """Split on blank lines, then pack paragraphs into ~target_words chunks."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text or "") if p.strip()]
    chunks, cur, n = [], [], 0
    for p in paras:
        wc = len(p.split())
        if cur and n + wc > max_words:
            chunks.append("\n\n".join(cur))
            cur, n = [], 0
        cur.append(p)
        n += wc
        if n >= target_words:
            chunks.append("\n\n".join(cur))
            cur, n = [], 0
    if cur:
        chunks.append("\n\n".join(cur))
    return chunks or ([text.strip()] if (text or "").strip() else [])


class KnowledgeIndex:
    def __init__(self):
        self._lock = Lock()
        self._chunks = []      # list of dicts: {entry_id, title, category, text, tf}
        self._idf = {}
        self._n = 0

    def build(self, entries):
        """entries: iterable of objects with .id .title .category .content"""
        chunks = []
        for e in entries:
            for ct in _chunk(e.content):
                toks = tokenize(e.title + " " + ct)
                if not toks:
                    continue
                tf = Counter(toks)
                chunks.append({
                    "entry_id": e.id, "title": e.title, "category": e.category,
                    "text": ct, "tf": tf, "len": len(toks),
                })
        df = Counter()
        for c in chunks:
            for term in c["tf"]:
                df[term] += 1
        n = max(len(chunks), 1)
        idf = {t: math.log((n + 1) / (dfc + 1)) + 1.0 for t, dfc in df.items()}
        with self._lock:
            self._chunks, self._idf, self._n = chunks, idf, n

    def _vec(self, tf):
        return {t: (f / max(sum(tf.values()), 1)) * self._idf.get(t, 0.0) for t, f in tf.items()}

    def search(self, query, k=4):
        with self._lock:
            chunks, idf = self._chunks, self._idf
        if not chunks:
            return []
        q_tf = Counter(tokenize(query))
        if not q_tf:
            return []
        q_vec = {t: (f / sum(q_tf.values())) * idf.get(t, 0.0) for t, f in q_tf.items()}
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0
        scored = []
        for c in chunks:
            d_vec = self._vec(c["tf"])
            d_norm = math.sqrt(sum(v * v for v in d_vec.values())) or 1.0
            dot = sum(q_vec.get(t, 0.0) * d_vec.get(t, 0.0) for t in q_vec)
            score = dot / (q_norm * d_norm)
            if score > 0:
                scored.append((score, c))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            {"score": round(s, 4), "title": c["title"], "category": c["category"],
             "text": c["text"], "entry_id": c["entry_id"]}
            for s, c in scored[:k]
        ]

    @property
    def size(self):
        return len(self._chunks)


# Module-level singleton; (re)built at app start and on knowledge edits.
index = KnowledgeIndex()


def rebuild_index(app=None):
    """Rebuild the retrieval index from published knowledge."""
    from .models import KnowledgeEntry
    entries = KnowledgeEntry.query.filter_by(published=True).all()
    index.build(entries)
    return index.size
