#include <iostream>
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <sqlite3.h>
#include <string>
#include <vector>
#include <map>
#include <algorithm>
#include <ctime>
#include <iomanip>
#include <sstream>
#include <set>

using json = nlohmann::json;

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

// Callback for CURL to write response to string
size_t WriteCallback(void* contents, size_t size, size_t nmemb, std::string* s) {
    s->append((char*)contents, size * nmemb);
    return size * nmemb;
}

// Convert date string (YYYY-MM-DD) to time_t
std::time_t DateStringToTime(const std::string& dateStr) {
    std::tm tm = {};
    std::istringstream ss(dateStr);
    ss >> std::get_time(&tm, "%Y-%m-%d");
    return std::mktime(&tm);
}

// Convert time_t to date string (YYYY-MM-DD)
std::string TimeToDateString(std::time_t t) {
    std::tm* tm = std::localtime(&t);
    std::ostringstream oss;
    oss << std::put_time(tm, "%Y-%m-%d");
    return oss.str();
}

// Check if date is a weekend
bool IsWeekend(const std::string& dateStr) {
    std::time_t t = DateStringToTime(dateStr);
    std::tm* tm = std::localtime(&t);
    int dayOfWeek = tm->tm_wday;  // 0=Sunday, 6=Saturday
    return dayOfWeek == 0 || dayOfWeek == 6;
}

// ============================================================================
// FRED API CLIENT
// ============================================================================

class FREDClient {
private:
    std::string apiKey;
    std::string baseURL = "https://api.stlouisfed.org/fred/series/data";

public:
    FREDClient(const std::string& key) : apiKey(key) {}

    // Fetch FRED data for a specific series
    json FetchSeriesData(const std::string& seriesId, const std::string& startDate, 
                         const std::string& endDate) {
        CURL* curl = curl_easy_init();
        std::string readBuffer;
        
        if (curl) {
            std::string url = baseURL + "?series_id=" + seriesId + 
                            "&api_key=" + apiKey +
                            "&from_date=" + startDate +
                            "&to_date=" + endDate +
                            "&file_type=json";

            curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
            curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);

            CURLcode res = curl_easy_perform(curl);
            
            if (res != CURLE_OK) {
                std::cerr << "FRED API Error: " << curl_easy_strerror(res) << std::endl;
                curl_easy_cleanup(curl);
                return json::object();
            }

            curl_easy_cleanup(curl);
            
            try {
                return json::parse(readBuffer);
            } catch (const std::exception& e) {
                std::cerr << "JSON Parse Error: " << e.what() << std::endl;
                return json::object();
            }
        }
        return json::object();
    }
};

// ============================================================================
// YAHOO FINANCE API CLIENT
// ============================================================================

class YahooFinanceClient {
private:
    std::string baseURL = "https://query1.finance.yahoo.com/v7/finance/download/";

public:
    // Fetch Yahoo Finance data for a stock symbol
    json FetchStockData(const std::string& symbol, const std::string& startDate, 
                        const std::string& endDate) {
        CURL* curl = curl_easy_init();
        std::string readBuffer;
        json result = json::array();

        if (curl) {
            // Convert dates to Unix timestamps
            std::time_t startTime = DateStringToTime(startDate);
            std::time_t endTime = DateStringToTime(endDate);

            std::string url = baseURL + symbol + 
                            "?period1=" + std::to_string(startTime) +
                            "&period2=" + std::to_string(endTime) +
                            "&interval=1d&events=history&download=true";

            curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
            curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);

            CURLcode res = curl_easy_perform(curl);

            if (res != CURLE_OK) {
                std::cerr << "Yahoo Finance API Error: " << curl_easy_strerror(res) << std::endl;
                curl_easy_cleanup(curl);
                return result;
            }

            curl_easy_cleanup(curl);

            // Parse CSV response
            result = ParseCSVResponse(readBuffer);
        }

        return result;
    }

private:
    json ParseCSVResponse(const std::string& csv) {
        json result = json::array();
        std::istringstream stream(csv);
        std::string line;
        bool isHeader = true;

        while (std::getline(stream, line)) {
            if (isHeader) {
                isHeader = false;
                continue;  // Skip header row
            }

            if (line.empty()) continue;

            // Parse CSV line (Date,Open,High,Low,Close,Adj Close,Volume)
            std::istringstream lineStream(line);
            std::vector<std::string> fields;
            std::string field;

            while (std::getline(lineStream, field, ',')) {
                fields.push_back(field);
            }

            if (fields.size() >= 7) {
                json dataPoint = {
                    {"date", fields[0]},
                    {"open", std::stod(fields[1])},
                    {"high", std::stod(fields[2])},
                    {"low", std::stod(fields[3])},
                    {"close", std::stod(fields[4])},
                    {"adjClose", std::stod(fields[5])},
                    {"volume", std::stoll(fields[6])}
                };
                result.push_back(dataPoint);
            }
        }

        return result;
    }
};

