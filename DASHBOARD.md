# 🎛️ MFAMS Delta1 Backtesting Dashboard

Interactive web app for testing trading strategies with macro + equity data.

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run the Dashboard
```bash
streamlit run dashboard.py
```

This will start the app at **http://localhost:8501**

## 📊 Features

### Interactive Controls (Sidebar)
- **Stock Symbol**: Select from GDX, NEM, GOLD, AEM, AU, KGC, CPER
- **FRED Indicator**: Choose UNRATE, CPIAUCSL, FEDFUNDS, or other macro series
- **Moving Average Period**: Adjust 5-100 day MA (affects entry signals)
- **Z-Score Threshold**: Control sensitivity of macro trigger (0.5-5.0)
- **Position Size**: Test leverage effects (0.1x - 3.0x)

### Visualizations
1. **Equity Curve**: Strategy vs Buy & Hold comparison
2. **Price & Signals**: Candlestick with entry/exit markers and moving average
3. **Macro Indicator**: Historical FRED values for reference
4. **Returns Distribution**: Daily return histogram
5. **Correlation Scatter**: FRED Z-Score vs stock returns
6. **Trade Log**: Recent activity with entry/exit details

### Performance Metrics
- **Total Return %**: Strategy gain vs initial capital
- **Sharpe Ratio**: Risk-adjusted returns (higher = better)
- **Win Rate %**: Percentage of profitable trades
- **Max Drawdown %**: Worst peak-to-trough decline
- **Trade Count**: Total signals generated

## 🎯 Strategy Explanation

### Signal Generation
1. Calculate **moving average** of stock closing prices (tunable period)
2. Compute **Z-score** of FRED economic indicator (unemployment, CPI, Fed rate, etc.)
3. **Buy signal** when Z-score > threshold (macro improving)
4. **Sell signal** when Z-score < -threshold (macro deteriorating)
5. **Position sizing** applied for leverage testing

### Use Cases
- **QR Testing**: "What if we use a stricter 3.0 Z-score? How does win rate change?"
- **Analyst Testing**: "Does 50-day MA work better than 20-day for GDX?"
- **Risk Analysis**: "What's the maximum drawdown with 2x leverage?"
- **Macro Linkage**: "Is UNRATE or CPIAUCSL better for predicting gold?"

## 📈 Example Workflow

1. Select **GDX** (gold mining ETF) and **UNRATE** (unemployment rate)
2. Adjust **MA Period** from 20 to 50
3. Watch equity curve update in real-time
4. Observe that longer MA = fewer but potentially more reliable signals
5. Tweak **Z-Score Threshold** from 2.0 to 1.5 for more aggressive trading
6. Compare Sharpe ratio and max drawdown
7. Export insights for Alpha Pod presentation

## 🔧 Customization

### Add New Markets
Edit `pipeline.cpp` to fetch additional stocks:
```cpp
std::vector<std::string> stocks = {"GDX", "YOUR_NEW_SYMBOL", ...};
```

### Add New FRED Series
Update `config.json`:
```json
"series": ["UNRATE", "YOUR_INDICATOR", ...]
```

### Modify Strategy
Edit `BacktestEngine.calculate_signals()` in `dashboard.py`:
- Change signal generation logic
- Add multiple indicators
- Implement stop-loss/take-profit

## 📊 Data Sources
- **FRED API**: Economic indicators (1947-present)
- **Alpha Vantage**: Stock prices (recent 100 days)
- **SQLite**: Local database persistence

## 🎓 Next Steps
1. Add risk parity position sizing
2. Implement Kelly Criterion for optimal leverage
3. Add option Greeks for hedging strategies
4. Connect to live trading API (backtest to execution)

---

**Built for MFAMS Alpha Pod backtesting | March 2026**
