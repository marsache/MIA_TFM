"""
RAG (Retrieval-Augmented Generation) engine for the local song dataset.

Provides a simple TF-IDF–style full-text search over the song catalogue so
that the MCP tools can retrieve the most relevant songs for any user query
without requiring an external vector database or embedding model.

Usage::

    from rag_engine import RAGEngine
    engine = RAGEngine()            # loads and indexes the dataset
    results = engine.search("marzas")          # returns list of song dicts
    song = engine.get_by_id(42)               # single song by id
    cats = engine.list_categories()           # all distinct categories

Indexing strategy
-----------------
Each song document is converted into a bag-of-words (lowercased tokens).
At query time the query is similarly tokenised and each document is scored
by the sum of token matches weighted by inverse-document-frequency (IDF).
A secondary fuzzy pass (difflib ratio) is applied when no exact token
overlap is found, so that near-spellings are still caught.
"""

from __future__ import annotations

import math
import re
import difflib
from collections import defaultdict
from typing import Any

from dataset_parser import load_dataset
from config import RAG_MAX_RESULTS, RAG_FUZZY_THRESHOLD

# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

_TOKEN_RE = re.compile(r"[a-záéíóúüñàèìòùâêîôû0-9]+", re.IGNORECASE)


def _tokenise(text: str) -> list[str]:
    """Return lowercased word tokens from *text*, stripping punctuation."""
    return _TOKEN_RE.findall(text.lower())


def _song_text(song: dict) -> str:
    """Concatenate all searchable fields of a song into a single string."""
    parts = [
        song.get("title", ""),
        song.get("collection", ""),
        song.get("subcollection", ""),
        song.get("category", ""),
        song.get("key", ""),
        song.get("time_signature", ""),
        song.get("lyrics", ""),
        str(song.get("tempo_bpm", "") or ""),
    ]
    return " ".join(p for p in parts if p)


# ---------------------------------------------------------------------------
# RAGEngine
# ---------------------------------------------------------------------------

