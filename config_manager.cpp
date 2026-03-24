#include <iostream>
#include <nlohmann/json.hpp>
#include <fstream>
#include <string>
#include <vector>

using json = nlohmann::json;

/**
 * Configuration Manager - Loads and validates configuration from JSON
 * 
 * Usage:
 *   ConfigManager config("config.json");
 *   std::string fredKey = config.GetFREDApiKey();
 *   std::vector<std::string> symbols = config.GetYahooSymbols();
 */
class ConfigManager {
private:
    json configData;
    bool isLoaded = false;

public:
    ConfigManager(const std::string& filePath) {
        LoadConfig(filePath);
    }

    /**
     * Load configuration from JSON file
     */
    bool LoadConfig(const std::string& filePath) {
        try {
            std::ifstream file(filePath);
            if (!file.is_open()) {
                std::cerr << "Error: Cannot open config file: " << filePath << std::endl;
                return false;
            }

            file >> configData;
            file.close();
            
            if (!ValidateConfig()) {
                std::cerr << "Error: Configuration validation failed" << std::endl;
                return false;
            }

            isLoaded = true;
            std::cout << "Configuration loaded successfully from " << filePath << std::endl;
            return true;

        } catch (const json::exception& e) {
            std::cerr << "JSON Error: " << e.what() << std::endl;
            return false;
        } catch (const std::exception& e) {
            std::cerr << "Error loading config: " << e.what() << std::endl;
            return false;
        }
    }

    /**
     * Validate that required configuration fields exist
     */
    bool ValidateConfig() {
        bool valid = true;

        // Check FRED API configuration
        if (!configData.contains("fredApi")) {
            std::cerr << "Warning: Missing 'fredApi' section in config" << std::endl;
            valid = false;
        } else if (!configData["fredApi"].contains("apiKey")) {
            std::cerr << "Warning: Missing 'fredApi.apiKey' in config" << std::endl;
            valid = false;
        }

        // Check Yahoo Finance configuration
        if (!configData.contains("yahooFinance")) {
            std::cerr << "Warning: Missing 'yahooFinance' section in config" << std::endl;
            valid = false;
        } else if (!configData["yahooFinance"].contains("symbols")) {
            std::cerr << "Warning: Missing 'yahooFinance.symbols' in config" << std::endl;
            valid = false;
        }

        // Check database configuration
        if (!configData.contains("database")) {
            std::cerr << "Warning: Missing 'database' section in config" << std::endl;
            valid = false;
        }

        return valid;
    }

    // ========== FRED API Configuration ==========

    std::string GetFREDApiKey() const {
        return GetStringValue("fredApi.apiKey", "");
    }

    std::vector<std::string> GetFREDSeries() const {
        return GetArrayValue("fredApi.series");
    }

    std::string GetFREDBaseUrl() const {
        return GetStringValue("fredApi.baseUrl", "https://api.stlouisfed.org/fred");
    }

    // ========== Yahoo Finance Configuration ==========

    std::vector<std::string> GetYahooSymbols() const {
        return GetArrayValue("yahooFinance.symbols");
    }

    std::string GetYahooInterval() const {
        return GetStringValue("yahooFinance.interval", "1d");
    }

    // ========== Database Configuration ==========

    std::string GetDatabasePath() const {
        return GetStringValue("database.path", "financial_data.db");
    }

    std::string GetDatabaseType() const {
        return GetStringValue("database.type", "sqlite");
    }

    // ========== Data Processing Configuration ==========

    std::string GetStartDate() const {
        return GetStringValue("dataProcessing.startDate", "2024-01-01");
    }

    std::string GetEndDate() const {
        return GetStringValue("dataProcessing.endDate", "2024-12-31");
    }

    bool GetFillMissingDays() const {
        return GetBoolValue("dataProcessing.fillMissingDays", true);
    }

    bool GetRemoveOutliers() const {
        return GetBoolValue("dataProcessing.removeOutliers", true);
    }

    double GetOutlierIQRMultiplier() const {
        return GetDoubleValue("dataProcessing.outlierIQRMultiplier", 1.5);
    }

    // ========== Scheduling Configuration ==========

    bool GetSchedulingEnabled() const {
        return GetBoolValue("scheduling.enabled", false);
    }

    int GetSchedulingFrequencyMinutes() const {
        return GetIntValue("scheduling.frequencyMinutes", 60);
    }

    std::string GetSchedulingTimeZone() const {
        return GetStringValue("scheduling.timeZone", "UTC");
    }

    // ========== Utility Methods ==========

