# Custom Strategies Guide

## Overview

The MFAMS Delta1 dashboard supports multiple trading strategies. Choose from **4 pre-built strategies** or implement custom strategies in Python.

---

## Built-in Strategies

### 1. **Z-Score (Macro Signal)** 
**Best for:** Macro-based trading using economic indicators

Trades based on the Z-score (standard deviation) of FRED economic indicators. The Z-score
uses an **expanding window**, so each day is scored only against data available up to that
day - a full-sample Z-score would leak future information into past signals:
- **Buy Signal:** FRED indicator Z-score > Threshold (economic conditions favor the stock)
- **Sell Signal:** FRED indicator Z-score < -Threshold

**Adjustable Parameters:**
- **Moving Average Period** (5-100): Period for calculating stock price moving average
- **Z-Score Threshold** (0.5-5.0): How many standard deviations to trigger signals
- **FRED Release Lag** (0-90 days, default 30): How long after the observation period the
  figure actually becomes public. Setting this to 0 reintroduces lookahead bias
- **Position Size** (0.1-3.0x): Leverage multiplier

**Best Used With:**
- UNRATE (unemployment) for cyclical stocks
- CPIAUCSL (inflation) for defensive stocks
- FEDFUNDS (interest rates) for financial stocks

---

### 2. **MA Crossover**
**Best for:** Trend following with simple moving averages

Classic moving average crossover strategy:
- **Buy Signal:** Fast MA crosses above Slow MA (uptrend begins)
- **Sell Signal:** Fast MA crosses below Slow MA (downtrend begins)

**Adjustable Parameters:**
- **Fast MA Period** (5-50): Short-term moving average (default 20)
- **Slow MA Period** (20-100): Long-term moving average (default 50)
- **Position Size** (0.1-3.0x): Leverage multiplier

**Note:** The textbook version of this indicator is 50/200, but the free Alpha Vantage tier
returns only ~100 trading days per symbol, so a 200-day slow MA leaves no data to trade on.
The defaults are 20/50 for that reason.

---

### 3. **RSI (Overbought/Oversold)**
**Best for:** Mean reversion in ranging markets

Trades based on Relative Strength Index (momentum oscillator):
- **Buy Signal:** RSI < Oversold Threshold (price too low, likely to bounce)
- **Sell Signal:** RSI > Overbought Threshold (price too high, likely to reverse)

**Adjustable Parameters:**
- **RSI Period** (5-50): Lookback period for calculation (default 14)
- **Oversold Threshold** (5-50): RSI level for buy signals (default 30)
- **Overbought Threshold** (50-95): RSI level for sell signals (default 70)
- **Position Size** (0.1-3.0x): Leverage multiplier

**Note:** RSI oscillates 0-100; extreme values indicate reversals

---

### 4. **Mean Reversion**
**Best for:** Trading price deviations from equilibrium

Trades when price deviates from its moving average:
- **Buy Signal:** Price falls > 2 std devs below MA (oversold)
- **Sell Signal:** Price rises > 2 std devs above MA (overbought)

**Adjustable Parameters:**
- **Moving Average Period** (5-100): Period for MA calculation
- **Standard Deviation Threshold** (0.5-5.0): Deviation bands
- **Position Size** (0.1-3.0x): Leverage multiplier

**Assumption:** Price tends to revert to its mean over time

---

## Shared Mechanics

These apply to every strategy, built-in or custom.

**Transaction costs.** `Transaction Cost (bps)` in the sidebar charges a cost per unit of
exposure traded, defaulting to 5 bps. `Total Return` is always net of costs; the
`Transaction Costs` tile shows the cumulative drag. Set it to 0 for frictionless results,
but remember that a strategy which only looks profitable at 0 bps is not profitable.

**Position lag.** A signal formed on day *t* earns day *t+1*'s return. Strategies never
trade on the same bar they compute a signal from.

**Win Rate is per trade**, where a trade is one unbroken stretch of non-zero exposure;
flipping long to short closes one trade and opens another. The share of profitable *days*
is shown in the metric's tooltip, and is a different (usually higher) number.

**Causality.** Any signal must use only data available at the time. The Z-Score strategy
uses an expanding window and lags the FRED series by its release delay for this reason.

## Creating Custom Strategies

### Step 1: Understand the Base Class

All strategies inherit from `Strategy`:

