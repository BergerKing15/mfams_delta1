#pragma once

#include <nlohmann/json.hpp>
#include <vector>
#include <algorithm>
#include <cmath>
#include <numeric>
#include <string>

using json = nlohmann::json;

/**
 * Data Utilities - Helper functions for financial data processing
 */
namespace DataUtils {

    // ========== Statistical Functions ==========

    /**
     * Calculate mean (average) of values
     */
    inline double Mean(const std::vector<double>& values) {
        if (values.empty()) return 0.0;
        return std::accumulate(values.begin(), values.end(), 0.0) / values.size();
    }

    /**
     * Calculate standard deviation
     */
    inline double StdDev(const std::vector<double>& values) {
        if (values.size() < 2) return 0.0;
        
        double mean = Mean(values);
        double variance = 0.0;
        
        for (const auto& val : values) {
            variance += std::pow(val - mean, 2);
        }
        
        return std::sqrt(variance / (values.size() - 1));
    }

    /**
     * Calculate median
     */
    inline double Median(std::vector<double> values) {
        if (values.empty()) return 0.0;
        
        std::sort(values.begin(), values.end());
        
        if (values.size() % 2 == 0) {
            return (values[values.size() / 2 - 1] + values[values.size() / 2]) / 2.0;
        } else {
            return values[values.size() / 2];
        }
    }

    /**
     * Calculate percentile
     */
    inline double Percentile(std::vector<double> values, double percentile) {
        if (values.empty()) return 0.0;
        
        std::sort(values.begin(), values.end());
        
        size_t index = static_cast<size_t>(percentile / 100.0 * (values.size() - 1));
        return values[std::min(index, values.size() - 1)];
    }

    /**
     * Calculate correlation between two data series
     */
    inline double Correlation(const std::vector<double>& x, const std::vector<double>& y) {
        if (x.size() != y.size() || x.empty()) return 0.0;
        
        double meanX = Mean(x);
        double meanY = Mean(y);
        double stdX = StdDev(x);
        double stdY = StdDev(y);
        
        if (stdX == 0.0 || stdY == 0.0) return 0.0;
        
        double covariance = 0.0;
        for (size_t i = 0; i < x.size(); ++i) {
            covariance += (x[i] - meanX) * (y[i] - meanY);
        }
        covariance /= x.size();
        
        return covariance / (stdX * stdY);
    }

    // ========== Time Series Functions ==========

    /**
     * Calculate Simple Moving Average
     */
    inline std::vector<double> SimpleMovingAverage(const std::vector<double>& values, size_t period) {
        std::vector<double> sma;
        
        if (values.size() < period) {
            return sma;
        }
        
        for (size_t i = 0; i <= values.size() - period; ++i) {
            double sum = 0.0;
            for (size_t j = 0; j < period; ++j) {
                sum += values[i + j];
            }
            sma.push_back(sum / period);
        }
        
        return sma;
    }

    /**
     * Calculate Exponential Moving Average
     */
    inline std::vector<double> ExponentialMovingAverage(const std::vector<double>& values, size_t period) {
        std::vector<double> ema;
        
        if (values.empty()) {
            return ema;
        }
        
        double multiplier = 2.0 / (period + 1);
        
        // First EMA is the simple average of first 'period' values
        double firstEma = 0.0;
        for (size_t i = 0; i < std::min(period, values.size()); ++i) {
            firstEma += values[i];
        }
        firstEma /= std::min(period, values.size());
        ema.push_back(firstEma);
        
        // Calculate EMA for remaining values
        for (size_t i = std::min(period, values.size()); i < values.size(); ++i) {
            double newEma = (values[i] * multiplier) + (ema.back() * (1.0 - multiplier));
            ema.push_back(newEma);
        }
        
        return ema;
    }

    /**
     * Calculate price returns (percentage change)
     */
    inline std::vector<double> CalculateReturns(const std::vector<double>& prices) {
        std::vector<double> returns;
        
        for (size_t i = 1; i < prices.size(); ++i) {
            if (prices[i - 1] != 0.0) {
                double ret = (prices[i] - prices[i - 1]) / prices[i - 1];
                returns.push_back(ret);
            }
        }
        
        return returns;
    }

    // ========== Data Validation ==========

    /**
     * Check if value is valid number (not NaN or Inf)
     */
    inline bool IsValidNumber(double value) {
        return std::isfinite(value);
    }

    /**
     * Validate JSON data point
     */
    inline bool ValidateDataPoint(const json& point, const std::vector<std::string>& requiredFields) {
        for (const auto& field : requiredFields) {
            if (!point.contains(field) || point[field].is_null()) {
                return false;
            }
        }
        return true;
    }

