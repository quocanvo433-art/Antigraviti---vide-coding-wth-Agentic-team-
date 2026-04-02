"""
DNA Header v16.7 - Sovereign Purity
Role: ENGRAM_RAG (Trí nhớ dài hạn)
Layer: 4 (Memory & Recall)

EngramRAG — Hệ thống trí nhớ dài hạn của Opus.
Lưu trữ engram (kinh nghiệm, bài học, checkpoint) và truy xuất bằng TF-IDF.
Zero VRAM — thuần Python, không cần embedding model.

Mỗi engram = 1 JSON nhỏ trong .opus/engrams/
Index = .opus/engrams/_index.jsonl (append-only cho tốc độ)
"""

import json
import math
import os
import re
import sys
from collections import Counter
from datetime import datetime

sys.path.insert(0, os.path.dirname(__file__))
from opus_lang import encode_log_entry


class EngramRAG:
    """
    Trí nhớ dài hạn (Layer 4).

    Lưu trữ kinh nghiệm và truy xuất bằng TF-IDF thuần Python.
    Không cần ChromaDB, không cần embedding model, zero VRAM.
    """

    def __init__(self, engram_dir=".opus/engrams"):
        self.engram_dir = engram_dir
        self.index_path = os.path.join(engram_dir, "_index.jsonl")
        os.makedirs(engram_dir, exist_ok=True)

    # ── Store ─────────────────────────────────────────────────────
    def store(self, category: str, content: str,
              tags: list = None, metadata: dict = None) -> str:
        """Lưu engram mới.

        Args:
            category: "lesson" | "checkpoint" | "session" | "handover" | "error"
            content: Nội dung (có thể là OpusLang)
            tags: Tags cho tìm kiếm (e.g., ["a04", "dna", "fix"])
            metadata: Thông tin bổ sung

        Returns:
            Engram ID
        """
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        engram_id = f"{category}_{ts}"

        engram = {
            "id": engram_id,
            "ts": datetime.now().isoformat(),
            "category": category,
            "content": content,
            "tags": tags or [],
            "metadata": metadata or {},
        }

        # Save full engram
        path = os.path.join(self.engram_dir, f"{engram_id}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(engram, f, indent=2, ensure_ascii=False)

        # Append to index (lightweight: id + content + tags for search)
        index_entry = {
            "id": engram_id,
            "category": category,
            "content": content,
            "tags": tags or [],
            "ts": engram["ts"],
        }
        with open(self.index_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(index_entry, ensure_ascii=False) + "\n")

        return engram_id

    # ── Recall (TF-IDF Search) ────────────────────────────────────
    def recall(self, query: str, top_k: int = 3,
               category_filter: str = None) -> list:
        """Truy xuất engrams liên quan nhất bằng TF-IDF.

        Args:
            query: Câu hỏi / từ khóa tìm kiếm
            top_k: Số kết quả trả về
            category_filter: Lọc theo category (optional)

        Returns:
            List of (score, engram_dict) sorted by relevance
        """
        index = self._load_index()
        if not index:
            return []

        # Filter by category if specified
        if category_filter:
            index = [e for e in index if e["category"] == category_filter]

        if not index:
            return []

        # Tokenize query
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        # Build corpus for IDF calculation
        corpus_tokens = []
        for entry in index:
            doc_text = f"{entry['content']} {' '.join(entry.get('tags', []))}"
            corpus_tokens.append(self._tokenize(doc_text))

        # Calculate IDF for each query term
        n_docs = len(corpus_tokens)
        idf = {}
        for token in query_tokens:
            df = sum(1 for doc_tokens in corpus_tokens if token in doc_tokens)
            idf[token] = math.log((n_docs + 1) / (df + 1)) + 1

        # Score each document
        scored = []
        for i, entry in enumerate(index):
            doc_tokens = corpus_tokens[i]
            doc_counter = Counter(doc_tokens)
            max_freq = max(doc_counter.values()) if doc_counter else 1

            score = 0.0
            for token in query_tokens:
                tf = doc_counter.get(token, 0) / max_freq  # Normalized TF
                score += tf * idf.get(token, 0)

            # Bonus for tag match
            if entry.get("tags"):
                tag_matches = sum(1 for t in entry["tags"]
                                  if any(qt in t.lower() for qt in query_tokens))
                score += tag_matches * 0.5

            if score > 0:
                scored.append((score, entry))

        # Sort by score descending, return top_k
        scored.sort(key=lambda x: -x[0])
        return scored[:top_k]

    # ── Specialized Queries ───────────────────────────────────────
    def lessons_learned(self, topic: str = "", top_k: int = 5) -> list:
        """Truy xuất bài học từ engrams có category='lesson'."""
        if topic:
            return self.recall(topic, top_k=top_k, category_filter="lesson")
        # Return all lessons sorted by time
        index = self._load_index()
        lessons = [e for e in index if e["category"] == "lesson"]
        return [(1.0, l) for l in sorted(lessons, key=lambda x: x["ts"], reverse=True)[:top_k]]

    def recent_sessions(self, n: int = 5) -> list:
        """Lấy n session gần nhất."""
        index = self._load_index()
        sessions = [e for e in index if e["category"] == "session"]
        return sorted(sessions, key=lambda x: x["ts"], reverse=True)[:n]

    # ── Learn (Store a Lesson) ────────────────────────────────────
    def learn(self, lesson: str, context: str = "", tags: list = None) -> str:
        """Rút kinh nghiệm — lưu bài học.

        Args:
            lesson: Bài học ngắn gọn
            context: Ngữ cảnh xảy ra
            tags: Tags phân loại

        Returns:
            Engram ID
        """
        content = f"LESSON: {lesson}"
        if context:
            content += f"\nCONTEXT: {context}"
        return self.store("lesson", content, tags=tags,
                          metadata={"learned_at": datetime.now().isoformat()})

    # ── Stats ─────────────────────────────────────────────────────
    def stats(self) -> dict:
        """Thống kê engram."""
        index = self._load_index()
        categories = Counter(e["category"] for e in index)
        return {
            "total": len(index),
            "by_category": dict(categories),
            "index_size_bytes": os.path.getsize(self.index_path) if os.path.exists(self.index_path) else 0,
        }

    # ── Internal ──────────────────────────────────────────────────
    def _load_index(self) -> list:
        """Load index from JSONL file."""
        if not os.path.exists(self.index_path):
            return []
        entries = []
        with open(self.index_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
        return entries

    @staticmethod
    def _tokenize(text: str) -> list:
        """Simple tokenizer: lowercase, split on non-alphanumeric."""
        return [t for t in re.split(r'[^a-zA-Z0-9_àáạảãâầấậẩẫăằắặẳẵèéẹẻẽêềếệểễìíịỉĩòóọỏõôồốộổỗơờớợởỡùúụủũưừứựửữỳýỵỷỹđ]+', text.lower()) if len(t) > 1]


# ── CLI ───────────────────────────────────────────────────────────
if __name__ == "__main__":
    rag = EngramRAG()

    if len(sys.argv) < 2 or sys.argv[1] == "demo":
        print("═══ EngramRAG Demo ═══\n")

        # Store some engrams
        rag.store("session", "A→C | fix(a04.brain):syn✓dna✓ | P:boost_prompt",
                  tags=["a04", "brain", "fix", "syntax", "dna"])
        rag.store("session", "C→D | test(genesis):PASS(3/3) | P:none",
                  tags=["genesis", "test", "pass"])
        rag.learn("Khi sửa syntax error trong a04, luôn chạy AST parse trước khi commit",
                  context="Phiên v16.7: mất 30 phút vì quên kiểm tra AST",
                  tags=["a04", "syntax", "ast", "lesson"])
        rag.learn("ChromaDB cần embedding model → dùng TF-IDF thuần Python để tiết kiệm VRAM",
                  context="RTX 5000 Ada 16GB chỉ còn 10GB cho A08 training",
                  tags=["chromadb", "vram", "rag", "optimization"])
        rag.store("error", "D→C | audit(agentic/*):syn✓dna✗(2) | P:fix_headers",
                  tags=["audit", "dna", "fail", "agentic"])

        # Stats
        s = rag.stats()
        print(f"Stored: {s['total']} engrams | Categories: {s['by_category']}\n")

        # Recall
        print("── Query: 'a04 syntax error fix' ──")
        results = rag.recall("a04 syntax error fix")
        for score, entry in results:
            print(f"  [{score:.2f}] ({entry['category']}) {entry['content'][:80]}")

        print("\n── Query: 'VRAM optimization' ──")
        results = rag.recall("VRAM optimization")
        for score, entry in results:
            print(f"  [{score:.2f}] ({entry['category']}) {entry['content'][:80]}")

        print("\n── Lessons Learned ──")
        lessons = rag.lessons_learned()
        for score, entry in lessons:
            print(f"  {entry['content'][:90]}")

    elif sys.argv[1] == "stats":
        s = rag.stats()
        print(json.dumps(s, indent=2))

    elif sys.argv[1] == "recall" and len(sys.argv) >= 3:
        query = " ".join(sys.argv[2:])
        results = rag.recall(query)
        for score, entry in results:
            print(f"[{score:.2f}] ({entry['category']}) {entry['content'][:100]}")

    elif sys.argv[1] == "learn" and len(sys.argv) >= 3:
        lesson = " ".join(sys.argv[2:])
        eid = rag.learn(lesson)
        print(f"Lesson stored: {eid}")

    elif sys.argv[1] == "store" and len(sys.argv) >= 3:
        # Lưu engram trực tiếp: python3 engram_rag.py store "nội dung" [tag1,tag2]
        content = sys.argv[2]
        tags = sys.argv[3].split(",") if len(sys.argv) > 3 else []
        eid = rag.store("session", content, tags=tags)
        print(f"✅ Engram lưu: {eid}")

    elif sys.argv[1] == "handover" and len(sys.argv) >= 3:
        # Bàn giao giữa models: python3 engram_rag.py handover "tóm tắt" [tag1,tag2]
        content = sys.argv[2]
        tags = sys.argv[3].split(",") if len(sys.argv) > 3 else ["handover"]
        if "handover" not in tags:
            tags.append("handover")
        eid = rag.store("handover", content, tags=tags)
        print(f"🤝 Bàn giao lưu: {eid}")
        print(f"   Phiên sau chạy: python3 engram_rag.py recall 'handover'")

    else:
        print("Cách dùng:")
        print("  python3 engram_rag.py demo           — Chạy demo")
        print("  python3 engram_rag.py stats           — Thống kê")
        print('  python3 engram_rag.py recall "query"   — Tìm kiếm')
        print('  python3 engram_rag.py learn "lesson"   — Lưu bài học')
        print('  python3 engram_rag.py store "content"   — Lưu engram')
        print('  python3 engram_rag.py handover "brief"  — Bàn giao inter-model')