```python
from strategies import Strategy
import pandas as pd
import numpy as np

class MyStrategy(Strategy):
    name = "My Custom Strategy"
    
    def calculate_signals(self):
        # Your implementation here
        merged = self.stock_df.copy()
        
        # Access parameters
        custom_param = self.params.get('custom_param', 20)
        
        # Generate signals (1=long, -1=short, 0=flat)
        merged['signal'] = 0
        merged.loc[some_condition, 'signal'] = 1
        
        # Returns, position lag and transaction costs are handled centrally.
        # Always finish with this instead of computing strategy_returns by hand.
        merged = self.apply_returns(merged)
        
        return merged
```

### Step 2: Access Available Data

Your strategy has access to:

**Stock Data:**
- `self.stock_df` — DataFrame with columns: `date, open, high, low, close, volume`

**Economic Data:**
- `self.fred_df` — DataFrame with columns: `date, value` (FRED economic indicator)

**Parameters:**
- `self.params` — Dictionary with strategy parameters passed from the UI

### Step 3: Generate Signals

Create a `signal` column with values:
- `1` = **Long position** (bullish)
- `-1` = **Short position** (bearish)
- `0` = **No position** (flat)

You only set `signal`. The one-day execution lag is applied for you, so a signal on day
*t* earns day *t+1*'s return.

### Step 4: Finish with apply_returns()

```python
return self.apply_returns(merged)
```

This fills in `returns`, `gross_returns`, `transaction_costs` and `strategy_returns`,
applying the position lag, the `position_size` multiplier and the transaction cost from the
sidebar. Computing `strategy_returns` yourself means your backtest silently ignores costs
and will look better than it is.

The returned DataFrame then has, at minimum:
- `date, close, returns, signal, strategy_returns`

### Step 5: Upload to Dashboard

1. Save your strategy as `my_strategy.py`
2. Go to the dashboard and expand **"Upload Custom Strategy"**
3. Click **"Upload custom strategy (.py)"** and select your file
4. Click **"Test Custom Strategy"** to backtest
5. Adjust parameters and re-test

---

## Example: Bollinger Bands Strategy

```python
from strategies import Strategy
import pandas as pd
import numpy as np

class BollingerBandsStrategy(Strategy):
    name = "Bollinger Bands"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        # Parameters
        ma_period = self.params.get('ma_period', 20)
        num_std = self.params.get('num_std', 2.0)
        
        # Calculate bands
        merged['ma'] = merged['close'].rolling(window=ma_period).mean()
        merged['std'] = merged['close'].rolling(window=ma_period).std()
        merged['upper'] = merged['ma'] + (num_std * merged['std'])
        merged['lower'] = merged['ma'] - (num_std * merged['std'])
        
        # Signals
        merged['signal'] = 0
        merged.loc[merged['close'] < merged['lower'], 'signal'] = 1   # Buy
        merged.loc[merged['close'] > merged['upper'], 'signal'] = -1  # Sell
        
        # Returns, position lag and transaction costs
        return self.apply_returns(merged)
```

---

## Tips for Writing Good Strategies

1. **Avoid look-ahead bias:** Don't use future data (use `shift()` for timing)
2. **Handle edge cases:** Check for NaN values and minimum data requirements
3. **Keep it simple:** Complex strategies don't always outperform simple ones
4. **Test thoroughly:** Compare to buy-and-hold baseline
5. **Consider risk:** Adjust position size to control drawdowns
6. **Document logic:** Add comments explaining your trading rules

---

## Testing Your Strategy

The dashboard displays:
- **Total Return** vs Buy & Hold baseline
- **Sharpe Ratio** (risk-adjusted return)
- **Win Rate** (% of profitable trades)
- **Max Drawdown** (largest peak-to-trough decline)
- **Number of Trades** (activity level)

Use these metrics to evaluate strategy quality.

---

## File Structure

```
dashboard.py              # Main Streamlit app
strategies.py             # Base Strategy class + built-in strategies
example_custom_strategy.py # Example custom strategy template
custom_strategy.py        # Upload your custom strategy here
```

---

## Common Issues

**Error:** `"No Strategy class found in uploaded file"`
- Make sure your class inherits from `Strategy`
- Make sure you have `from strategies import Strategy` at the top

**Error:** `KeyError: 'some_column'`
- Check that your signal logic references existing DataFrame columns
- Verify the FRED data is being loaded correctly

**Low performance?**
- Adjust parameters using the sliders before uploading
- Consider the trading costs (real-world spreads/slippage)
- Validate against longer time periods

---

## Next Steps

- Try modifying `example_custom_strategy.py` strategies
- Create your own strategy combining technical + macro indicators
- Compare different parameter combinations
- Download results for further analysis

Happy backtesting! 🚀
