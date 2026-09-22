# 🎛️ MFAMS Delta1 Backtesting Dashboard

Interactive web app for testing trading strategies with macro + equity data.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Dashboard
```bash
streamlit run app/dashboard.py
```

This will start the app at **http://localhost:8501**

## 📊 Features

### Interactive Controls (Sidebar)

Always available:
- **Stock Symbol** / **FRED Indicator**: whatever is in the database, discovered
  automatically from the `stock_` and `fred_` table prefixes
- **Strategy**: Z-Score, MA Crossover, RSI or Mean Reversion (see
  [STRATEGIES.md](STRATEGIES.md))
- **Position Size**: leverage multiplier (0.1x - 3.0x)
- **Transaction Cost (bps)**: charged per unit of exposure traded, default 5.
  Total Return is always net of this
- **Risk-Free Rate (annual %)**: the rate Sharpe is measured against, default 0.
  The help text shows the latest FEDFUNDS value in your database

Strategy-specific controls appear below those and change with the selection - MA
periods for the crossover, RSI thresholds for RSI, and for Z-Score a **FRED Release
Lag** that keeps the macro signal causal.

### Visualizations
1. **Equity Curve**: Strategy vs Buy & Hold comparison
2. **Price & Signals**: Candlestick with entry/exit markers and moving average
3. **Macro Indicator**: Historical FRED values for reference
4. **Returns Distribution**: Daily return histogram
5. **Correlation Scatter**: FRED Z-Score vs stock returns
6. **Trade Log**: Recent activity with entry/exit details

### Performance Metrics
- **Total Return %**: strategy gain, net of transaction costs, with the buy & hold
  difference shown beneath it
- **Sharpe Ratio**: annualised, measured against the risk-free rate you set
- **Win Rate %**: share of completed *trades* that made money, where a trade is one
  unbroken stretch of exposure. The tooltip also gives the share of profitable days,
  which is a different and usually higher number
- **Max Drawdown %**: worst peak-to-trough decline
- **Transaction Costs %**: cumulative drag, already deducted from Total Return

A warning appears above the metrics when a symbol has under 250 trading days. On the
free Alpha Vantage tier every symbol does, so treat the numbers as a way to compare
parameter choices rather than evidence a strategy works.

## 🎯 Strategy Explanation

Four strategies ship with the dashboard; the Z-Score one is described here because it
is the only strategy that uses the macro series. The others are documented in
[STRATEGIES.md](STRATEGIES.md).

### Z-Score Signal Generation
1. Shift the FRED series forward by the **release lag**, so the signal only uses
   figures that were public at the time
2. Compute an **expanding-window Z-score** of the indicator - expanding, not
   full-sample, so past signals cannot see future data
3. **Buy** when the Z-score rises above the threshold, **sell** when it falls below
   the negative threshold
4. Exposure is lagged one day: a signal on day *t* earns day *t+1*'s return
5. **Position size** and **transaction costs** are applied to the result

### Use Cases
- **QR Testing**: "What if we use a stricter 3.0 Z-score? How does win rate change?"
- **Analyst Testing**: "Does a 50-day MA work better than 20-day for GDX?"
- **Risk Analysis**: "What's the maximum drawdown with 2x leverage?"
- **Cost Sensitivity**: "Does this still work at 20 bps, or only at zero?"
- **Macro Linkage**: "Is UNRATE or CPIAUCSL better for predicting gold?"

## 📈 Example Workflow

1. Select **GDX** (gold mining ETF) and **UNRATE** (unemployment rate)
2. Adjust **MA Period** from 20 to 50
3. Watch equity curve update in real-time
4. Observe that longer MA = fewer but potentially more reliable signals
5. Tweak **Z-Score Threshold** from 2.0 to 1.5 for more aggressive trading
6. Raise **Transaction Cost** and watch how quickly a high-turnover setting gives back
   its edge
7. Set **Risk-Free Rate** to the current FEDFUNDS value to see whether the strategy
   beats cash
8. Compare Sharpe ratio and max drawdown

## 🔧 Customization

### Add New Markets or FRED Series
Easiest is the **Add Custom Stock or FRED Data** panel at the bottom of the app - it
fetches and stores without touching the C++ pipeline, and the new symbol appears in
the sidebar immediately.

To add them to the regular pipeline run, edit `config.json`:
```json
"alphaVantage": { "symbols": ["GDX", "YOUR_SYMBOL"] },
"fredApi":      { "series":  ["UNRATE", "YOUR_INDICATOR"] }
```
No recompile needed; the pipeline reads both lists at startup.

### Modify or Add a Strategy
Strategies live in `app/strategies.py`, not in the dashboard. Subclass `Strategy`,
set a `signal` column, finish with `return self.apply_returns(merged)`, and register
the class in the `STRATEGIES` dict at the bottom of the file. The full walkthrough is
in [STRATEGIES.md](STRATEGIES.md).

To try one without editing the repo, use the **Upload Custom Strategy** panel;
`app/example_custom_strategy.py` is a working template.

## 🔬 Validation

The **Validation: Parameter Sweep & Walk-Forward** section runs the full parameter grid
in-sample, then runs walk-forward folds in which parameters are selected using only data
that precedes the window they are scored on. It reports the overfitting premium - the
difference between the two - and warns when a tuned result fails to survive.

It also applies the in-sample winner to every symbol in the database. Treat agreement
there cautiously: the default universe is mostly gold miners correlating about 0.77 with
one another, so it is closer to two independent bets than eight.

The same analysis is available headlessly:

```bash
python app/optimize.py --symbol GDX --strategy "MA Crossover" --splits 4
```

## 📊 Data Sources
- **FRED API**: Economic indicators (1947-present), published with a release lag the
  dashboard models
- **Alpha Vantage**: Daily stock prices, roughly the last 100 trading days on the free
  tier, with no dividend adjustment
- **SQLite**: `data/financial_data.db`, the only thing shared between the C++ pipeline
  and this app

See "Known Limitations" in the [README](../README.md) for what these constraints mean
for interpreting results.

## 🎓 Next Steps
1. Add risk parity position sizing
2. Implement Kelly Criterion for optimal leverage
3. Add option Greeks for hedging strategies
4. Connect to live trading API (backtest to execution)

---

**Built for MFAMS Alpha Pod backtesting | March 2026**
