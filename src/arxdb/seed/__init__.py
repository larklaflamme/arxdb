"""Seed corpus package (Phase 4).

`corpus.py` holds the phaser-thread corpus as declarative data (frozen
dataclasses), not imperative code. The only imperative part is the seed
script (`scripts/seed_phaser.py`), which ingests the corpus through the
public `verify_and_commit` pipeline.
"""

from .corpus import CORPUS_EDGES, CORPUS_NODES, CorpusEdge, CorpusNode

__all__ = ["CORPUS_NODES", "CORPUS_EDGES", "CorpusNode", "CorpusEdge"]
