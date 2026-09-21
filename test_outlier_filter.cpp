// Tests for the return-based bad-tick filter.
// Build: g++ -std=c++17 -o test_outlier_filter test_outlier_filter.cpp

#include "outlier_filter.hpp"
#include <iostream>
#include <vector>
#include <string>
#include <cmath>

static int failures = 0;

static void Check(const std::string& name, bool ok, const std::string& detail = "") {
    std::cout << (ok ? "  PASS  " : "  FAIL  ") << name;
    if (!ok && !detail.empty()) std::cout << "  (" << detail << ")";
    std::cout << std::endl;
    if (!ok) ++failures;
}

static std::string Join(const std::vector<size_t>& v) {
    std::string s;
    for (size_t i : v) s += std::to_string(i) + " ";
    return s.empty() ? "none" : s;
}

// A plausible daily series: small alternating noise around a drift.
static std::vector<double> NoisySeries(size_t n, double start, double drift) {
    std::vector<double> v;
    double p = start;
    for (size_t i = 0; i < n; ++i) {
        // i is size_t: cast before subtracting, or the expression wraps.
        double noise = (static_cast<int>(i % 5) - 2) * 0.004;   // -0.8% .. +0.8%
        p *= (1.0 + drift + noise);
        v.push_back(p);
    }
    return v;
}

int main() {
    std::cout << "Spike-and-revert detection" << std::endl;
    {
        std::vector<double> v = NoisySeries(60, 100.0, 0.0005);
        double original = v[30];
        v[30] *= 1.40;                       // bad print: +40% that comes straight back
        std::vector<size_t> f = OutlierFilter::FlagSpikes(v);
        Check("flags the spike", f.size() == 1 && f[0] == 30, "got: " + Join(f));

        double repaired = OutlierFilter::InterpolatedValue(v, 30);
        Check("repair lands near the true value",
              std::fabs(repaired - original) / original < 0.02,
              "repaired=" + std::to_string(repaired) + " true=" + std::to_string(original));
    }
    {
        std::vector<double> v = NoisySeries(60, 100.0, 0.0005);
        v[30] *= 0.60;                       // downward bad print
        std::vector<size_t> f = OutlierFilter::FlagSpikes(v);
        Check("flags a downward spike", f.size() == 1 && f[0] == 30, "got: " + Join(f));
    }

    std::cout << "Real moves are preserved" << std::endl;
    {
        // A genuine crash: -25% that does NOT revert. Level-based IQR would
        // have treated the whole post-crash regime as outliers.
        std::vector<double> v = NoisySeries(30, 100.0, 0.0005);
        std::vector<double> after = NoisySeries(30, v.back() * 0.75, 0.0005);
        v.insert(v.end(), after.begin(), after.end());
        std::vector<size_t> f = OutlierFilter::FlagSpikes(v);
        Check("does not flag a one-way crash", f.empty(), "got: " + Join(f));
    }
    {
        // Strong sustained trend: every price is "far from the median" by level,
        // but no single day is anomalous.
        std::vector<double> v = NoisySeries(100, 50.0, 0.008);   // ~0.8%/day
        std::vector<size_t> f = OutlierFilter::FlagSpikes(v);
        Check("does not flag a strong trend", f.empty(), "got: " + Join(f));
    }

    std::cout << "Edge cases" << std::endl;
    {
        Check("empty series", OutlierFilter::FlagSpikes({}).empty());
        Check("too few points", OutlierFilter::FlagSpikes({10.0, 11.0, 10.5}).empty());
        std::vector<double> flat(50, 42.0);
        Check("flat series flags nothing", OutlierFilter::FlagSpikes(flat).empty());
        std::vector<double> zeros(10, 0.0);
        Check("zero prices do not divide by zero", OutlierFilter::FlagSpikes(zeros).empty());

        // A spike on the final bar cannot be confirmed as a reversal, so it stays.
        std::vector<double> v = NoisySeries(40, 100.0, 0.0005);
        v.back() *= 1.5;
        std::vector<size_t> f = OutlierFilter::FlagSpikes(v);
        Check("unconfirmable final-bar move is kept", f.empty(), "got: " + Join(f));
    }

    std::cout << std::endl
              << (failures == 0 ? "ALL TESTS PASSED" : "FAILURES: " + std::to_string(failures))
              << std::endl;
    return failures == 0 ? 0 : 1;
}
