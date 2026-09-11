from __future__ import annotations

from tennis_genome.experiments import market_book_qa as _base

# Amendment 004 changes only the corrected batch artifact version. The identity
# resolver remains v2 and every preregistered denominator/coverage gate remains
# unchanged.
_base._BATCH_VERSION = "market-book-001-batch-v3"
_base._RESOLVER_VERSION = "bookmaker-canonical-join-v2"


def main() -> None:
    _base.main()


if __name__ == "__main__":
    main()
