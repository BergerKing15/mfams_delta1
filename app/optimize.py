#!/usr/bin/env python3
"""Parameter search and walk-forward validation.

Sliding a parameter until the equity curve looks good is how backtests lie. The
point of this module is to make that failure mode measurable:

  * ``sweep`` scores every parameter combination on the whole sample. That is
    in-sample performance - the number you get by hunting for the best setting
    and then quoting it. It is an upper bound, not an expectation.

  * ``walk_forward`` picks parameters using only data up to a point in time and
    scores them on the period that follows, repeatedly. Nothing is chosen with
    knowledge of the period it is scored on, so the result approximates what the
    strategy would have delivered had it been run live.

The distance between the two is the overfitting premium. A strategy with a
strong in-sample Sharpe and a weak walk-forward Sharpe has told you it was
fitted to noise.
"""

from __future__ import annotations

import sys
from itertools import product
from pathlib import Path

import pandas as pd

APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from strategies import STRATEGIES, Strategy  # noqa: E402

DB_PATH = PROJECT_ROOT / "data" / "financial_data.db"

# Grids are deliberately small. With ~100 trading days per symbol, a large grid
# guarantees a flattering in-sample winner and tells you nothing.
PARAM_GRIDS = {
    'Z-Score (Macro Signal)': {
        'ma_period': [10, 20, 40],
        'zscore_threshold': [0.5, 1.0, 1.5, 2.0],
        'fred_lag_days': [30],
    },
    'MA Crossover': {
        'fast_ma': [5, 10, 20],
        'slow_ma': [30, 50, 80],
    },
    'RSI (Overbought/Oversold)': {
        'rsi_period': [7, 14, 21],
        'oversold': [20, 30],
        'overbought': [70, 80],
    },
    'Mean Reversion': {
        'ma_period': [10, 20, 40],
        'std_dev_threshold': [1.0, 1.5, 2.0, 2.5],
    },
}


def expand_grid(grid):
    """Every valid combination in a parameter grid."""
    keys = list(grid)
    combos = [dict(zip(keys, values)) for values in product(*(grid[k] for k in keys))]
    # A crossover needs the fast average to actually be faster than the slow one.
    return [c for c in combos
            if not ('fast_ma' in c and 'slow_ma' in c and c['fast_ma'] >= c['slow_ma'])]


def evaluate(strategy_cls, stock_df, fred_df, params, cost_bps=5.0,
             risk_free_rate=0.0, window=None):
    """Run one parameter set, scoring it over ``window`` if given.

    ``window`` is a (start, end) pair of positional indices. The strategy still
    sees every row up to ``end`` so its indicators can warm up, but only rows
    inside the window are scored. Since every signal is causal, letting the
    strategy see earlier rows leaks nothing.
    """
    full_params = dict(params)
    full_params['transaction_cost_bps'] = cost_bps

    try:
        results = strategy_cls(stock_df, fred_df, **full_params).calculate_signals()
    except Exception:
        return None
    if results is None or len(results) == 0:
        return None

    if window is not None:
        start, end = window
        results = results.iloc[start:end]
        if len(results) < 2:
            return None

    metrics = Strategy.calculate_metrics(results, risk_free_rate=risk_free_rate)
    if not metrics:
        return None
    return {**params, **metrics, 'observations': len(results)}


def sweep(strategy_name, stock_df, fred_df, cost_bps=5.0, risk_free_rate=0.0):
    """Score every parameter combination on the full sample (in-sample)."""
    strategy_cls = STRATEGIES[strategy_name]
    rows = []
    for params in expand_grid(PARAM_GRIDS[strategy_name]):
        row = evaluate(strategy_cls, stock_df, fred_df, params,
                       cost_bps=cost_bps, risk_free_rate=risk_free_rate)
        if row:
            rows.append(row)
    if not rows:
        return pd.DataFrame()
    return (pd.DataFrame(rows)
            .sort_values('sharpe_ratio', ascending=False)
            .reset_index(drop=True))


