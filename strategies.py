"""
Custom Trading Strategy Library
Base class for implementing and extending trading strategies
"""

import pandas as pd
import numpy as np
from abc import ABC, abstractmethod


class Strategy(ABC):
    """Base class for all trading strategies"""
    
    def __init__(self, stock_df, fred_df, **params):
        """
        Args:
            stock_df: DataFrame with columns [date, open, high, low, close, volume]
            fred_df: DataFrame with columns [date, value]
            **params: Strategy-specific parameters
        """
        self.stock_df = stock_df.copy()
        self.fred_df = fred_df.copy()
        self.params = params
    
    def apply_returns(self, merged):
        """Compute returns from a 'signal' column, net of transaction costs.

        Every strategy should end with this rather than computing
        strategy_returns by hand, so costs are booked consistently.

        Positions are lagged one day: a signal formed on day t earns day t+1's
        return. Cost is charged on the day exposure changes, in proportion to
        how much it changed.
        """
        position_size = self.params.get('position_size', 1.0)
        cost_bps = self.params.get('transaction_cost_bps', 0.0)

        merged['returns'] = merged['close'].pct_change()
        exposure = merged['signal'] * position_size
        merged['gross_returns'] = (exposure.shift(1) * merged['returns']).fillna(0)

        # Turnover on the first row is the cost of establishing the position.
        turnover = exposure.diff().abs()
        if len(turnover):
            turnover.iloc[0] = abs(exposure.iloc[0])
        merged['transaction_costs'] = (turnover * (cost_bps / 10000.0)).fillna(0)
        merged['strategy_returns'] = merged['gross_returns'] - merged['transaction_costs']
        return merged

    @abstractmethod
    def calculate_signals(self):
        """
        Must return DataFrame with columns:
        - date, close, returns
        - signal (1=long, -1=short, 0=no position)
        - strategy_returns (daily P&L)
        - cumulative_returns, buy_hold (for performance tracking)
        """
        pass
    
    @staticmethod
    def calculate_metrics(backtest_df):
        """Calculate performance metrics from backtest results"""
        if backtest_df is None or len(backtest_df) == 0:
            return {}
        
        backtest_df = backtest_df.copy()
        backtest_df['cumulative_returns'] = (1 + backtest_df['strategy_returns']).cumprod()
        backtest_df['buy_hold'] = (1 + backtest_df['returns']).cumprod()
        
        total_return = (backtest_df['cumulative_returns'].iloc[-1] - 1) * 100
        buy_hold_return = (backtest_df['buy_hold'].iloc[-1] - 1) * 100

        sharpe = (backtest_df['strategy_returns'].mean() / backtest_df['strategy_returns'].std()) * np.sqrt(252)             if backtest_df['strategy_returns'].std() > 0 else 0

        max_dd = ((backtest_df['cumulative_returns'].cummax() - backtest_df['cumulative_returns']) /
                 backtest_df['cumulative_returns'].cummax()).max() * 100

        trades = Strategy.extract_trades(backtest_df)
        num_trades = len(trades)
        win_rate = (sum(1 for t in trades if t > 0) / num_trades * 100) if num_trades else 0

        # Share of *days* in the market that were profitable. Reported separately
        # because win_rate is per trade, and the two are easily confused.
        active = backtest_df[backtest_df['strategy_returns'] != 0]
        win_rate_days = (active[active['strategy_returns'] > 0].shape[0] /
                         active.shape[0] * 100) if active.shape[0] > 0 else 0

        total_costs = backtest_df['transaction_costs'].sum() * 100             if 'transaction_costs' in backtest_df.columns else 0.0

        return {
            'total_return': total_return,
            'buy_hold_return': buy_hold_return,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'win_rate_days': win_rate_days,
            'max_drawdown': max_dd,
            'num_trades': num_trades,
            'total_costs': total_costs,
            'final_equity': backtest_df['cumulative_returns'].iloc[-1]
        }

    @staticmethod
    def extract_trades(backtest_df):
        """Return each completed trade's return, as a fraction.

        A trade is one unbroken stretch of non-zero exposure. Flipping straight
        from long to short closes one trade and opens another.
        """
        signal = backtest_df['signal'].fillna(0)
        returns = backtest_df['strategy_returns'].fillna(0)

        trades = []
        equity = 1.0
        current = 0
        for i in range(len(signal)):
            held = signal.iloc[i - 1] if i > 0 else 0   # yesterday's exposure earns today
            if held != current:
                if current != 0:
                    trades.append(equity - 1)
                equity = 1.0
                current = held
            if held != 0:
                equity *= (1 + returns.iloc[i])
        if current != 0:
            trades.append(equity - 1)
        return trades


