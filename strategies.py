"""
Custom Trading Strategy Library
Base class for implementing and extending trading strategies
"""

import pandas as pd
import numpy as np
from scipy import stats
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
        
        sharpe = (backtest_df['strategy_returns'].mean() / backtest_df['strategy_returns'].std()) * np.sqrt(252) \
            if backtest_df['strategy_returns'].std() > 0 else 0
        
        win_rate = (backtest_df[backtest_df['strategy_returns'] > 0].shape[0] / 
                   backtest_df[backtest_df['strategy_returns'] != 0].shape[0] * 100) \
            if backtest_df[backtest_df['strategy_returns'] != 0].shape[0] > 0 else 0
        
        max_dd = ((backtest_df['cumulative_returns'].cummax() - backtest_df['cumulative_returns']) / 
                 backtest_df['cumulative_returns'].cummax()).max() * 100
        
        return {
            'total_return': total_return,
            'buy_hold_return': buy_hold_return,
            'sharpe_ratio': sharpe,
            'win_rate': win_rate,
            'max_drawdown': max_dd,
            'num_trades': (backtest_df['signal'] != backtest_df['signal'].shift(1)).sum(),
            'final_equity': backtest_df['cumulative_returns'].iloc[-1]
        }


class ZScoreStrategy(Strategy):
    """Trade based on FRED economic indicator Z-score"""
    name = "Z-Score (Macro Signal)"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        ma_period = self.params.get('ma_period', 20)
        zscore_threshold = self.params.get('zscore_threshold', 2.0)
        position_size = self.params.get('position_size', 1.0)
        
        # Forward-fill FRED values to daily frequency
        fred_clean = self.fred_df[['date', 'value']].set_index('date')
        fred_filled = fred_clean.reindex(
            pd.date_range(self.fred_df['date'].min(), self.stock_df['date'].max(), freq='D')
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
        
        # Z-score of FRED
        fred_values = merged['value'].dropna()
        if len(fred_values) > 1:
            merged['fred_zscore'] = np.nan
            merged.loc[fred_values.index, 'fred_zscore'] = stats.zscore(fred_values)
        else:
            merged['fred_zscore'] = 0
        
        # Generate signals
        merged['signal'] = 0
        merged.loc[merged['fred_zscore'] > zscore_threshold, 'signal'] = 1
        merged.loc[merged['fred_zscore'] < -zscore_threshold, 'signal'] = -1
        
        # Calculate returns
        merged['returns'] = merged['close'].pct_change()
        merged['strategy_returns'] = merged['signal'].shift(1) * merged['returns'] * position_size
        merged['strategy_returns'] = merged['strategy_returns'].fillna(0)
        
        return merged


class MACrossoverStrategy(Strategy):
    """Trade based on moving average crossover (MA50 / MA200)"""
    name = "MA Crossover"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        fast_ma = self.params.get('fast_ma', 50)
        slow_ma = self.params.get('slow_ma', 200)
        position_size = self.params.get('position_size', 1.0)
        
        if len(merged) < slow_ma:
            return None
        
        # Calculate MAs
        merged['fast_ma'] = merged['close'].rolling(window=fast_ma).mean()
        merged['slow_ma'] = merged['close'].rolling(window=slow_ma).mean()
        
        # Generate signals: fast MA > slow MA = bullish
        merged['signal'] = 0
        merged.loc[merged['fast_ma'] > merged['slow_ma'], 'signal'] = 1
        merged.loc[merged['fast_ma'] < merged['slow_ma'], 'signal'] = -1
        
        # Calculate returns
        merged['returns'] = merged['close'].pct_change()
        merged['strategy_returns'] = merged['signal'].shift(1) * merged['returns'] * position_size
        merged['strategy_returns'] = merged['strategy_returns'].fillna(0)
        
        return merged


class RSIStrategy(Strategy):
    """Trade based on Relative Strength Index (RSI)"""
    name = "RSI (Overbought/Oversold)"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        rsi_period = self.params.get('rsi_period', 14)
        overbought = self.params.get('overbought', 70)
        oversold = self.params.get('oversold', 30)
        position_size = self.params.get('position_size', 1.0)
        
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
        
        # Calculate returns
        merged['returns'] = merged['close'].pct_change()
        merged['strategy_returns'] = merged['signal'].shift(1) * merged['returns'] * position_size
        merged['strategy_returns'] = merged['strategy_returns'].fillna(0)
        
        return merged


class MeanReversionStrategy(Strategy):
    """Trade based on price deviation from moving average (mean reversion)"""
    name = "Mean Reversion"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        ma_period = self.params.get('ma_period', 20)
        std_dev_threshold = self.params.get('std_dev_threshold', 2.0)
        position_size = self.params.get('position_size', 1.0)
        
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
        
        # Calculate returns
        merged['returns'] = merged['close'].pct_change()
        merged['strategy_returns'] = merged['signal'].shift(1) * merged['returns'] * position_size
        merged['strategy_returns'] = merged['strategy_returns'].fillna(0)
        
        return merged


# Registry of available strategies
STRATEGIES = {
    'Z-Score (Macro Signal)': ZScoreStrategy,
    'MA Crossover': MACrossoverStrategy,
    'RSI (Overbought/Oversold)': RSIStrategy,
    'Mean Reversion': MeanReversionStrategy,
}
