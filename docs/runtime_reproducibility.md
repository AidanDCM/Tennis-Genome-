# Runtime reproducibility

The supported frozen calculator and prospective-evidence runtime is CPython **3.11.16** with the exact package versions in `requirements/runtime.lock`. Normal CI is intended to install that runtime through `requirements/ci.lock`, then install the project itself with `--no-deps`.

This pin does not change any frozen scientific coefficient or model artifact. It makes computational verification and future prospective records attributable to a concrete interpreter/dependency environment rather than to a moving `>=` dependency resolution.

For production-style supervised calculation, use the pinned JSON/file-loading path. An in-memory object that claims the sealed production bundle fingerprint is not permitted to attach caller-supplied neighbor records; the neighbor-bank byte digests are verified only by the path loader. Synthetic non-production bundles remain available for unit and research tests.
