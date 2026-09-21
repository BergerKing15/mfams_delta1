// Verifies MarketCalendar against published NYSE closure dates.
// Build: g++ -std=c++17 -o test_market_calendar test_market_calendar.cpp

#include "market_calendar.hpp"
#include <iostream>
#include <vector>
#include <string>

static int failures = 0;

static void ExpectYear(int year, const std::vector<std::string>& expected) {
    const std::set<std::string>& actual = MarketCalendar::HolidaysForYear(year);
    std::set<std::string> want(expected.begin(), expected.end());

    std::cout << year << ": ";
    if (actual == want) {
        std::cout << "OK (" << actual.size() << " holidays)" << std::endl;
        return;
    }

    ++failures;
    std::cout << "MISMATCH" << std::endl;
    for (std::set<std::string>::const_iterator it = want.begin(); it != want.end(); ++it)
        if (!actual.count(*it)) std::cout << "    missing:   " << *it << std::endl;
    for (std::set<std::string>::const_iterator it = actual.begin(); it != actual.end(); ++it)
        if (!want.count(*it)) std::cout << "    unexpected: " << *it << std::endl;
}

int main() {
    // Published NYSE holiday calendars.
    ExpectYear(2024, {"2024-01-01","2024-01-15","2024-02-19","2024-03-29","2024-05-27",
                      "2024-06-19","2024-07-04","2024-09-02","2024-11-28","2024-12-25"});
    ExpectYear(2025, {"2025-01-01","2025-01-20","2025-02-17","2025-04-18","2025-05-26",
                      "2025-06-19","2025-07-04","2025-09-01","2025-11-27","2025-12-25"});
    // 2026: July 4 is a Saturday, observed Friday July 3.
    ExpectYear(2026, {"2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25",
                      "2026-06-19","2026-07-03","2026-09-07","2026-11-26","2026-12-25"});
    // 2027: Juneteenth Sat -> Fri 6/18, July 4 Sun -> Mon 7/5, Christmas Sat -> Fri 12/24.
    ExpectYear(2027, {"2027-01-01","2027-01-18","2027-02-15","2027-03-26","2027-05-31",
                      "2027-06-18","2027-07-05","2027-09-06","2027-11-25","2027-12-24"});
    // 2028: New Year's Day is a Saturday, so there is no closure for it at all.
    ExpectYear(2028, {"2028-01-17","2028-02-21","2028-04-14","2028-05-29","2028-06-19",
                      "2028-07-04","2028-09-04","2028-11-23","2028-12-25"});
    // 2033: New Year's Day is a Saturday again; Christmas is a Sunday -> Mon 12/26.
    ExpectYear(2033, {"2033-01-17","2033-02-21","2033-04-15","2033-05-30","2033-06-20",
                      "2033-07-04","2033-09-05","2033-11-24","2033-12-26"});

    // The three days this project's database wrongly filled as trading days.
    const char* regressions[] = {"2026-01-01", "2026-01-19", "2026-02-16"};
    for (const char* d : regressions) {
        bool ok = MarketCalendar::IsHoliday(d);
        std::cout << "regression " << d << ": " << (ok ? "recognized" : "NOT RECOGNIZED") << std::endl;
        if (!ok) ++failures;
    }

    // Ordinary trading days must not be flagged.
    const char* tradingDays[] = {"2026-01-02", "2026-03-24", "2027-07-06"};
    for (const char* d : tradingDays) {
        bool bad = MarketCalendar::IsHoliday(d);
        std::cout << "trading day " << d << ": " << (bad ? "WRONGLY FLAGGED" : "ok") << std::endl;
        if (bad) ++failures;
    }

    std::cout << (failures == 0 ? "\nALL TESTS PASSED" : "\nFAILURES: ") << (failures ? std::to_string(failures) : "") << std::endl;
    return failures == 0 ? 0 : 1;
}
