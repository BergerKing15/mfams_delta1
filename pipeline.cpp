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
#include <thread>
#include <chrono>
#include <fstream>

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
    std::string baseURL = "https://api.stlouisfed.org/fred/series/observations";

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
            curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36");
            curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);

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
// ALPHA VANTAGE API CLIENT
// ============================================================================

class AlphaVantageClient {
private:
    std::string apiKey;
    std::string baseURL = "https://www.alphavantage.co/query";

public:
    AlphaVantageClient(const std::string& key) : apiKey(key) {}

    // Fetch Alpha Vantage stock data
    json FetchStockData(const std::string& symbol) {
        CURL* curl = curl_easy_init();
        std::string readBuffer;
        json result = json::array();

        if (curl) {
            // Use TIME_SERIES_DAILY (free tier) with compact output (last 100 days)
            // Note: outputsize=full is a premium feature, so we use default compact
            std::string url = baseURL + "?function=TIME_SERIES_DAILY" +
                            "&symbol=" + symbol +
                            "&apikey=" + apiKey;
                            // Note: removed &outputsize=full as it's premium-only on free tier

            curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
            curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);
            curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows NT 10.0; Win64; x64)");
            curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
            curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);

            CURLcode res = curl_easy_perform(curl);

            if (res != CURLE_OK) {
                std::cerr << "Alpha Vantage API Error for " << symbol << ": " 
                          << curl_easy_strerror(res) << std::endl;
                curl_easy_cleanup(curl);
                return result;
            }

            curl_easy_cleanup(curl);

            // Parse response
            result = ParseAlphaVantageResponse(readBuffer);
        }

        return result;
    }