def walk_forward(strategy_name, stock_df, fred_df, n_splits=4, min_train=40,
                 cost_bps=5.0, risk_free_rate=0.0, min_trades=1):
    """Choose parameters on past data only, score them on the period after.

    Anchored (expanding) window: each fold trains on everything before it and is
    tested on the fold itself. Returns one row per fold.
    """
    strategy_cls = STRATEGIES[strategy_name]
    combos = expand_grid(PARAM_GRIDS[strategy_name])
    n = len(stock_df)
    if n < min_train + n_splits * 5:
        return pd.DataFrame()

    fold_size = (n - min_train) // n_splits
    if fold_size < 5:
        return pd.DataFrame()

    folds = []
    for i in range(n_splits):
        train_end = min_train + i * fold_size
        test_end = train_end + fold_size if i < n_splits - 1 else n

        # --- selection: in-sample only, never sees the test window ---
        best, best_sharpe = None, float('-inf')
        for params in combos:
            row = evaluate(strategy_cls, stock_df.iloc[:train_end], fred_df, params,
                           cost_bps=cost_bps, risk_free_rate=risk_free_rate)
            if row and row['num_trades'] >= min_trades and row['sharpe_ratio'] > best_sharpe:
                best, best_sharpe = params, row['sharpe_ratio']
        if best is None:
            continue

        # --- evaluation: those parameters, on the untouched window ---
        oos = evaluate(strategy_cls, stock_df, fred_df, best,
                       cost_bps=cost_bps, risk_free_rate=risk_free_rate,
                       window=(train_end, test_end))
        if oos is None:
            continue

        folds.append({
            'fold': i + 1,
            'train_days': train_end,
            'test_days': test_end - train_end,
            'chosen_params': ', '.join(f'{k}={v}' for k, v in best.items()),
            'in_sample_sharpe': best_sharpe,
            'out_of_sample_sharpe': oos['sharpe_ratio'],
            'out_of_sample_return': oos['total_return'],
            'trades': oos['num_trades'],
        })

    return pd.DataFrame(folds)


def compare_symbols(strategy_name, params, symbols, load_stock, fred_df,
                    cost_bps=5.0, risk_free_rate=0.0):
    """Same parameters across many symbols.

    An edge that exists on one ticker and nowhere else is usually a property of
    that ticker's sample, not of the strategy.
    """
    strategy_cls = STRATEGIES[strategy_name]
    rows = []
    for symbol in symbols:
        stock_df = load_stock(symbol)
        if stock_df is None or len(stock_df) == 0:
            continue
        row = evaluate(strategy_cls, stock_df, fred_df, params,
                       cost_bps=cost_bps, risk_free_rate=risk_free_rate)
        if row:
            rows.append({
                'symbol': symbol,
                'sharpe_ratio': row['sharpe_ratio'],
                'total_return': row['total_return'],
                'buy_hold_return': row['buy_hold_return'],
                'max_drawdown': row['max_drawdown'],
                'num_trades': row['num_trades'],
            })
    return pd.DataFrame(rows)


def _cli():
    import argparse
    import sqlite3

    parser = argparse.ArgumentParser(
        description="Parameter sweep and walk-forward validation")
    parser.add_argument('--symbol', default='GDX')
    parser.add_argument('--fred', default='UNRATE')
    parser.add_argument('--strategy', default='MA Crossover', choices=list(STRATEGIES))
    parser.add_argument('--cost-bps', type=float, default=5.0)
    parser.add_argument('--risk-free', type=float, default=0.0)
    parser.add_argument('--splits', type=int, default=4)
    args = parser.parse_args()

    conn = sqlite3.connect(str(DB_PATH))
    stock = pd.read_sql_query(
        f"SELECT date, open, high, low, close, volume FROM stock_{args.symbol} ORDER BY date",
        conn)
    stock['date'] = pd.to_datetime(stock['date'])
    fred = pd.read_sql_query(
        f"SELECT date, value FROM fred_{args.fred} ORDER BY date", conn)
    fred['date'] = pd.to_datetime(fred['date'])

    print(f"\n{args.strategy} on {args.symbol} ({len(stock)} trading days, "
          f"{args.cost_bps} bps costs, {args.risk_free}% risk-free)\n")

    table = sweep(args.strategy, stock, fred, args.cost_bps, args.risk_free)
    if table.empty:
        print("No parameter combination produced a result.")
        return

    cols = ([c for c in PARAM_GRIDS[args.strategy] if c in table.columns]
            + ['sharpe_ratio', 'total_return', 'max_drawdown', 'num_trades'])
    print(f"In-sample sweep (best 5 of {len(table)} combinations):")
    print(table[cols].head(5).to_string(index=False,
                                        float_format=lambda v: f"{v:8.2f}"))

    folds = walk_forward(args.strategy, stock, fred, n_splits=args.splits,
                         cost_bps=args.cost_bps, risk_free_rate=args.risk_free)
    print("\nWalk-forward (parameters chosen on past data only):")
    if folds.empty:
        print(f"  Not enough data for {args.splits} folds.")
        return
    print(folds.to_string(index=False, float_format=lambda v: f"{v:8.2f}"))

    best_is = table['sharpe_ratio'].iloc[0]
    mean_oos = folds['out_of_sample_sharpe'].mean()
    print(f"\n  best in-sample Sharpe:      {best_is:6.2f}")
    print(f"  mean out-of-sample Sharpe:  {mean_oos:6.2f}")
    print(f"  overfitting premium:        {best_is - mean_oos:6.2f}")
    print("\n  The premium is how much of the in-sample result came from fitting")
    print("  the sample rather than finding an edge.\n")


if __name__ == '__main__':
    _cli()