class RAGEngine:
    """In-memory search engine over the local song dataset."""

    def __init__(self) -> None:
        self._songs: list[dict] = load_dataset()
        self._by_id: dict[int, dict] = {s["id"]: s for s in self._songs}
        self._build_index()

    # ── Index construction ────────────────────────────────────────────────

    def _build_index(self) -> None:
        """Build an inverted TF-IDF index over all songs."""
        N = len(self._songs)
        # term → set of song ids
        doc_freq: dict[str, int] = defaultdict(int)
        # song_id → {term → count}
        tf: dict[int, dict[str, int]] = {}

        for song in self._songs:
            tokens = _tokenise(_song_text(song))
            counts: dict[str, int] = defaultdict(int)
            for tok in tokens:
                counts[tok] += 1
            tf[song["id"]] = dict(counts)
            for tok in set(counts):
                doc_freq[tok] += 1

        # idf(term) = log((N + 1) / (df + 1)) + 1  (smoothed)
        idf: dict[str, float] = {
            term: math.log((N + 1) / (df + 1)) + 1
            for term, df in doc_freq.items()
        }

        # Precompute TF-IDF vectors
        self._tfidf: dict[int, dict[str, float]] = {}
        for sid, counts in tf.items():
            total = sum(counts.values()) or 1
            self._tfidf[sid] = {
                term: (count / total) * idf[term]
                for term, count in counts.items()
            }

        self._idf = idf
        # Keep a flat token list per song for fuzzy fallback
        self._song_tokens: dict[int, set[str]] = {
            song["id"]: set(_tokenise(_song_text(song)))
            for song in self._songs
        }
        # All unique terms (for fuzzy query expansion)
        self._all_terms: list[str] = list(doc_freq.keys())

    # ── Public search API ─────────────────────────────────────────────────

    def search(
        self,
        query: str,
        max_results: int = RAG_MAX_RESULTS,
        *,
        collection: str = "",
        category: str = "",
        key: str = "",
        time_signature: str = "",
    ) -> list[dict]:
        """Full-text search over the song dataset.

        Optional keyword arguments restrict results to songs matching a
        specific collection, category, key, or time signature (case-
        insensitive substring match for string fields).

        Returns at most *max_results* songs sorted by relevance score.
        """
        query = query.strip()
        candidates = self._apply_filters(collection, category, key, time_signature)

        if not query:
            return self._truncate(list(candidates.values()), max_results)

        query_tokens = _tokenise(query)
        # Expand tokens via fuzzy matching against index vocabulary
        expanded = self._expand_query(query_tokens)

        scores: dict[int, float] = {}
        for sid, song in candidates.items():
            score = self._score(sid, expanded, query)
            if score > 0:
                scores[sid] = score

        if not scores:
            # Fuzzy fallback: score by title similarity only
            q_lower = query.lower()
            for sid, song in candidates.items():
                ratio = difflib.SequenceMatcher(
                    None, q_lower, song.get("title", "").lower()
                ).ratio()
                if ratio >= RAG_FUZZY_THRESHOLD:
                    scores[sid] = ratio

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [self._by_id[sid] for sid, _ in ranked[:max_results]]

    def get_by_id(self, song_id: int) -> dict | None:
        """Return the song with *song_id*, or ``None`` if not found."""
        return self._by_id.get(song_id)

    def list_categories(self) -> dict[str, Any]:
        """Return a summary of all collections, categories, and subcollections."""
        collections: dict[str, dict] = {}
        for song in self._songs:
            coll = song["collection"]
            cat = song["category"]
            subcat = song["subcollection"]
            if coll not in collections:
                collections[coll] = {"total": 0, "categories": {}}
            collections[coll]["total"] += 1
            if cat:
                cats = collections[coll]["categories"]
                if cat not in cats:
                    cats[cat] = {"total": 0, "subcategories": set()}
                cats[cat]["total"] += 1
                if subcat:
                    cats[cat]["subcategories"].add(subcat)

        # Convert sets to sorted lists for JSON serialisation
        for coll in collections.values():
            for cat in coll["categories"].values():
                cat["subcategories"] = sorted(cat["subcategories"])

        return collections

    def get_statistics(self) -> dict:
        """Return aggregate statistics about the dataset."""
        keys: dict[str, int] = defaultdict(int)
        times: dict[str, int] = defaultdict(int)
        for song in self._songs:
            if song["key"]:
                keys[song["key"]] += 1
            if song["time_signature"]:
                times[song["time_signature"]] += 1

        with_lyrics = sum(1 for s in self._songs if s["lyrics"].strip())
        return {
            "total_songs": len(self._songs),
            "songs_with_lyrics": with_lyrics,
            "key_distribution": dict(sorted(keys.items(), key=lambda x: -x[1])),
            "time_signature_distribution": dict(
                sorted(times.items(), key=lambda x: -x[1])
            ),
        }

    # ── Private helpers ───────────────────────────────────────────────────

    def _apply_filters(
        self,
        collection: str,
        category: str,
        key: str,
        time_signature: str,
    ) -> dict[int, dict]:
        """Return the subset of songs matching all non-empty filter values."""
        result: dict[int, dict] = {}
        coll_l = collection.lower()
        cat_l = category.lower()
        key_l = key.lower()
        ts_l = time_signature.lower()
        for song in self._songs:
            if coll_l and coll_l not in song.get("collection", "").lower():
                continue
            if cat_l and cat_l not in (
                song.get("category", "") + " " + song.get("subcollection", "")
            ).lower():
                continue
            if key_l and key_l not in song.get("key", "").lower():
                continue
            if ts_l and ts_l not in song.get("time_signature", "").lower():
                continue
            result[song["id"]] = song
        return result

    def _expand_query(self, tokens: list[str]) -> list[str]:
        """Return *tokens* plus close vocabulary matches (fuzzy expansion)."""
        expanded = list(tokens)
        for tok in tokens:
            if tok in self._idf:
                continue  # exact match – no expansion needed
            # find the closest terms in the vocabulary
            close = difflib.get_close_matches(tok, self._all_terms, n=3, cutoff=0.75)
            expanded.extend(close)
        return expanded

    def _score(self, song_id: int, query_tokens: list[str], raw_query: str) -> float:
        """Compute a relevance score for *song_id* given *query_tokens*."""
        vec = self._tfidf.get(song_id, {})
        score = sum(vec.get(tok, 0.0) for tok in query_tokens)

        # Bonus for title substring match
        song = self._by_id[song_id]
        title_lower = song.get("title", "").lower()
        if raw_query.lower() in title_lower:
            score += 2.0
        elif any(tok in title_lower for tok in query_tokens):
            score += 0.5

        return score

    @staticmethod
    def _truncate(songs: list[dict], max_results: int) -> list[dict]:
        return songs[:max_results]
