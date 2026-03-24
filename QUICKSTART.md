# Quick Start Guide

Get your financial data pipeline up and running in 10 minutes!

## Step 1: Prerequisites Check (2 minutes)

Verify your system has the required tools:

```bash
# Check for C++ compiler
g++ --version  # or clang++ --version

# Check for CMake
cmake --version

# Check for curl
curl --version

# Check for SQLite
sqlite3 --version
```

If any are missing, run the setup script (Step 2) with dependencies flag.

## Step 2: Automatic Setup (5 minutes)

### Linux/macOS - Full Automated Setup

```bash
# Make build script executable
chmod +x build.sh

# Full setup (install deps, setup libraries, build)
./build.sh --full
```

This will:
- ✓ Install system dependencies (libcurl, sqlite3, cmake)
- ✓ Download nlohmann/json library
- ✓ Build the project
- ✓ Prompt you to configure settings

### Windows or Manual Build

```bash
# Install dependencies manually, then:
mkdir build
cd build
cmake ..
cmake --build .
cd ..
```

## Step 3: Get Your API Keys (1 minute)

### FRED API Key (Required for economic data)

1. Visit: https://fredaccount.stlouisfed.org
2. Create a free account
3. Go to Account Settings → API Keys
4. Copy your 32-character API key

Keep this key safe and secure!

## Step 4: Configure the Pipeline (2 minutes)

Edit `config.json`:

```bash
nano config.json  # or your editor of choice
```

**Minimal Configuration:**
```json
{
  "fredApi": {
    "apiKey": "YOUR_API_KEY_HERE",
    "series": ["UNRATE"]
  },
  "yahooFinance": {
    "symbols": ["AAPL"]
  },
  "database": {
    "path": "financial_data.db"
  },
  "dataProcessing": {
    "startDate": "2024-01-01",
    "endDate": "2024-12-31"
  }
}
```

**Recommended Configuration:**
```json
{
  "fredApi": {
    "apiKey": "YOUR_API_KEY_HERE",
    "series": [
      "UNRATE",      // Unemployment Rate
      "CPIAUCSL",    // Consumer Price Index
      "DGS10"        // 10-Year Treasury Rate
    ]
  },
  "yahooFinance": {
    "symbols": [
      "AAPL",
      "MSFT",
      "GOOGL",
      "AMZN"
    ]
  },
  "database": {
    "path": "financial_data.db"
  },
  "dataProcessing": {
    "startDate": "2023-01-01",
    "endDate": "2024-12-31",
    "fillMissingDays": true,
    "removeOutliers": true
  }
}
```

## Step 5: Run the Pipeline

```bash
./build/financial_pipeline
```

**Expected Output:**
```
=== Financial Data Pipeline ===

--- Fetching FRED Data ---
Retrieved 252 FRED observations
Successfully stored FRED data for UNRATE

--- Fetching Yahoo Finance Data ---
Processing AAPL...
  Retrieved 252 raw price points
  After outlier removal: 251 points
  After filling missing days: 252 points
  Successfully stored data for AAPL

--- Verifying Stored Data ---
Sample AAPL data (first 3 records):
  2023-01-03: Close=$150.93
  2023-01-04: Close=$151.48
  2023-01-05: Close=$152.29

=== Pipeline Complete ===
```

## Step 6: Query Your Data

### Using SQLite CLI

```bash
sqlite3 financial_data.db

# View AAPL stock data
sqlite> SELECT date, close FROM stock_AAPL 
        WHERE date >= '2024-06-01' 
        ORDER BY date DESC 
        LIMIT 10;

# View FRED unemployment data
sqlite> SELECT date, value FROM fred_UNRATE 
        ORDER BY date DESC 
        LIMIT 10;

# Get basic statistics
sqlite> SELECT 
  COUNT(*) as count,
  MIN(close) as min_price,
  MAX(close) as max_price,
  ROUND(AVG(close), 2) as avg_price
FROM stock_AAPL;
```

### Example Queries

**Get stocks above 30-day MA:**
```sql
SELECT a.date, a.close,
       ROUND(AVG(b.close) OVER (ORDER BY a.date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW), 2) as ma_30
FROM stock_AAPL a
JOIN stock_AAPL b ON a.date >= b.date
WHERE a.date >= '2024-09-01'
GROUP BY a.date
ORDER BY a.date DESC;
```

