from __future__ import annotations

from tennis_genome.market import bookmaker_batch_v2 as _v2

# Amendment 004 changes sanitized-row provenance and therefore the batch artifact
# version only. Identity resolution remains the preregistered v2 resolver.
_v2._BATCH_VERSION = "market-book-001-batch-v3"

build_market_book_records = _v2.build_market_book_records
main = _v2.main


if __name__ == "__main__":
    main()
