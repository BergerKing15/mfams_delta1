#ifndef OUTLIER_FILTER_HPP
#define OUTLIER_FILTER_HPP

// Bad-tick detection for daily price series.
//
// Applying an IQR filter to price *levels* is the wrong frame: in a trending
// series the highest and lowest prices are the newest and oldest ones, not
// errors, and a genuine crash sits far from the median while being perfectly
// real. Outliers in market data are anomalies in the *returns*.
//
// A data error in a daily series has a recognisable shape: the price jumps and
// immediately comes back. A real move does not revert the next day. So a point
// is flagged only when the return into it and the return out of it are both
// extreme and point in opposite directions. That keeps real crashes and rallies
// and catches the spike-and-revert signature of a bad print.
//
// The filter is deliberately conservative - it would rather keep a bad tick
// than delete a real move, since a deleted real move is unrecoverable and
// silently biases every backtest that follows.

#include <vector>
#include <algorithm>
#include <cstddef>
#include <cmath>

namespace OutlierFilter {

// Nearest-rank quartiles over an already-sorted sample.
inline double Quantile(const std::vector<double>& sorted, double q) {
    if (sorted.empty()) return 0.0;
    size_t idx = static_cast<size_t>(q * (sorted.size() - 1));
    if (idx >= sorted.size()) idx = sorted.size() - 1;
    return sorted[idx];
}

// Indices of values that look like bad prints, given a chronological series.
// Needs at least 4 points; the first and last points are never flagged,
// because a reversal cannot be confirmed at the edges.
inline std::vector<size_t> FlagSpikes(const std::vector<double>& values,
                                      double iqrMultiplier = 1.5) {
    std::vector<size_t> flagged;
    if (values.size() < 4) return flagged;

    // returns[i] is the move from values[i-1] into values[i].
    std::vector<double> returns(values.size(), 0.0);
    for (size_t i = 1; i < values.size(); ++i) {
        if (values[i - 1] == 0.0) continue;
        returns[i] = values[i] / values[i - 1] - 1.0;
    }

    std::vector<double> sorted(returns.begin() + 1, returns.end());
    std::sort(sorted.begin(), sorted.end());

    double q1 = Quantile(sorted, 0.25);
    double q3 = Quantile(sorted, 0.75);
    double iqr = q3 - q1;

    // A degenerate spread gives no usable scale, so flag nothing rather than
    // flag everything.
    if (iqr <= 0.0) return flagged;

    double lower = q1 - iqrMultiplier * iqr;
    double upper = q3 + iqrMultiplier * iqr;

    for (size_t i = 1; i + 1 < values.size(); ++i) {
        double into = returns[i];
        double out  = returns[i + 1];

        bool intoExtreme = (into < lower || into > upper);
        bool outExtreme  = (out  < lower || out  > upper);
        bool reverses    = (into > 0.0 && out < 0.0) || (into < 0.0 && out > 0.0);

        if (intoExtreme && outExtreme && reverses) flagged.push_back(i);
    }

    return flagged;
}

// Replacement value for a flagged point: the midpoint of its neighbours.
inline double InterpolatedValue(const std::vector<double>& values, size_t index) {
    if (index == 0 || index + 1 >= values.size()) return values[index];
    return (values[index - 1] + values[index + 1]) / 2.0;
}

}  // namespace OutlierFilter

#endif  // OUTLIER_FILTER_HPP
