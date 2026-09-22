# Financial Data Pipeline

Automatic financial data fetching, cleaning, and storage system using C++ that integrates with FRED API and Alpha Vantage.

## Features

- **FRED API Integration**: Fetch economic indicators (unemployment, inflation, interest rates, etc.)
- **Alpha Vantage Integration**: Fetch daily stock price data for multiple symbols
- **Data Cleaning**:
  - Automatic handling of market holidays and weekends
  - Forward-fill for missing business days
  - Outlier detection and removal using IQR method
- **SQLite Database Storage**: Persistent data storage with automatic table creation
- **Modular Architecture**: Easily extensible for additional data sources

## Repository Layout

```
src/                C++ pipeline sources
  include/          project headers (market calendar, outlier filter)
app/                Streamlit dashboard and strategy library
tests/              C++ unit tests  (make test)
tools/              standalone API probe, not part of the build
third_party/        vendored nlohmann/json
data/               SQLite database and logs (gitignored)
docs/               QUICKSTART, DASHBOARD, STRATEGIES, PROJECT, REQUIREMENTS
```

Run all commands from the repository root.

## Requirements

### System Dependencies

**Ubuntu/Debian:**
```bash
sudo apt-get install -y \
    build-essential \
    cmake \
    libcurl4-openssl-dev \
    libsqlite3-dev \
    git
```

**macOS:**
```bash
brew install cmake curl sqlite3
```

**Windows (MSVC):**
- Install Visual Studio 2019+ with C++ development tools
- Install CMake from https://cmake.org/download/

### C++ Libraries

The project requires:
- **libcurl**: HTTP client library (system package)
- **sqlite3**: Database library (system package)
- **nlohmann/json**: Header-only JSON library (included automatically via CMake or download)

To download nlohmann/json:
```bash
mkdir -p include
wget https://github.com/nlohmann/json/releases/download/v3.11.2/json.hpp -O third_party/nlohmann/json.hpp
```

## Getting Started

### 1. Obtain API Keys

**FRED API Key:**
- Visit https://fredaccount.stlouisfed.org/login
- Create a free account and generate an API key
- Full documentation: https://fred.stlouisfed.org/docs/api/

**Alpha Vantage API Key:**
- Visit https://www.alphavantage.co/support/#api-key
- Request a free key (no account required)
- Full documentation: https://www.alphavantage.co/documentation/

### 2. Configure the Pipeline

Copy the template and fill in your keys:
```bash
cp config.example.json config.json
```

```json
{
  "fredApi": {
    "apiKey": "YOUR_FRED_API_KEY",
    "series": ["UNRATE", "CPIAUCSL", "DGS10", "FEDFUNDS"]
  },
  "alphaVantage": {
    "apiKey": "YOUR_ALPHA_VANTAGE_API_KEY",
    "symbols": ["GDX", "NEM", "GOLD"]
  }
}
```

`config.json` is gitignored because it holds live API keys - keep your keys out of
`config.example.json`. Everything the pipeline needs comes from this file; nothing is
hardcoded in `src/pipeline.cpp`.

### 3. Build the Project

**Using CMake (Recommended):**
```bash
mkdir build
cd build
cmake ..
make
```

**Direct Compilation:**
```bash
g++ -std=c++17 -o financial_pipeline src/pipeline.cpp \
    -lcurl -lsqlite3 -I./include
```

### 4. Run the Pipeline

Run it from the project root - the config path is relative, so it looks for
`./config.json` in the working directory:

```bash
./build/financial_pipeline
```

**Expected Output:**
```
=== Financial Data Pipeline ===

--- Fetching FRED Data ---
Processing UNRATE...
  Retrieved 60 observations
  Successfully stored FRED data for UNRATE

--- Fetching Stock Data from Alpha Vantage ---
Processing GDX...
  Retrieved 100 raw price points
  After outlier removal: 98 points
  After filling missing days: 100 points
  Successfully stored data for GDX

--- Verifying Stored Data ---
FRED UNRATE: 60 records
Stock GDX: 100 records
Sample GDX data (first 3 records):
  2024-01-02: Close=$28.93
  2024-01-03: Close=$28.41
  2024-01-04: Close=$28.77

=== Pipeline Complete ===
```

## Database Schema