// ============================================================================
// DATA CLEANER
// ============================================================================

class DataCleaner {
private:
    std::set<std::string> marketHolidays = {
        // US Market holidays (add more as needed)
        "2024-01-01", "2024-01-15", "2024-02-19", "2024-03-29", 
        "2024-05-27", "2024-06-19", "2024-07-04", "2024-09-02",
        "2024-11-28", "2024-12-25",
        "2025-01-01", "2025-01-20", "2025-02-17", "2025-04-18",
        "2025-05-26", "2025-06-19", "2025-07-04", "2025-09-01",
        "2025-11-27", "2025-12-25"
    };

public:
    // Check if date is a market holiday
    bool IsMarketHoliday(const std::string& dateStr) {
        return marketHolidays.count(dateStr) > 0;
    }

    // Fill missing days with forward fill (last known value)
    json FillMissingDays(const json& data, const std::string& startDate, 
                         const std::string& endDate) {
        json filled = json::array();
        std::set<std::string> existingDates;

        // Collect all existing dates
        for (const auto& point : data) {
            if (point.contains("date")) {
                existingDates.insert(point["date"].get<std::string>());
            }
        }

        // Generate all business days in range
        std::time_t currentTime = DateStringToTime(startDate);
        std::time_t endTimeVal = DateStringToTime(endDate);
        const int SECONDS_PER_DAY = 86400;
        json lastValue = json::object();

        while (currentTime <= endTimeVal) {
            std::string dateStr = TimeToDateString(currentTime);

            // Check if it's a weekend or holiday - skip
            if (IsWeekend(dateStr) || IsMarketHoliday(dateStr)) {
                currentTime += SECONDS_PER_DAY;
                continue;
            }

            // If date exists in data, use it; otherwise forward fill
            bool found = false;
            for (const auto& point : data) {
                if (point.contains("date") && 
                    point["date"].get<std::string>() == dateStr) {
                    lastValue = point;
                    found = true;
                    break;
                }
            }

            if (!found && !lastValue.is_null() && !lastValue.empty()) {
                // Forward fill with updated date
                json filled_point = lastValue;
                filled_point["date"] = dateStr;
                filled_point["filled"] = true;
                filled.push_back(filled_point);
            } else if (found) {
                filled.push_back(lastValue);
            }

            currentTime += SECONDS_PER_DAY;
        }

        return filled;
    }

    // Remove outliers using IQR method
    json RemoveOutliers(const json& data, const std::string& field, double iqrMultiplier = 1.5) {
        if (data.empty() || !data[0].contains(field)) {
            return data;
        }

        // Extract values
        std::vector<double> values;
        for (const auto& point : data) {
            if (point.contains(field) && point[field].is_number()) {
                values.push_back(point[field].get<double>());
            }
        }

        if (values.size() < 4) return data;  // Need at least 4 values for IQR

        std::sort(values.begin(), values.end());

        size_t q1_idx = values.size() / 4;
        size_t q3_idx = 3 * values.size() / 4;
        double q1 = values[q1_idx];
        double q3 = values[q3_idx];
        double iqr = q3 - q1;

        double lowerBound = q1 - iqrMultiplier * iqr;
        double upperBound = q3 + iqrMultiplier * iqr;

        // Filter outliers
        json filtered = json::array();
        for (const auto& point : data) {
            if (point.contains(field) && point[field].is_number()) {
                double val = point[field].get<double>();
                if (val >= lowerBound && val <= upperBound) {
                    filtered.push_back(point);
                }
            } else {
                filtered.push_back(point);
            }
        }

        return filtered;
    }
};

// ============================================================================
// SQLITE DATABASE MANAGER
// ============================================================================

class DatabaseManager {
private:
    sqlite3* db = nullptr;

public:
    DatabaseManager(const std::string& dbPath) {
        int rc = sqlite3_open(dbPath.c_str(), &db);
        if (rc != SQLITE_OK) {
            std::cerr << "Cannot open database: " << sqlite3_errmsg(db) << std::endl;
            db = nullptr;
        }
    }

    ~DatabaseManager() {
        if (db) {
            sqlite3_close(db);
        }
    }