    /**
     * Check for data discontinuities (large gaps)
     */
    struct DataGap {
        size_t startIndex;
        size_t endIndex;
        double gapSize;
    };

    inline std::vector<DataGap> FindDataGaps(const std::vector<double>& values, double threshold) {
        std::vector<DataGap> gaps;
        
        if (values.size() < 2) {
            return gaps;
        }
        
        double avgChange = 0.0;
        std::vector<double> changes;
        
        for (size_t i = 1; i < values.size(); ++i) {
            changes.push_back(std::abs(values[i] - values[i - 1]));
        }
        
        avgChange = Mean(changes);
        double thresholdValue = avgChange * threshold;
        
        for (size_t i = 1; i < values.size(); ++i) {
            double change = std::abs(values[i] - values[i - 1]);
            if (change > thresholdValue) {
                gaps.push_back({i - 1, i, change});
            }
        }
        
        return gaps;
    }

    // ========== Data Formatting ==========

    /**
     * Format double to string with precision
     */
    inline std::string FormatDouble(double value, int precision = 2) {
        std::ostringstream oss;
        oss << std::fixed << std::setprecision(precision) << value;
        return oss.str();
    }

    /**
     * Convert percentage return to string
     */
    inline std::string FormatReturn(double returnValue) {
        return FormatDouble(returnValue * 100, 2) + "%";
    }

    // ========== Data Extraction Helpers ==========

    /**
     * Extract numeric column from JSON array
     */
    inline std::vector<double> ExtractColumn(const json& data, const std::string& field) {
        std::vector<double> column;
        
        if (!data.is_array()) {
            return column;
        }
        
        for (const auto& point : data) {
            if (point.contains(field) && point[field].is_number()) {
                column.push_back(point[field].get<double>());
            }
        }
        
        return column;
    }

    /**
     * Extract date strings from JSON array
     */
    inline std::vector<std::string> ExtractDates(const json& data) {
        std::vector<std::string> dates;
        
        if (!data.is_array()) {
            return dates;
        }
        
        for (const auto& point : data) {
            if (point.contains("date") && point["date"].is_string()) {
                dates.push_back(point["date"].get<std::string>());
            }
        }
        
        return dates;
    }

    /**
     * Filter data by date range
     */
    inline json FilterByDateRange(const json& data, const std::string& startDate, 
                                  const std::string& endDate) {
        json filtered = json::array();
        
        if (!data.is_array()) {
            return filtered;
        }
        
        for (const auto& point : data) {
            if (point.contains("date")) {
                std::string date = point["date"].get<std::string>();
                if (date >= startDate && date <= endDate) {
                    filtered.push_back(point);
                }
            }
        }
        
        return filtered;
    }

    // ========== Report Generation ==========

    /**
     * Generate summary statistics report
     */
    struct SummaryStats {
        double min = 0.0;
        double max = 0.0;
        double mean = 0.0;
        double median = 0.0;
        double stdDev = 0.0;
        double q1 = 0.0;
        double q3 = 0.0;
        size_t count = 0;
    };

    inline SummaryStats CalculateSummaryStats(const std::vector<double>& values) {
        SummaryStats stats;
        
        if (values.empty()) {
            return stats;
        }
        
        stats.count = values.size();
        stats.mean = Mean(values);
        stats.median = Median(values);
        stats.stdDev = StdDev(values);
        stats.min = *std::min_element(values.begin(), values.end());
        stats.max = *std::max_element(values.begin(), values.end());
        stats.q1 = Percentile(values, 25);
        stats.q3 = Percentile(values, 75);
        
        return stats;
    }

    /**
     * Print summary statistics
     */
    inline void PrintSummaryStats(const std::string& name, const SummaryStats& stats) {
        std::cout << "\n=== " << name << " ===" << std::endl;
        std::cout << "Count:      " << stats.count << std::endl;
        std::cout << "Mean:       " << FormatDouble(stats.mean) << std::endl;
        std::cout << "Median:     " << FormatDouble(stats.median) << std::endl;
        std::cout << "Std Dev:    " << FormatDouble(stats.stdDev) << std::endl;
        std::cout << "Min:        " << FormatDouble(stats.min) << std::endl;
        std::cout << "Max:        " << FormatDouble(stats.max) << std::endl;
        std::cout << "Q1:         " << FormatDouble(stats.q1) << std::endl;
        std::cout << "Q3:         " << FormatDouble(stats.q3) << std::endl;
    }

} // namespace DataUtils

#include <iomanip>
#include <sstream>
#include <iostream>
