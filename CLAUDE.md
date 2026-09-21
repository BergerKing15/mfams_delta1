# CLAUDE.md

Guidance for Claude Code working in this repository.

## What this is

MFAMS Delta1: a two-part financial backtesting project.

1. **C++ ingestion pipeline** (`pipeline.cpp`) — fetches FRED economic series and Alpha
   Vantage stock prices, cleans them (weekend/holiday-aware forward fill, IQR outlier
   removal), and writes them to the SQLite file `financial_data.db`.
2. **Python/Streamlit dashboard** (`dashboard.py` + `strategies.py`) — reads that same
   SQLite file and backtests trading strategies over it.

The SQLite file is the only interface between the two halves. There is no shared code.

## Build and run

C++ pipeline (CMake is the primary path; the `Makefile` is an equivalent alternative):

```bash
mkdir -p build && cd build && cmake .. && make   # -> build/financial_pipeline
./build/financial_pipeline                        # reads ./config.json, writes ./financial_data.db
make config                                       # builds build/config_manager (separate utility)
./build.sh --full                                 # deps + nlohmann/json + build (Linux/macOS only)
```

Requires libcurl, sqlite3, and `include/nlohmann/json.hpp` (vendored, already present).
C++17. `financial_pipeline` must run from a directory containing `config.json`, since the
config path is hardcoded relative.

Dashboard:

```bash
pip install -r requirements.txt
streamlit run dashboard.py       # http://localhost:8501
```

The dashboard calls `st.stop()` if `financial_data.db` is missing, so run the pipeline (or
use the dashboard's own "Add Custom Stock or FRED Data" panel) first.

There is no test suite. `test_alphavantage.cpp` is a standalone manual probe of the Alpha
Vantage API, not a unit test, and is not wired into CMake or the Makefile.

## Database conventions

Tables are created dynamically, one per instrument, and code discovers them by prefix:

- `fred_<SERIES_ID>` — `date TEXT UNIQUE`, `value REAL`
- `stock_<SYMBOL>` — `date TEXT UNIQUE`, `open/high/low/close/adj_close REAL`, `volume`,
  `filled BOOLEAN` (1 = forward-filled, not a real trading day)

`dashboard.py` lists what is available by querying `sqlite_master` for those prefixes, so
adding a symbol or series anywhere makes it appear in the UI with no code change. Inserts
use `INSERT OR REPLACE` on the unique `date`, so re-running the pipeline is idempotent.

## Adding a strategy

Strategies live in `strategies.py`, subclass `Strategy`, and are registered in the
`STRATEGIES` dict at the bottom of the file — add the entry or the dashboard won't see it.
`calculate_signals()` takes `stock_df`/`fred_df` plus `self.params`, sets a `signal` column
(1/-1/0), and must finish by returning `self.apply_returns(merged)` — that helper lags the
position one day, books transaction costs from `transaction_cost_bps`, and fills in
`returns`, `gross_returns`, `transaction_costs` and `strategy_returns`. Don't compute
`strategy_returns` by hand; costs would silently go missing. Return `None` when there isn't
enough data (the dashboard turns `None` into a user-facing "adjust parameters" message
rather than a crash).

`Strategy.calculate_metrics()` derives Sharpe, drawdown and per-trade statistics.
`win_rate` is per *trade* (an unbroken stretch of exposure, via `extract_trades()`);
`win_rate_days` is the day-level figure. Don't conflate them.

Two things to keep in mind:

- Read every parameter with `self.params.get(name, default)`. The dashboard's sidebar
  renders a different control set per strategy, so a parameter may simply be absent.
- Data is thin (Alpha Vantage returns ~100 days on the free tier), so long lookbacks
  silently produce empty backtests. Existing defaults are deliberately short for this
  reason — MA Crossover uses 20/50, not the textbook 50/200.
- Downstream chart code in `dashboard.py` guards on column presence (`if 'ma' in df`), so
  optional indicator columns are fine to add.

Users can also upload a `.py` strategy file through the dashboard, which execs it and picks
up any `Strategy` subclass; `example_custom_strategy.py` is the template.

## Repository quirks

- **`config.json` holds live FRED and Alpha Vantage API keys.** It is gitignored;
  `config.example.json` is the committed placeholder template. Never put real keys in the
  example, and don't echo keys into logs, docs, or commit messages. Note that the keys are
  still present in git history from before the file was untracked.
- `data_utils.hpp` is dead code — nothing includes it.
- The two cleaning stages are independent by design: `RepairOutliers` fixes *values*
  (in place, marking the bar `filled`), `FillMissingDays` fixes *calendar gaps*. They used
  to interact — deleting a bar left a hole the filler papered over with the previous day's
  price, turning a suspect bar into a flat zero-return one. Don't reintroduce deletion.
- Outliers are judged on returns, never price levels, and only the spike-and-revert shape
  is treated as an error. `make test` covers both headers.
- `config.json`'s `outputSize` field is ignored: `outputsize=full` is premium-only on Alpha
  Vantage, so `pipeline.cpp` always gets the ~100-day compact response.
- The pipeline sleeps 12 seconds between symbols for Alpha Vantage's 5 req/min free tier, so
  a multi-symbol run is slow by design.
- Market holidays are computed in `market_calendar.hpp`, not listed. `make test` checks them
  against published NYSE dates including the observance edge cases. Don't reintroduce a
  hardcoded list — the previous one expired at 2025 and fabricated bars on 2026 holidays.
- Any signal a strategy computes must be causal. The FRED Z-score uses an expanding window
  for this reason; a full-sample `scipy.stats.zscore` leaks future data into past signals.
  Note that FRED series are also published with a lag that the merge does not yet model.