    bool IsConnected() const { return db != nullptr; }

    // Create FRED data table
    bool CreateFREDTable(const std::string& seriesId) {
        if (!db) return false;

        std::string tableName = "fred_" + seriesId;
        std::string sql = R"(
            CREATE TABLE IF NOT EXISTS )" + tableName + R"( (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT UNIQUE NOT NULL,
                value REAL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
        )";

        char* errMsg = nullptr;
        int rc = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &errMsg);

        if (rc != SQLITE_OK) {
            std::cerr << "SQL Error: " << errMsg << std::endl;
            sqlite3_free(errMsg);
            return false;
        }

        return true;
    }

    // Create Yahoo Finance table
    bool CreateStockTable(const std::string& symbol) {
        if (!db) return false;

        std::string tableName = "stock_" + symbol;
        std::string sql = R"(
            CREATE TABLE IF NOT EXISTS )" + tableName + R"( (
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
        )";

        char* errMsg = nullptr;
        int rc = sqlite3_exec(db, sql.c_str(), nullptr, nullptr, &errMsg);

        if (rc != SQLITE_OK) {
            std::cerr << "SQL Error: " << errMsg << std::endl;
            sqlite3_free(errMsg);
            return false;
        }

        return true;
    }

    // Insert FRED data
    bool InsertFREDData(const std::string& seriesId, const json& data) {
        if (!db || data.empty()) return false;

        std::string tableName = "fred_" + seriesId;

        for (const auto& point : data) {
            if (!point.contains("date") || !point.contains("value")) continue;

            std::string date = point["date"].get<std::string>();
            double value = point["value"].is_null() ? 0.0 : point["value"].get<double>();

            std::string sql = "INSERT OR REPLACE INTO " + tableName + 
                            " (date, value) VALUES (?, ?);";

            sqlite3_stmt* stmt;
            if (sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
                std::cerr << "Prepare Error: " << sqlite3_errmsg(db) << std::endl;
                continue;
            }

            sqlite3_bind_text(stmt, 1, date.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_double(stmt, 2, value);

            if (sqlite3_step(stmt) != SQLITE_DONE) {
                std::cerr << "Insert Error: " << sqlite3_errmsg(db) << std::endl;
            }

            sqlite3_finalize(stmt);
        }

        return true;
    }

    // Insert stock data
    bool InsertStockData(const std::string& symbol, const json& data) {
        if (!db || data.empty()) return false;

        std::string tableName = "stock_" + symbol;

        for (const auto& point : data) {
            if (!point.contains("date")) continue;

            std::string date = point["date"].get<std::string>();
            double open = point.contains("open") ? point["open"].get<double>() : 0.0;
            double high = point.contains("high") ? point["high"].get<double>() : 0.0;
            double low = point.contains("low") ? point["low"].get<double>() : 0.0;
            double close = point.contains("close") ? point["close"].get<double>() : 0.0;
            double adjClose = point.contains("adjClose") ? point["adjClose"].get<double>() : 0.0;
            long volume = point.contains("volume") ? point["volume"].get<long>() : 0;
            bool filled = point.contains("filled") ? point["filled"].get<bool>() : false;

            std::string sql = "INSERT OR REPLACE INTO " + tableName + 
                            " (date, open, high, low, close, adj_close, volume, filled) "
                            "VALUES (?, ?, ?, ?, ?, ?, ?, ?);";

            sqlite3_stmt* stmt;
            if (sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
                std::cerr << "Prepare Error: " << sqlite3_errmsg(db) << std::endl;
                continue;
            }

            sqlite3_bind_text(stmt, 1, date.c_str(), -1, SQLITE_STATIC);
            sqlite3_bind_double(stmt, 2, open);
            sqlite3_bind_double(stmt, 3, high);
            sqlite3_bind_double(stmt, 4, low);
            sqlite3_bind_double(stmt, 5, close);
            sqlite3_bind_double(stmt, 6, adjClose);
            sqlite3_bind_int64(stmt, 7, volume);
            sqlite3_bind_int(stmt, 8, filled ? 1 : 0);

            if (sqlite3_step(stmt) != SQLITE_DONE) {
                std::cerr << "Insert Error: " << sqlite3_errmsg(db) << std::endl;
            }

            sqlite3_finalize(stmt);
        }

        return true;
    }

    // Retrieve data from database
    json RetrieveData(const std::string& tableName) {
        if (!db) return json::array();

        json result = json::array();
        sqlite3_stmt* stmt;

        std::string sql = "SELECT * FROM " + tableName + ";";

        if (sqlite3_prepare_v2(db, sql.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
            std::cerr << "Prepare Error: " << sqlite3_errmsg(db) << std::endl;
            return result;
        }

        while (sqlite3_step(stmt) == SQLITE_ROW) {
            json row = json::object();
            int columnCount = sqlite3_column_count(stmt);

            for (int i = 0; i < columnCount; i++) {
                const char* columnName = sqlite3_column_name(stmt, i);
                int type = sqlite3_column_type(stmt, i);

                if (type == SQLITE_TEXT) {
                    row[columnName] = reinterpret_cast<const char*>(sqlite3_column_text(stmt, i));
                } else if (type == SQLITE_FLOAT) {
                    row[columnName] = sqlite3_column_double(stmt, i);
                } else if (type == SQLITE_INTEGER) {
                    row[columnName] = sqlite3_column_int64(stmt, i);
                }
            }
            result.push_back(row);
        }

        sqlite3_finalize(stmt);
        return result;
    }
};

// ============================================================================
// MAIN PIPELINE
// ============================================================================

int main(int argc, char* argv[]) {
    std::cout << "=== Financial Data Pipeline ===" << std::endl;

    // Configuration
    std::string fredApiKey = "YOUR_FRED_API_KEY";  // Replace with your API key
    std::string dbPath = "financial_data.db";
    std::string startDate = "2024-01-01";
    std::string endDate = "2024-12-31";

    // Initialize components
    FREDClient fredClient(fredApiKey);
    YahooFinanceClient yahooClient;
    DataCleaner cleaner;
    DatabaseManager dbManager(dbPath);

    if (!dbManager.IsConnected()) {
        std::cerr << "Failed to connect to database" << std::endl;
        return 1;
    }

    // ========== FRED Data Pipeline ==========
    std::cout << "\n--- Fetching FRED Data ---" << std::endl;
    std::string fredSeriesId = "UNRATE";  // Unemployment Rate
    
    if (dbManager.CreateFREDTable(fredSeriesId)) {
        json fredData = fredClient.FetchSeriesData(fredSeriesId, startDate, endDate);

        if (!fredData.empty() && fredData.contains("observations")) {
            std::cout << "Retrieved " << fredData["observations"].size() << " FRED observations" << std::endl;
            
            // Insert data
            if (dbManager.InsertFREDData(fredSeriesId, fredData["observations"])) {
                std::cout << "Successfully stored FRED data for " << fredSeriesId << std::endl;
            }
        } else {
            std::cout << "No FRED data returned (API key may be invalid)" << std::endl;
        }
    }

    // ========== Yahoo Finance Data Pipeline ==========
    std::cout << "\n--- Fetching Yahoo Finance Data ---" << std::endl;
    std::vector<std::string> symbols = {"AAPL", "MSFT", "GOOGL"};  // Add symbols as needed

    for (const auto& symbol : symbols) {
        std::cout << "Processing " << symbol << "..." << std::endl;

        if (dbManager.CreateStockTable(symbol)) {
            // Fetch raw data
            json rawData = yahooClient.FetchStockData(symbol, startDate, endDate);
            
            if (!rawData.empty()) {
                std::cout << "  Retrieved " << rawData.size() << " raw price points" << std::endl;

                // Clean data: remove outliers
                json cleanedData = cleaner.RemoveOutliers(rawData, "close");
                std::cout << "  After outlier removal: " << cleanedData.size() << " points" << std::endl;

                // Fill missing business days
                json filledData = cleaner.FillMissingDays(cleanedData, startDate, endDate);
                std::cout << "  After filling missing days: " << filledData.size() << " points" << std::endl;

                // Store in database
                if (dbManager.InsertStockData(symbol, filledData)) {
                    std::cout << "  Successfully stored data for " << symbol << std::endl;
                }
            } else {
                std::cout << "  No data returned for " << symbol << std::endl;
            }
        }
    }

    // ========== Verify Stored Data ==========
    std::cout << "\n--- Verifying Stored Data ---" << std::endl;
    json stockData = dbManager.RetrieveData("stock_AAPL");
    if (!stockData.empty()) {
        std::cout << "Sample AAPL data (first 3 records):" << std::endl;
        for (size_t i = 0; i < std::min(size_t(3), stockData.size()); i++) {
            std::cout << "  " << stockData[i]["date"] << ": Close=$" 
                      << stockData[i]["close"] << std::endl;
        }
    }

    std::cout << "\n=== Pipeline Complete ===" << std::endl;
    return 0;
}
