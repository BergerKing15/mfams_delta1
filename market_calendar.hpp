#ifndef MARKET_CALENDAR_HPP
#define MARKET_CALENDAR_HPP

// US equity market holiday calendar, computed rather than hardcoded.
//
// A hardcoded list silently expires: once the calendar year moves past the last
// entry, every holiday looks like an ordinary trading day and the gap filler
// fabricates price bars for days the market was closed.
//
// Rules implemented (NYSE Rule 7.2):
//   - Fixed-date holidays falling on Saturday are observed the preceding Friday,
//     and on Sunday the following Monday.
//   - Exception: when New Year's Day falls on a Saturday, the exchange does NOT
//     close the preceding Friday.
//   - Good Friday is always a Friday, so it needs no observance shift.
//
// Not covered: ad-hoc closures (national days of mourning, weather), which
// cannot be derived from a rule.

#include <string>
#include <set>
#include <map>
#include <sstream>
#include <iomanip>

class MarketCalendar {
public:
    // Is this "YYYY-MM-DD" a full-day market closure?
    static bool IsHoliday(const std::string& dateStr) {
        if (dateStr.size() < 10) return false;
        int year = 0;
        try {
            year = std::stoi(dateStr.substr(0, 4));
        } catch (const std::exception&) {
            return false;
        }
        const std::set<std::string>& holidays = HolidaysForYear(year);
        return holidays.count(dateStr) > 0;
    }

    // Sunday = 0 ... Saturday = 6. Sakamoto's method: pure arithmetic, so it
    // avoids localtime()/mktime() and their timezone and DST surprises.
    static int DayOfWeek(int y, int m, int d) {
        static const int t[] = {0, 3, 2, 5, 0, 3, 5, 1, 4, 6, 2, 4};
        if (m < 3) y -= 1;
        return (y + y / 4 - y / 100 + y / 400 + t[m - 1] + d) % 7;
    }

    // All closures for a year, as "YYYY-MM-DD". Cached per year.
    static const std::set<std::string>& HolidaysForYear(int year) {
        static std::map<int, std::set<std::string>> cache;
        std::map<int, std::set<std::string>>::iterator it = cache.find(year);
        if (it != cache.end()) return it->second;

        std::set<std::string> holidays;

        // New Year's Day - observed Monday if it lands on Sunday, but never
        // rolled back to the previous Friday.
        {
            int m = 1, d = 1;
            int dow = DayOfWeek(year, m, d);
            if (dow == 0) {           // Sunday -> Monday
                d = 2;
                holidays.insert(FormatDate(year, m, d));
            } else if (dow != 6) {    // Saturday -> no closure at all
                holidays.insert(FormatDate(year, m, d));
            }
        }

        holidays.insert(NthWeekdayOfMonth(year, 1, 1, 3));   // MLK Day: 3rd Monday in January
        holidays.insert(NthWeekdayOfMonth(year, 2, 1, 3));   // Presidents' Day: 3rd Monday in February
        holidays.insert(GoodFriday(year));
        holidays.insert(LastWeekdayOfMonth(year, 5, 1));     // Memorial Day: last Monday in May
        holidays.insert(ObservedFixedDate(year, 6, 19));     // Juneteenth
        holidays.insert(ObservedFixedDate(year, 7, 4));      // Independence Day
        holidays.insert(NthWeekdayOfMonth(year, 9, 1, 1));   // Labor Day: 1st Monday in September
        holidays.insert(NthWeekdayOfMonth(year, 11, 4, 4));  // Thanksgiving: 4th Thursday in November
        holidays.insert(ObservedFixedDate(year, 12, 25));    // Christmas

        cache[year] = holidays;
        return cache[year];
    }

private:
    static std::string FormatDate(int y, int m, int d) {
        std::ostringstream oss;
        oss << std::setfill('0') << std::setw(4) << y << "-"
            << std::setw(2) << m << "-" << std::setw(2) << d;
        return oss.str();
    }

    static bool IsLeapYear(int y) {
        return (y % 4 == 0 && y % 100 != 0) || (y % 400 == 0);
    }

    static int DaysInMonth(int y, int m) {
        static const int days[] = {31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31};
        if (m == 2 && IsLeapYear(y)) return 29;
        return days[m - 1];
    }

    // Shift a date by whole days, rolling across month and year boundaries.
    static void AddDays(int& y, int& m, int& d, int delta) {
        while (delta > 0) {
            ++d;
            if (d > DaysInMonth(y, m)) { d = 1; ++m; if (m > 12) { m = 1; ++y; } }
            --delta;
        }
        while (delta < 0) {
            --d;
            if (d < 1) { --m; if (m < 1) { m = 12; --y; } d = DaysInMonth(y, m); }
            ++delta;
        }
    }

    // weekday: Sunday = 0 ... Saturday = 6. n is 1-based.
    static std::string NthWeekdayOfMonth(int y, int m, int weekday, int n) {
        int firstDow = DayOfWeek(y, m, 1);
        int day = 1 + ((weekday - firstDow) + 7) % 7 + (n - 1) * 7;
        return FormatDate(y, m, day);
    }

    static std::string LastWeekdayOfMonth(int y, int m, int weekday) {
        int last = DaysInMonth(y, m);
        int lastDow = DayOfWeek(y, m, last);
        int day = last - ((lastDow - weekday) + 7) % 7;
        return FormatDate(y, m, day);
    }

    // Saturday -> preceding Friday, Sunday -> following Monday.
    static std::string ObservedFixedDate(int y, int m, int d) {
        int dow = DayOfWeek(y, m, d);
        int oy = y, om = m, od = d;
        if (dow == 6) AddDays(oy, om, od, -1);
        else if (dow == 0) AddDays(oy, om, od, 1);
        return FormatDate(oy, om, od);
    }

    // Easter Sunday by the anonymous Gregorian algorithm; Good Friday is two days before.
    static std::string GoodFriday(int y) {
        int a = y % 19;
        int b = y / 100;
        int c = y % 100;
        int d = b / 4;
        int e = b % 4;
        int f = (b + 8) / 25;
        int g = (b - f + 1) / 3;
        int h = (19 * a + b - d - g + 15) % 30;
        int i = c / 4;
        int k = c % 4;
        int l = (32 + 2 * e + 2 * i - h - k) % 7;
        int m = (a + 11 * h + 22 * l) / 451;
        int month = (h + l - 7 * m + 114) / 31;
        int day = ((h + l - 7 * m + 114) % 31) + 1;

        int gy = y, gm = month, gd = day;
        AddDays(gy, gm, gd, -2);
        return FormatDate(gy, gm, gd);
    }
};

#endif  // MARKET_CALENDAR_HPP