### FRED Data Table: `fred_<SERIES_ID>`
```sql
CREATE TABLE fred_UNRATE (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL,
    value REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### Stock Data Table: `stock_<SYMBOL>`
```sql
CREATE TABLE stock_AAPL (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT UNIQUE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    adj_close REAL,
    volume INTEGER,
    filled BOOLEAN DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

## Data Cleaning Features

### 1. Missing Day Handling
- Automatically detects gaps in trading days
- Skips weekends (Saturdays and Sundays)
- Recognizes US market holidays (customizable list)
- Uses forward-fill: carries previous trading day's values

### 2. Bad-Tick Repair
- Judged on **returns**, not price levels. An IQR filter over price levels treats
  the newest and oldest prices in a trending series as outliers, and a genuine
  crash as an error
- Flags the spike-and-revert signature of a bad print: the move into a bar and
  the move out of it are both extreme *and* point in opposite directions
- A real one-way move (a crash that stays down) is kept
- Flagged bars are **interpolated from their neighbours, not deleted**, and
  marked `filled`. The whole bar is scaled by one factor so OHLC stays coherent
- Configurable IQR multiplier (default: 1.5); see `src/include/outlier_filter.hpp`

### 3. Market Holiday Recognition
Holidays are **computed** from the NYSE rules in `src/include/market_calendar.hpp`, for any year, so
the calendar never goes stale:
- New Year's Day, MLK Day, Presidents' Day
- Good Friday (Easter-derived), Memorial Day, Juneteenth
- Independence Day, Labor Day
- Thanksgiving, Christmas

Observance rules are applied: a fixed-date holiday on a Saturday is observed the preceding
Friday and on a Sunday the following Monday, except New Year's Day, which is simply not
observed when it falls on a Saturday.

Ad-hoc closures (national days of mourning, weather) can't be derived from a rule and are
not covered. To verify the calendar:
```bash
make test
```

## Architecture

### Core Classes

**FREDClient**
- Handles API communication with Federal Reserve Economic Data
- Parses JSON responses
- Manages authentication with API key

**AlphaVantageClient**
- Downloads daily stock price data via HTTP
- Parses the `Time Series (Daily)` JSON response
- Surfaces API `Error Message` / `Note` / `Information` responses (rate limits, bad symbols)

**DataCleaner**
- Validates and transforms financial data
- Implements missing day filling
- Performs outlier detection
- Checks for weekends/holidays

**DatabaseManager**
- Creates and manages SQLite tables
- Handles data insertion and retrieval
- Supports dynamic table creation
- Prepared statements for SQL injection prevention

## Advanced Usage

### Extend with Additional Symbols

Edit `config.json` - no recompile needed:
```json
"alphaVantage": {
  "symbols": ["GDX", "NEM", "GOLD", "AEM", "AU", "KGC", "CPER"]
}
```

Note that the pipeline sleeps 12 seconds between symbols to stay under the free-tier rate
limit, so long symbol lists take a while.

### Fetch Additional Economic Indicators

Also `config.json`:
```json
"fredApi": {
  "series": ["UNRATE", "CPIAUCSL", "DGS10", "FEDFUNDS", "INDPRO"]
}
```

### Adjust Bad-Tick Sensitivity

In `DataCleaner::RepairOutliers()`:
```cpp
// Stricter (repair more aggressively)
json cleaned = cleaner.RepairOutliers(data, "close", 1.0);

// More lenient (leave more data untouched)
json cleaned = cleaner.RepairOutliers(data, "close", 2.0);
```

The filter is deliberately conservative: it would rather keep a bad tick than
delete a real move, since a deleted real move is unrecoverable and biases every
backtest that reads the data afterwards. Run `make test` to exercise it.

### Query Database

```bash
sqlite3 data/financial_data.db
sqlite> SELECT * FROM stock_AAPL WHERE date >= '2024-06-01' LIMIT 5;
sqlite> SELECT date, value FROM fred_UNRATE ORDER BY date DESC;
```

## Troubleshooting

### Build Errors

**"curl.h: No such file"**
```bash
# Ubuntu/Debian
sudo apt-get install libcurl4-openssl-dev

# macOS
brew install curl
```

**"sqlite3.h: No such file"**
```bash
# Ubuntu/Debian
sudo apt-get install libsqlite3-dev

# macOS
brew install sqlite3
```

**"nlohmann/json.hpp: No such file"**
```bash
mkdir -p include
wget https://github.com/nlohmann/json/releases/download/v3.11.2/json.hpp \
    -O third_party/nlohmann/json.hpp
```

### Runtime Errors

**"FRED API Error" or empty data**
- Verify your API key is correct
- Check internet connection
- Confirm FRED service is up: https://fredaccount.stlouisfed.org

**"API Rate Limit" or "API Information" for stock symbols**
- The Alpha Vantage free tier allows 5 requests/minute and caps daily requests
- Trim the `symbols` list in `config.json` and retry later

**"No time series data in response"**
- Usually an invalid ticker, or a rate-limit response in disguise
- Verify the symbol at https://www.alphavantage.co/documentation/

**"Cannot open database"**
- Ensure write permissions in current directory
- Check disk space availability
- Verify SQLite3 installation

**"Certificate verification failed"**
- Update CA certificates:
  ```bash
  # Ubuntu/Debian
  sudo apt-get install ca-certificates
  
  # macOS
  brew install curl-ca-bundle
  ```

## Performance Tips

1. **Batch Updates**: Process multiple symbols in sequence to avoid network saturation
2. **Date Ranges**: Use specific date ranges to reduce API load
3. **Caching**: Store frequently accessed data locally
4. **Indexing**: Add database indices for frequently queried columns:
   ```sql
   CREATE INDEX idx_stock_date ON stock_AAPL(date);
   CREATE INDEX idx_fred_date ON fred_UNRATE(date);
   ```

## Scheduling & Automation

To run automatically:

**Unix/Linux (cron):**
```bash
# Every day at 6 PM
0 18 * * * /path/to/financial_pipeline

# Every hour
0 * * * * /path/to/financial_pipeline
```

Add to crontab:
```bash
crontab -e
```

**Windows (Task Scheduler):**
1. Search for "Task Scheduler"
2. Create Basic Task
3. Set Trigger (Daily, Hourly, etc.)
4. Set Action: Start Program: `C:\path\to\financial_pipeline.exe`

## Future Enhancements

- [ ] Scheduling module for automated execution
- [ ] Data export to CSV/Excel
- [ ] REST API interface
- [ ] Performance metrics calculation
- [ ] Multi-threading for parallel API requests
- [ ] Pandas DataFrame export capability
- [ ] Additional data sources (IEX Cloud, Tiingo)
- [ ] Data validation and sanity checks
- [ ] Logging to file

## Validating a Strategy

A backtest tuned until it looks good is not evidence. `app/optimize.py` measures the
difference between a tuned result and an honest one.

```bash
python app/optimize.py --symbol GDX --strategy "MA Crossover"
```

It reports two numbers:

- **In-sample sweep**: the best Sharpe across the parameter grid, scored on the whole
  sample. This is what you get by hunting for the best setting and quoting it.
- **Walk-forward**: parameters chosen using only data up to a point in time, then scored
  on the period that follows, across several anchored folds. Nothing is chosen with
  knowledge of the window it is scored on.

The gap is the **overfitting premium**. On the bundled data it is large:

```
strategy                     best in-sample  mean OOS  premium
Z-Score (Macro Signal)                -0.69     -3.21     2.53
MA Crossover                           1.38     -2.62     4.00
RSI (Overbought/Oversold)              1.62      0.24     1.39
Mean Reversion                         0.19     -2.40     2.58
```

MA Crossover tuned to 10/30 shows a Sharpe of 1.38 on the full sample and -2.62 out of
sample. The tuned number is an artifact of the sample, and without this comparison it
would look like a working strategy.

The same sweep is available in the dashboard under **Validation**, along with a
cross-symbol check. Read that check carefully: the default universe is mostly gold
miners whose daily returns correlate about 0.77, so eight symbols carry roughly two
independent bets, not eight.

## Known Limitations

Things the data itself cannot support, worth knowing before trusting a backtest.

**No dividend adjustment.** `adj_close` is a copy of `close`. The free Alpha Vantage tier
returns no adjusted series, so total-return effects are missing entirely. For GDX, NEM and
the other dividend-paying names in the default config, backtests understate long returns and
overstate short ones. Don't build dividend-aware logic on this column.

**Short history.** The free tier returns roughly the last 100 trading days per symbol, about
five months. Sharpe ratios, win rates and drawdowns are all unstable on a sample that short,
and one trade can dominate the result. The dashboard warns when a series has under 250 days.
Use these numbers to compare parameter choices, not as evidence that a strategy works.

**Survivorship and point-in-time.** Prices come from a live API with no vintage history, so a
delisted ticker simply returns nothing and revised FRED figures silently overwrite the
originals. The FRED release lag models publication delay but not revisions.

**Risk-free rate defaults to 0.** Sharpe measures raw volatility-adjusted return unless you
set the sidebar's Risk-Free Rate. During any period when cash paid something, 0 flatters
every strategy - the dashboard suggests the latest FEDFUNDS value from your database.

## API Rate Limiting

**FRED API:**
- Rate limit: 120 requests per minute
- No API key: 10 requests per minute

**Alpha Vantage (free tier):**
- Rate limit: 5 requests per minute, plus a daily request cap
- The pipeline already sleeps 12 seconds between symbols to respect this
- `outputsize=full` is premium-only, so each symbol returns roughly the last 100 trading
  days - the `outputSize` field in `config.json` is not currently used

## License

MIT License - Feel free to use and modify for your needs.

## Support

For issues with:
- **FRED API**: https://fred.stlouisfed.org/docs/api
- **Alpha Vantage**: https://www.alphavantage.co/documentation/
- **libcurl**: https://curl.se/
- **SQLite**: https://www.sqlite.org/docs.html
- **nlohmann/json**: https://github.com/nlohmann/json

## Contributing

To improve this pipeline:
1. Add more data sources
2. Add comprehensive logging
4. Implement scheduling
5. Create unit tests
6. Optimize database queries