private:
    json ParseAlphaVantageResponse(const std::string& response) {
        json result = json::array();

        try {
            json responseJson = json::parse(response);

            // Check for error messages
            if (responseJson.contains("Error Message")) {
                std::cerr << "API Error: " << responseJson["Error Message"].get<std::string>() << std::endl;
                return result;
            }

            if (responseJson.contains("Note")) {
                std::cerr << "API Rate Limit: " << responseJson["Note"].get<std::string>() << std::endl;
                return result;
            }

            if (responseJson.contains("Information")) {
                std::cerr << "API Information: " << responseJson["Information"].get<std::string>() << std::endl;
                return result;
            }

            // Extract time series data - looking for "Time Series (Daily)" key
            std::string timeSeriesKey = "Time Series (Daily)";
            if (!responseJson.contains(timeSeriesKey)) {
                std::cerr << "No time series data in response (key: " << timeSeriesKey << ")" << std::endl;
                return result;
            }

            auto timeSeries = responseJson[timeSeriesKey];

            // Iterate through each date and build result
            for (auto it = timeSeries.begin(); it != timeSeries.end(); ++it) {
                std::string date = it.key();
                auto dayData = it.value();

                try {
                    double open = std::stod(dayData["1. open"].get<std::string>());
                    double high = std::stod(dayData["2. high"].get<std::string>());
                    double low = std::stod(dayData["3. low"].get<std::string>());
                    double close = std::stod(dayData["4. close"].get<std::string>());
                    long volume = std::stoll(dayData["5. volume"].get<std::string>());

                    json dataPoint = {
                        {"date", date},
                        {"open", open},
                        {"high", high},
                        {"low", low},
                        {"close", close},
                        {"adjClose", close},  // Use close as adjClose for free tier
                        {"volume", volume}
                    };

                    result.push_back(dataPoint);
                } catch (const std::exception& e) {
                    std::cerr << "Error parsing day data for " << date << ": " << e.what() << std::endl;
                    continue;
                }
            }

            std::cout << "  Parsed " << result.size() << " days from Alpha Vantage" << std::endl;

        } catch (const std::exception& e) {
            std::cerr << "JSON Parse Error: " << e.what() << std::endl;
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
    // If data is empty, return as-is
    // If data has dates, use the date range from the data itself, not a fixed range
    json FillMissingDays(const json& data, const std::string& startDate = "", 
                         const std::string& endDate = "") {
        json filled = json::array();
        
        if (data.empty()) {
            return filled;
        }

        std::set<std::string> existingDates;
        std::string minDate = "9999-12-31";
        std::string maxDate = "0000-01-01";

        // Collect all existing dates and find the range in the data
        for (const auto& point : data) {
            if (point.contains("date")) {
                std::string date = point["date"].get<std::string>();
                existingDates.insert(date);
                if (date < minDate) minDate = date;
                if (date > maxDate) maxDate = date;
            }
        }

        // Use data's date range if fixed range is not provided
        std::string actualStartDate = startDate.empty() ? minDate : startDate;
        std::string actualEndDate = endDate.empty() ? maxDate : endDate;

        // Generate all business days in range
        std::time_t currentTime = DateStringToTime(actualStartDate);
        std::time_t endTimeVal = DateStringToTime(actualEndDate);
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
            
            // Handle value field: can be string, number, or null
            double value = 0.0;
            if (point["value"].is_null()) {
                continue;  // Skip null values
            } else if (point["value"].is_number()) {
                value = point["value"].get<double>();
            } else if (point["value"].is_string()) {
                try {
                    value = std::stod(point["value"].get<std::string>());
                } catch (...) {
                    continue;  // Skip if can't parse
                }
            }

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

json LoadConfiguration(const std::string& configPath) {
    std::ifstream configFile(configPath);
    if (!configFile.is_open()) {
        std::cerr << "Failed to open config file: " << configPath << std::endl;
        return json::object();
    }

    json config;
    try {
        configFile >> config;
        return config;
    } catch (const std::exception& e) {
        std::cerr << "Failed to parse config file: " << e.what() << std::endl;
        return json::object();
    }
}

int main() {
    std::cout << "=== Financial Data Pipeline ===" << std::endl;

    // Load configuration from config.json
    json config = LoadConfiguration("config.json");
    if (config.is_null() || config.empty()) {
        std::cerr << "Failed to load configuration" << std::endl;
        return 1;
    }

    // Extract configuration values
    std::string fredApiKey = config["fredApi"]["apiKey"].get<std::string>();
    std::string alphaVantageApiKey = config["alphaVantage"]["apiKey"].get<std::string>();
    std::string dbPath = config["database"]["path"].get<std::string>();
    
    std::vector<std::string> fredSeries;
    for (const auto& series : config["fredApi"]["series"]) {
        fredSeries.push_back(series.get<std::string>());
    }

    std::vector<std::string> stocks;
    for (const auto& symbol : config["alphaVantage"]["symbols"]) {
        stocks.push_back(symbol.get<std::string>());
    }

    std::string startDate = config["dataProcessing"]["startDate"].get<std::string>();
    std::string endDate = config["dataProcessing"]["endDate"].get<std::string>();

    // Initialize components
    FREDClient fredClient(fredApiKey);
    AlphaVantageClient alphaVantageClient(alphaVantageApiKey);
    DataCleaner cleaner;
    DatabaseManager dbManager(dbPath);

    if (!dbManager.IsConnected()) {
        std::cerr << "Failed to connect to database" << std::endl;
        return 1;
    }

    // ========== FRED Data Pipeline ==========
    std::cout << "\n--- Fetching FRED Data ---" << std::endl;
    for (const auto& seriesId : fredSeries) {
        std::cout << "Processing " << seriesId << "..." << std::endl;
        
        if (dbManager.CreateFREDTable(seriesId)) {
            json fredData = fredClient.FetchSeriesData(seriesId, "1900-01-01", "2099-12-31");

            if (!fredData.empty() && fredData.contains("observations")) {
                std::cout << "  Retrieved " << fredData["observations"].size() << " observations" << std::endl;
                
                // Insert data
                if (dbManager.InsertFREDData(seriesId, fredData["observations"])) {
                    std::cout << "  Successfully stored FRED data for " << seriesId << std::endl;
                }
            } else {
                std::cout << "  No FRED data returned for " << seriesId << std::endl;
            }
        }
    }

    // ========== Alpha Vantage Stock Data Pipeline ==========
    std::cout << "\n--- Fetching Stock Data from Alpha Vantage ---" << std::endl;

    for (const auto& symbol : stocks) {
        std::cout << "Processing " << symbol << "..." << std::endl;

        if (dbManager.CreateStockTable(symbol)) {
            // Fetch raw data from Alpha Vantage
            json rawData = alphaVantageClient.FetchStockData(symbol);
            
            if (!rawData.empty()) {
                std::cout << "  Retrieved " << rawData.size() << " raw price points" << std::endl;

                // Clean data: remove outliers
                json cleanedData = cleaner.RemoveOutliers(rawData, "close");
                std::cout << "  After outlier removal: " << cleanedData.size() << " points" << std::endl;

                // Fill missing business days
                // FillMissingDays will auto-detect date range if not provided
                json filledData = cleaner.FillMissingDays(cleanedData);
                std::cout << "  After filling missing days: " << filledData.size() << " points" << std::endl;

                // Store in database
                if (dbManager.InsertStockData(symbol, filledData)) {
                    std::cout << "  Successfully stored data for " << symbol << std::endl;
                }
            } else {
                std::cout << "  No data returned for " << symbol << " (check API key and rate limits)" << std::endl;
            }
        }
        
        // Add delay between requests to respect API rate limits (Alpha Vantage: 5 requests/min free tier)
        std::this_thread::sleep_for(std::chrono::seconds(12));
    }

    // ========== Verify Stored Data ==========
    std::cout << "\n--- Verifying Stored Data ---" << std::endl;
    
    // Check FRED data
    json fredCheck = dbManager.RetrieveData("fred_UNRATE");
    if (!fredCheck.empty()) {
        std::cout << "FRED UNRATE: " << fredCheck.size() << " records" << std::endl;
    }

    // Check stock data
    json stockData = dbManager.RetrieveData("stock_GDX");
    if (!stockData.empty()) {
        std::cout << "Stock GDX: " << stockData.size() << " records" << std::endl;
        std::cout << "Sample GDX data (first 3 records):" << std::endl;
        for (size_t i = 0; i < std::min(size_t(3), stockData.size()); i++) {
            std::cout << "  " << stockData[i]["date"] << ": Close=$" 
                      << stockData[i]["close"] << std::endl;
        }
    } else {
        std::cout << "No stock data available yet" << std::endl;
    }

    std::cout << "\n=== Pipeline Complete ===" << std::endl;
    return 0;
}