class ZScoreStrategy(Strategy):
    """Trade based on FRED economic indicator Z-score"""
    name = "Z-Score (Macro Signal)"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        ma_period = self.params.get('ma_period', 20)
        zscore_threshold = self.params.get('zscore_threshold', 2.0)
        
        # FRED observations are published well after the period they describe
        # (UNRATE for March is released in early April). Shifting the dates
        # forward by the release lag keeps the signal causal; without it the
        # strategy trades on numbers nobody had yet.
        fred_lag_days = self.params.get('fred_lag_days', 30)
        lagged = self.fred_df[['date', 'value']].copy()
        lagged['date'] = lagged['date'] + pd.Timedelta(days=fred_lag_days)

        # Forward-fill FRED values to daily frequency
        fred_clean = lagged.set_index('date')
        fred_filled = fred_clean.reindex(
            pd.date_range(lagged['date'].min(), self.stock_df['date'].max(), freq='D')
        ).ffill().reset_index()
        fred_filled.columns = ['date', 'value']
        
        # Merge with stock data
        merged = pd.merge(merged, fred_filled, on='date', how='left')
        merged = merged.sort_values('date').reset_index(drop=True)
        merged = merged.dropna(subset=['value']).reset_index(drop=True)
        
        if len(merged) < ma_period:
            return None
        
        # Calculate technical indicators
        merged['ma'] = merged['close'].rolling(window=ma_period).mean()
        merged['deviation'] = merged['close'] - merged['ma']
        
        # Z-score of FRED, computed causally.
        # An expanding window uses only data available up to each row; a full-sample
        # zscore() would score early rows using statistics drawn from later ones, which
        # leaks future information into past signals.
        zscore_min_periods = self.params.get('zscore_min_periods', 20)
        values = merged['value']
        mean = values.expanding(min_periods=zscore_min_periods).mean()
        std = values.expanding(min_periods=zscore_min_periods).std()
        merged['fred_zscore'] = ((values - mean) / std.replace(0, np.nan)).fillna(0)
        
        # Generate signals
        merged['signal'] = 0
        merged.loc[merged['fred_zscore'] > zscore_threshold, 'signal'] = 1
        merged.loc[merged['fred_zscore'] < -zscore_threshold, 'signal'] = -1
        
        # Returns net of costs (see Strategy.apply_returns)
        merged = self.apply_returns(merged)
        
        return merged


class MACrossoverStrategy(Strategy):
    """Trade based on moving average crossover (MA20 / MA50)"""
    name = "MA Crossover"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        fast_ma = self.params.get('fast_ma', 20)
        slow_ma = self.params.get('slow_ma', 50)
        
        if len(merged) < slow_ma:
            return None
        
        # Calculate MAs
        merged['ma'] = merged['close'].rolling(window=fast_ma).mean()  # For visualization
        merged['fast_ma'] = merged['close'].rolling(window=fast_ma).mean()
        merged['slow_ma'] = merged['close'].rolling(window=slow_ma).mean()
        
        # Generate signals: fast MA > slow MA = bullish
        merged['signal'] = 0
        merged.loc[merged['fast_ma'] > merged['slow_ma'], 'signal'] = 1
        merged.loc[merged['fast_ma'] < merged['slow_ma'], 'signal'] = -1
        
        # Returns net of costs (see Strategy.apply_returns)
        merged = self.apply_returns(merged)
        
        return merged


class RSIStrategy(Strategy):
    """Trade based on Relative Strength Index (RSI)"""
    name = "RSI (Overbought/Oversold)"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        rsi_period = self.params.get('rsi_period', 14)
        overbought = self.params.get('overbought', 70)
        oversold = self.params.get('oversold', 30)
        
        if len(merged) < rsi_period:
            return None
        
        # Calculate RSI
        delta = merged['close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=rsi_period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=rsi_period).mean()
        rs = gain / loss
        merged['rsi'] = 100 - (100 / (1 + rs))
        
        # Generate signals
        merged['signal'] = 0
        merged.loc[merged['rsi'] > overbought, 'signal'] = -1  # Sell when overbought
        merged.loc[merged['rsi'] < oversold, 'signal'] = 1    # Buy when oversold
        
        # Returns net of costs (see Strategy.apply_returns)
        merged = self.apply_returns(merged)
        
        return merged


class MeanReversionStrategy(Strategy):
    """Trade based on price deviation from moving average (mean reversion)"""
    name = "Mean Reversion"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        ma_period = self.params.get('ma_period', 20)
        std_dev_threshold = self.params.get('std_dev_threshold', 2.0)
        
        if len(merged) < ma_period:
            return None
        
        # Calculate MA and standard deviation
        merged['ma'] = merged['close'].rolling(window=ma_period).mean()
        merged['std'] = merged['close'].rolling(window=ma_period).std()
        
        # Calculate z-score of price vs MA
        merged['price_zscore'] = (merged['close'] - merged['ma']) / merged['std']
        
        # Generate signals: buy when price too low, sell when too high
        merged['signal'] = 0
        merged.loc[merged['price_zscore'] < -std_dev_threshold, 'signal'] = 1   # Buy
        merged.loc[merged['price_zscore'] > std_dev_threshold, 'signal'] = -1   # Sell
        
        # Returns net of costs (see Strategy.apply_returns)
        merged = self.apply_returns(merged)
        
        return merged


# Registry of available strategies
STRATEGIES = {
    'Z-Score (Macro Signal)': ZScoreStrategy,
    'MA Crossover': MACrossoverStrategy,
    'RSI (Overbought/Oversold)': RSIStrategy,
    'Mean Reversion': MeanReversionStrategy,
}