    /**
     * Print current configuration (without sensitive data)
     */
    void PrintConfiguration() const {
        std::cout << "\n=== Current Configuration ===" << std::endl;
        
        std::cout << "\nFRED API:" << std::endl;
        std::cout << "  - API Key: " << (GetFREDApiKey().empty() ? "NOT SET" : "***SET***") << std::endl;
        std::cout << "  - Series: ";
        auto series = GetFREDSeries();
        for (const auto& s : series) {
            std::cout << s << " ";
        }
        std::cout << std::endl;

        std::cout << "\nYahoo Finance:" << std::endl;
        std::cout << "  - Symbols: ";
        auto symbols = GetYahooSymbols();
        for (const auto& sym : symbols) {
            std::cout << sym << " ";
        }
        std::cout << std::endl;
        std::cout << "  - Interval: " << GetYahooInterval() << std::endl;

        std::cout << "\nDatabase:" << std::endl;
        std::cout << "  - Path: " << GetDatabasePath() << std::endl;
        std::cout << "  - Type: " << GetDatabaseType() << std::endl;

        std::cout << "\nData Processing:" << std::endl;
        std::cout << "  - Date Range: " << GetStartDate() << " to " << GetEndDate() << std::endl;
        std::cout << "  - Fill Missing Days: " << (GetFillMissingDays() ? "Yes" : "No") << std::endl;
        std::cout << "  - Remove Outliers: " << (GetRemoveOutliers() ? "Yes" : "No") << std::endl;
        std::cout << "  - Outlier IQR Multiplier: " << GetOutlierIQRMultiplier() << std::endl;

        std::cout << "\nScheduling:" << std::endl;
        std::cout << "  - Enabled: " << (GetSchedulingEnabled() ? "Yes" : "No") << std::endl;
        if (GetSchedulingEnabled()) {
            std::cout << "  - Frequency: Every " << GetSchedulingFrequencyMinutes() << " minutes" << std::endl;
            std::cout << "  - Time Zone: " << GetSchedulingTimeZone() << std::endl;
        }
        std::cout << std::endl;
    }

    bool IsLoaded() const { return isLoaded; }

private:
    // Helper methods to safely access JSON values with defaults

    std::string GetStringValue(const std::string& path, const std::string& defaultValue) const {
        try {
            auto it = configData;
            for (const auto& key : Split(path, '.')) {
                if (it.contains(key)) {
                    it = it[key];
                } else {
                    return defaultValue;
                }
            }
            return it.is_string() ? it.get<std::string>() : defaultValue;
        } catch (...) {
            return defaultValue;
        }
    }

    bool GetBoolValue(const std::string& path, bool defaultValue) const {
        try {
            auto it = configData;
            for (const auto& key : Split(path, '.')) {
                if (it.contains(key)) {
                    it = it[key];
                } else {
                    return defaultValue;
                }
            }
            return it.is_boolean() ? it.get<bool>() : defaultValue;
        } catch (...) {
            return defaultValue;
        }
    }

    int GetIntValue(const std::string& path, int defaultValue) const {
        try {
            auto it = configData;
            for (const auto& key : Split(path, '.')) {
                if (it.contains(key)) {
                    it = it[key];
                } else {
                    return defaultValue;
                }
            }
            return it.is_number_integer() ? it.get<int>() : defaultValue;
        } catch (...) {
            return defaultValue;
        }
    }

    double GetDoubleValue(const std::string& path, double defaultValue) const {
        try {
            auto it = configData;
            for (const auto& key : Split(path, '.')) {
                if (it.contains(key)) {
                    it = it[key];
                } else {
                    return defaultValue;
                }
            }
            return it.is_number() ? it.get<double>() : defaultValue;
        } catch (...) {
            return defaultValue;
        }
    }

    /**
     * Get array values from JSON path
     */
    std::vector<std::string> GetArrayValue(const std::string& path) const {
        std::vector<std::string> result;
        try {
            auto it = configData;
            for (const auto& key : Split(path, '.')) {
                if (it.contains(key)) {
                    it = it[key];
                } else {
                    return result;
                }
            }

            if (it.is_array()) {
                for (const auto& item : it) {
                    if (item.is_string()) {
                        result.push_back(item.get<std::string>());
                    }
                }
            }
        } catch (...) {
            // Return empty vector on error
        }
        return result;
    }

    /**
     * Split string by delimiter
     */
    std::vector<std::string> Split(const std::string& str, char delimiter) const {
        std::vector<std::string> tokens;
        std::string token;
        std::istringstream tokenStream(str);

        while (std::getline(tokenStream, token, delimiter)) {
            tokens.push_back(token);
        }

        return tokens;
    }
};

// Example usage
int main() {
    // Load configuration
    ConfigManager config("config.json");

    if (!config.IsLoaded()) {
        std::cerr << "Failed to load configuration" << std::endl;
        return 1;
    }

    // Display configuration
    config.PrintConfiguration();

    // Use configuration in your code
    std::string fredApiKey = config.GetFREDApiKey();
    std::vector<std::string> symbols = config.GetYahooSymbols();
    std::vector<std::string> fredSeries = config.GetFREDSeries();

    std::cout << "FRED API Key loaded: " << (fredApiKey.empty() ? "NO" : "YES") << std::endl;
    std::cout << "Yahoo symbols count: " << symbols.size() << std::endl;
    std::cout << "FRED series count: " << fredSeries.size() << std::endl;

    return 0;
}