**Find largest daily changes:**
```sql
SELECT date, close, 
       ROUND(((close - LAG(close) OVER(ORDER BY date)) / LAG(close) OVER(ORDER BY date) * 100), 2) as pct_change
FROM stock_AAPL
WHERE pct_change IS NOT NULL
ORDER BY ABS(pct_change) DESC
LIMIT 10;
```

**FRED data trends:**
```sql
SELECT date, value FROM fred_UNRATE
WHERE date >= '2023-01-01'
ORDER BY date;
```

## Troubleshooting Quick Reference

### Build Fails with "curl.h: No such file"

**Linux:**
```bash
sudo apt-get install libcurl4-openssl-dev
```

**macOS:**
```bash
brew install curl
```

### Build Fails with "sqlite3.h: No such file"

**Linux:**
```bash
sudo apt-get install libsqlite3-dev
```

**macOS:**
```bash
brew install sqlite3
```

### Build Fails with "nlohmann/json.hpp: No such file"

```bash
./build.sh --setup-json
```

Or manually:
```bash
mkdir -p include/nlohmann
wget https://github.com/nlohmann/json/releases/download/v3.11.2/json.hpp \
    -O include/nlohmann/json.hpp
```

### "FRED API Error" after build succeeds

1. **Verify API Key**: Check that your key is correct in `config.json`
   ```bash
   grep apiKey config.json
   ```

2. **Check Connectivity**: Test internet connection
   ```bash
   curl -I https://api.stlouisfed.org
   ```

3. **API Key Format**: API key should be 32 characters
   ```bash
   grep apiKey config.json | grep -o '[a-z0-9]*' | tail -1 | wc -c
   # Should output: 33 (32 chars + newline)
   ```

### "Cannot open database" error

Make sure you have write permissions in the current directory:
```bash
ls -la | grep financial_data.db
chmod 644 financial_data.db  # if needed
```

Or specify a different path in `config.json`:
```json
"database": {
  "path": "/tmp/financial_data.db"
}
```

## Next Steps

### 1. **Schedule Automatic Runs**

**Unix/Linux (crontab):**
```bash
crontab -e

# Add one of these lines:
0 18 * * *  /home/user/delta1/build/financial_pipeline   # Daily at 6 PM
0 * * * *   /home/user/delta1/build/financial_pipeline   # Every hour
```

**Windows (Task Scheduler):**
1. Search for "Task Scheduler"
2. Create Basic Task
3. Set Trigger → Daily/Hourly
4. Set Action → Start Program → `C:\path\to\financial_pipeline.exe`

### 2. **Extend the Pipeline**

- **Add More Data Sources**: Modify APIs to include crypto, forex, commodities
- **Advanced Analytics**: Add technical indicators (RSI, MACD, Bollinger Bands)
- **Machine Learning**: Use data for prediction models
- **Reporting**: Generate daily/weekly reports
- **Export**: Add CSV, JSON, Excel export functionality

### 3. **Optimize Performance**

- Create database indices:
  ```sql
  CREATE INDEX idx_stock_date ON stock_AAPL(date);
  CREATE INDEX idx_fred_date ON fred_UNRATE(date);
  ```

- Archive old data to separate database
- Implement incremental updates (only fetch new data)
- Use connection pooling for concurrent API requests

## Additional Resources

- **FRED API Documentation**: https://fred.stlouisfed.org/docs/api
- **nlohmann/json GitHub**: https://github.com/nlohmann/json
- **libcurl Documentation**: https://curl.se/
- **SQLite Documentation**: https://www.sqlite.org/docs.html
- **CMake Documentation**: https://cmake.org/documentation/

## Tips & Tricks

### View Configuration
```bash
# Pretty-print config.json
jq . config.json

# Or with Python
python3 -m json.tool config.json
```

### Database Backup
```bash
# Backup daily
cp financial_data.db financial_data_$(date +%Y%m%d).db

# Backup with compression
tar czf financial_data_$(date +%Y%m%d).tar.gz financial_data.db
```

### Monitor Disk Usage
```bash
du -h financial_data.db
sqlite3 financial_data.db ".tables"
sqlite3 financial_data.db "SELECT name FROM sqlite_master WHERE type='table';"
```

### Check Data Freshness
```bash
sqlite3 financial_data.db \
  "SELECT MAX(date) as latest_date FROM stock_AAPL;"
```

## Getting Help

1. Check the comprehensive [README.md](README.md)
2. Review [config.json](config.json) examples
3. Check CMake build output for errors
4. Verify credential format and API connectivity
5. Create an issue on GitHub with:
   - Your OS and compiler version
   - Full error message
   - Steps to reproduce

Happy data fetching! 📊
