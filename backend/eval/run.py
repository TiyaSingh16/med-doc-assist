"""Retrieval evaluation: does search return the chunk that answers the question?

    python -m eval.run --retriever minilm     # the production embedding model
    python -m eval.run --retriever keyword    # simple keyword (TF-IDF) baseline

For each question, the top-k chunks are retrieved. A hit means one of them is
on the expected page AND contains the answer keyword. Reports hit@k and MRR
(mean reciprocal rank of the first correct chunk) for several chunk sizes and
k values, so chunking choices can be justified with numbers.

Uses the app's own chunking (app.ai.embedder.split_into_chunks). The minilm
retriever needs the sentence-transformers model, downloaded from Hugging Face
on first use.
"""
import argparse
import math
import re
from collections import Counter

from app.ai import embedder
from app.services.pdf_service import PAGE_SEPARATOR
from eval.dataset import QUESTIONS, REPORTS

TOKEN = re.compile(r"[a-z0-9]+")


def tokens(text):
    return TOKEN.findall(text.lower())


class KeywordRetriever:
    """TF-IDF cosine similarity: a no-model baseline to compare against."""

    def __init__(self, chunks):
        self.chunks = chunks
        docs = [Counter(tokens(c)) for c, _ in chunks]
        df = Counter(t for d in docs for t in d)
        n = len(docs)
        self.idf = {t: math.log((n + 1) / (f + 1)) + 1 for t, f in df.items()}
        self.vectors = [self._vec(d) for d in docs]

    def _vec(self, counts):
        v = {t: c * self.idf.get(t, 0.0) for t, c in counts.items()}
        norm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        return {t: x / norm for t, x in v.items()}

    def rank(self, question):
        q = self._vec(Counter(tokens(question)))
        scores = [sum(q.get(t, 0) * x for t, x in v.items()) for v in self.vectors]
        return sorted(range(len(self.chunks)), key=lambda i: -scores[i])


class EmbeddingRetriever:
    def __init__(self, chunks, model):
        self.chunks = chunks
        self.model = model
        self.vectors = model.embed_documents([c for c, _ in chunks])

    def rank(self, question):
        q = self.model.embed_query(question)
        scores = [sum(a * b for a, b in zip(q, v)) for v in self.vectors]
        return sorted(range(len(self.chunks)), key=lambda i: -scores[i])


def evaluate(make_retriever, chunk_size, ks):
    embedder.CHUNK_SIZE = chunk_size
    embedder.CHUNK_OVERLAP = chunk_size // 10
    retrievers = {
        name: make_retriever(embedder.split_into_chunks(PAGE_SEPARATOR.join(pages)))
        for name, pages in REPORTS.items()
    }
    hits = {k: 0 for k in ks}
    reciprocal_ranks = []
    for report, question, page, keyword in QUESTIONS:
        r = retrievers[report]
        order = r.rank(question)
        first = next(
            (rank for rank, i in enumerate(order, 1)
             if r.chunks[i][1]["page"] == page and keyword.lower() in r.chunks[i][0].lower()),
            None,
        )
        reciprocal_ranks.append(1 / first if first else 0.0)
        for k in ks:
            hits[k] += bool(first and first <= k)
    n = len(QUESTIONS)
    return {k: hits[k] / n for k in ks}, sum(reciprocal_ranks) / n


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--retriever", choices=["minilm", "keyword"], default="minilm")
    parser.add_argument("--chunk-sizes", default="300,500,800")
    parser.add_argument("--ks", default="1,2,4")
    args = parser.parse_args()
    ks = [int(k) for k in args.ks.split(",")]

    if args.retriever == "keyword":
        make = KeywordRetriever
    else:
        model = embedder.get_embeddings()
        make = lambda chunks: EmbeddingRetriever(chunks, model)  # noqa: E731

    print(f"retriever={args.retriever}  questions={len(QUESTIONS)}  reports={len(REPORTS)}")
    print("chunk_size | " + " | ".join(f"hit@{k}" for k in ks) + " | MRR")
    for size in [int(s) for s in args.chunk_sizes.split(",")]:
        hit, mrr = evaluate(make, size, ks)
        print(f"{size:>10} | " + " | ".join(f"{hit[k]:.2f}" for k in ks) + f" | {mrr:.2f}")


if __name__ == "__main__":
    main()
