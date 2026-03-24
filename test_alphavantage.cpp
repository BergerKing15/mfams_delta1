#include <iostream>
#include <curl/curl.h>
#include <nlohmann/json.hpp>
#include <string>
#include <thread>
#include <chrono>

using json = nlohmann::json;

// Callback for CURL to write response to string
size_t WriteCallback(void* contents, size_t size, size_t nmemb, std::string* s) {
    s->append((char*)contents, size * nmemb);
    return size * nmemb;
}

// ============================================================================
// ALPHA VANTAGE API CLIENT TEST
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
            std::string url = baseURL + "?function=TIME_SERIES_DAILY" +
                            "&symbol=" + symbol +
                            "&apikey=" + apiKey;
                            // Note: outputsize=full is premium-only, using default compact (last 100 days)

            std::cout << "  Fetching: " << url << std::endl;

            curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
            curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, WriteCallback);
            curl_easy_setopt(curl, CURLOPT_WRITEDATA, &readBuffer);
            curl_easy_setopt(curl, CURLOPT_USERAGENT, "Mozilla/5.0 (Windows NT 10.0; Win64; x64)");
            curl_easy_setopt(curl, CURLOPT_SSL_VERIFYPEER, 0L);
            curl_easy_setopt(curl, CURLOPT_TIMEOUT, 30L);

            CURLcode res = curl_easy_perform(curl);

            if (res != CURLE_OK) {
                std::cerr << "  Error: " << curl_easy_strerror(res) << std::endl;
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
            // Print first 500 chars of response for debugging
            std::cout << "  Response (first 500 chars): " << response.substr(0, 500) << std::endl;

            json responseJson = json::parse(response);

            // Check for error messages
            if (responseJson.contains("Error Message")) {
                std::cerr << "  API Error: " << responseJson["Error Message"].get<std::string>() << std::endl;
                return result;
            }

            if (responseJson.contains("Note")) {
                std::cerr << "  API Rate Limit: " << responseJson["Note"].get<std::string>() << std::endl;
                return result;
            }

            if (responseJson.contains("Information")) {
                std::cerr << "  API Information: " << responseJson["Information"].get<std::string>() << std::endl;
                return result;
            }

            // Extract time series data - looking for "Time Series (Daily)" key
            std::string timeSeriesKey = "Time Series (Daily)";
            if (!responseJson.contains(timeSeriesKey)) {
                std::cerr << "  No time series data in response" << std::endl;
                std::cout << "  Available keys: ";
                for (auto& el : responseJson.items()) {
                    std::cout << el.key() << " ";
                }
                std::cout << std::endl;
                return result;
            }

            auto timeSeries = responseJson[timeSeriesKey];

            // Iterate through each date and build result
            int count = 0;
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
                        {"volume", volume}
                    };

                    result.push_back(dataPoint);
                    count++;
                } catch (const std::exception& e) {
                    std::cerr << "    Error parsing " << date << ": " << e.what() << std::endl;
                    continue;
                }
            }

            std::cout << "  ✓ Parsed " << count << " days from Alpha Vantage" << std::endl;

        } catch (const std::exception& e) {
            std::cerr << "  JSON Parse Error: " << e.what() << std::endl;
        }

        return result;
    }
};

int main() {
    std::cout << "=== Testing Alpha Vantage Integration ===" << std::endl;

    std::string alphaVantageApiKey = "LDH5SBMS1ZZ3NW35";
    std::vector<std::string> symbols = {"GDX", "NEM"};  // Test with just 2 symbols

    AlphaVantageClient client(alphaVantageApiKey);

    for (const auto& symbol : symbols) {
        std::cout << "\nFetching " << symbol << "..." << std::endl;
        json data = client.FetchStockData(symbol);
        
        if (!data.empty()) {
            std::cout << "  Retrieved " << data.size() << " records" << std::endl;
            
            // Show first 3 records
            std::cout << "  First 3 records:" << std::endl;
            for (size_t i = 0; i < std::min(size_t(3), data.size()); i++) {
                std::cout << "    " << data[i]["date"] << ": Close=$" 
                          << data[i]["close"] << std::endl;
            }
        } else {
            std::cout << "  No data returned" << std::endl;
        }

        // Rate limiting: 5 requests per minute = 12 seconds between requests
        std::cout << "  Waiting 12 seconds before next request..." << std::endl;
        std::this_thread::sleep_for(std::chrono::seconds(12));
    }

    std::cout << "\n=== Test Complete ===" << std::endl;
    return 0;
}
