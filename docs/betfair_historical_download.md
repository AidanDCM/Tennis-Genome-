# Betfair Historical Data API download runbook

Status: **procurement/download tooling only; no market result implied**

This runbook downloads Betfair Historical Data that has already been purchased and made available in the account's **My Data** area. The repository does not automate purchases and does not store Betfair credentials.

Official Betfair documentation states that the Historical Data API uses the `ssoid` header, supports `GetMyData`, `GetCollectionsOptions`, `GetAdvBasketSize`, `DownloadListOfFiles` and `DownloadFile`, and recommends automated API downloads for large purchased datasets.

## Security boundary

Never put the Betfair username, password or session token in:

- Git;
- a command-line argument;
- a committed config file;
- a notebook;
- a MARKET-HIST artifact.

The downloader reads a valid Betfair session token only from the local environment variable:

```bash
export BETFAIR_SSOID='<valid Betfair session token>'
```

Obtain that session token locally through Betfair's supported API-login/session process. Do not paste it into repository issues, pull requests or experiment artifacts.

The downloader object redacts the token from its representation. HTTP errors do not print request headers.

## 1. Confirm what has actually been purchased

The API only downloads historical files that were purchased first and appear in **My Data**.

```bash
python -m tennis_genome.market.betfair_historical_download purchases
```

Use the exact `plan` string returned by Betfair for the month/package you intend to download. Do not guess a plan label in a production run.

## 2. Dry-run the chosen interval

Use a local ignored directory such as `data/raw/betfair-historical/`.

```bash
python -m tennis_genome.market.betfair_historical_download download \
  --plan 'Advanced Plan' \
  --start-date 2020-01-01 \
  --end-date 2025-12-31 \
  --output-root data/raw/betfair-historical \
  --dry-run
```

The command is intentionally restricted to:

- sport = `Tennis`;
- market type = `MATCH_ODDS`;
- file type = `M` (individual market files).

It splits requests into calendar-month windows before calling `DownloadListOfFiles`, following Betfair's recommendation to avoid one very large download request. Duplicate remote file paths are deduplicated deterministically.

Optional repeated `--country XX` arguments may be used only when a purchased bundle intentionally has a country restriction. The default is no country filter.

## 3. Download the purchased files

Remove `--dry-run` after checking the requested interval and plan:

```bash
python -m tennis_genome.market.betfair_historical_download download \
  --plan 'Advanced Plan' \
  --start-date 2020-01-01 \
  --end-date 2025-12-31 \
  --output-root data/raw/betfair-historical
```

The example dates are illustrative. Prefer the minimum ADVANCED interval recommended by BASIC-PREFLIGHT-001 rather than automatically buying/downloading 2020–2025.

## Resume and integrity behavior

Each remote market file is written to a `.part` file first and atomically moved into place only after the download finishes.

The local output root contains `download-state.json`, which records for every completed remote file:

- Betfair remote path;
- deterministic local relative path;
- byte size;
- SHA-256.

On a rerun:

- a tracked file whose current byte size and SHA-256 still match is skipped;
- a tracked file whose bytes changed causes the run to fail;
- an existing untracked file at an intended destination causes the run to fail rather than being overwritten;
- a stale `.part` file may be removed and downloaded again;
- a missing tracked file is downloaded again.

The remote path is accepted only when it stays below `/data/xds/historic/` and ends in `.bz2`. Path traversal or unexpected source paths fail closed.

## 4. Feed the downloaded directory into the existing pipeline

Do not commit the downloaded files.

For BASIC history, use the existing BASIC-PREFLIGHT-001 path to estimate the minimum useful ADVANCED purchase interval.

For ADVANCED/PRO history:

1. create the frozen historical source manifest;
2. run MARKET-HIST-001 reconstruction;
3. run MARKET-HIST-QA-001;
4. run POWER-MDE-001 without winner outcomes;
5. create the MARKET-VALIDATION-RUN-001 Stage A outcome-unlock seal;
6. only then supply canonical settled outcomes to Stage B.

See:

- `docs/betfair_historical_ingestion.md`
- `docs/market_validation_run.md`

## Why there is no automatic purchase step

Purchasing data is an account/billing action and the exact useful interval should be determined from BASIC-PREFLIGHT/QA/power considerations first. The repository intentionally automates only retrieval of data the operator has already chosen and purchased.

## Official API assumptions used by this tool

As of the implementation date, Betfair's documented Historical Data API base is:

`https://historicdata.betfair.com/api/`

The downloader freezes that host and does not expose a CLI option to redirect the SSO token to another server.

The filter uses `DownloadListOfFiles` with Tennis, `MATCH_ODDS` and `M`; file bytes are then retrieved through `DownloadFile?filePath=...`.

If Betfair changes those API contracts, update this acquisition utility and its tests. Do not modify frozen research results merely because the provider's download API changes.
