from __future__ import annotations

from tennis_genome.experiments import market_book_qa as _base

# Amendment 003 changes only the artifact/resolver version. All QA denominator,
# coverage thresholds, source priority checks, and artifact hashing remain in the
# already-preregistered MARKET-BOOK-QA-001 implementation.
_base._BATCH_VERSION = "market-book-001-batch-v2"
_base._RESOLVER_VERSION = "bookmaker-canonical-join-v2"


def main() -> None:
    _base.main()


if __name__ == "__main__":
    main()
