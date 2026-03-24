# Financial Data Pipeline

Automatic financial data fetching, cleaning, and storage system using C++ that integrates with FRED API and Yahoo Finance.

## Features

- **FRED API Integration**: Fetch economic indicators (unemployment, inflation, interest rates, etc.)
- **Yahoo Finance Integration**: Fetch stock price data for multiple symbols
- **Data Cleaning**:
  - Automatic handling of market holidays and weekends
  - Forward-fill for missing business days
  - Outlier detection and removal using IQR method
- **SQLite Database Storage**: Persistent data storage with automatic table creation
- **Modular Architecture**: Easily extensible for additional data sources

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
wget https://github.com/nlohmann/json/releases/download/v3.11.2/json.hpp -O include/nlohmann/json.hpp
```

## Getting Started

### 1. Obtain API Keys

**FRED API Key:**
- Visit https://fredaccount.stlouisfed.org/login
- Create a free account and generate an API key
- Full documentation: https://fred.stlouisfed.org/docs/api/

### 2. Configure the Pipeline

Edit `config.json`:
```json
{
  "fredApi": {
    "apiKey": "YOUR_ACTUAL_API_KEY_HERE",
    "series": ["UNRATE", "CPIAUCSL", "DGS10", "FEDFUNDS"]
  },
  "yahooFinance": {
    "symbols": ["AAPL", "MSFT", "GOOGL"]
  }
}
```

Alternatively, update the hardcoded values in `main()` of `pipeline.cpp`:
```cpp
std::string fredApiKey = "YOUR_FRED_API_KEY";
std::vector<std::string> symbols = {"AAPL", "MSFT", "GOOGL"};
```

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
g++ -std=c++17 -o financial_pipeline pipeline.cpp \
    -lcurl -lsqlite3 -I./include
```

### 4. Run the Pipeline

```bash
./financial_pipeline
```

**Expected Output:**
```
=== Financial Data Pipeline ===

--- Fetching FRED Data ---
Retrieved 60 FRED observations
Successfully stored FRED data for UNRATE

--- Fetching Yahoo Finance Data ---
Processing AAPL...
  Retrieved 252 raw price points
  After outlier removal: 251 points
  After filling missing days: 252 points
  Successfully stored data for AAPL

--- Verifying Stored Data ---
Sample AAPL data (first 3 records):
  2024-01-02: Close=$165.23
  2024-01-03: Close=$166.45
  2024-01-04: Close=$164.87

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

### 2. Outlier Detection
- Uses Interquartile Range (IQR) method
- Configurable multiplier (default: 1.5)
- Removes extreme price movements
- Filters outliers per field (e.g., close price)

### 3. Market Holiday Recognition
Current recognized holidays (2024-2025):
- New Year's Day, MLK Day, Presidents' Day
- Good Friday, Memorial Day, Juneteenth
- Independence Day, Labor Day
- Thanksgiving, Christmas

To add more holidays, modify the `marketHolidays` set in the `DataCleaner` class.

## Architecture

### Core Classes

**FREDClient**
- Handles API communication with Federal Reserve Economic Data
- Parses JSON responses
- Manages authentication with API key

**YahooFinanceClient**
- Downloads stock price data via HTTP
- Parses CSV responses
- Handles date range conversions

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

Edit `main()`:
```cpp
std::vector<std::string> symbols = {
    "AAPL", "MSFT", "GOOGL", "AMZN", "TSLA",
    "META", "NVIDIA", "JPM"
};
```

### Fetch Additional Economic Indicators

Edit `main()`:
```cpp
std::vector<std::string> fredSeries = {
    "UNRATE",      // Unemployment Rate
    "CPIAUCSL",    // Consumer Price Index
    "DGS10",       // 10-Year Treasury Rate
    "FEDFUNDS",    // Federal Funds Rate
    "INDPRO"       // Industrial Production
};

for (const auto& seriesId : fredSeries) {
    // Fetch and process each series
}
```

### Adjust Outlier Detection

In `DataCleaner::RemoveOutliers()`:
```cpp
// Stricter (remove more outliers)
json cleaned = cleaner.RemoveOutliers(data, "close", 1.0);

// More lenient (keep more data)
json cleaned = cleaner.RemoveOutliers(data, "close", 2.0);
```

### Query Database

```bash
sqlite3 financial_data.db
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
    -O include/nlohmann/json.hpp
```

### Runtime Errors

**"FRED API Error" or empty data**
- Verify your API key is correct
- Check internet connection
- Confirm FRED service is up: https://fredaccount.stlouisfed.org

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

- [ ] Configuration file support (JSON/YAML parsing)
- [ ] Scheduling module for automated execution
- [ ] Data export to CSV/Excel
- [ ] REST API interface
- [ ] Performance metrics calculation
- [ ] Multi-threading for parallel API requests
- [ ] Pandas DataFrame export capability
- [ ] Additional data sources (IEX Cloud, Alpha Vantage)
- [ ] Data validation and sanity checks
- [ ] Logging to file

## API Rate Limiting

**FRED API:**
- Rate limit: 120 requests per minute
- No API key: 10 requests per minute

**Yahoo Finance:**
- No official rate limits
- Recommended: 1-2 second delay between requests

## License

MIT License - Feel free to use and modify for your needs.

## Support

For issues with:
- **FRED API**: https://fred.stlouisfed.org/docs/api
- **libcurl**: https://curl.se/
- **SQLite**: https://www.sqlite.org/docs.html
- **nlohmann/json**: https://github.com/nlohmann/json

## Contributing

To improve this pipeline:
1. Add more data sources
2. Implement configuration file parsing
3. Add comprehensive logging
4. Implement scheduling
5. Create unit tests
6. Optimize database queries
