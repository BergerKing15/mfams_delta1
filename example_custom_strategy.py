"""
Example Custom Strategy Template
Upload this file (or a modified version) to the dashboard to test custom strategies
"""

from strategies import Strategy
import pandas as pd
import numpy as np


class BollingerBandStrategy(Strategy):
    """
    Trade when price breaks Bollinger Bands
    - Buy when price drops below lower band
    - Sell when price rises above upper band
    """
    
    name = "Bollinger Bands Breakout"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        # Get parameters from self.params
        ma_period = self.params.get('ma_period', 20)
        num_std = self.params.get('num_std', 2.0)
        position_size = self.params.get('position_size', 1.0)
        
        if len(merged) < ma_period:
            return None
        
        # Calculate Bollinger Bands
        merged['ma'] = merged['close'].rolling(window=ma_period).mean()
        merged['std'] = merged['close'].rolling(window=ma_period).std()
        merged['upper_band'] = merged['ma'] + (num_std * merged['std'])
        merged['lower_band'] = merged['ma'] - (num_std * merged['std'])
        
        # Generate signals
        merged['signal'] = 0
        
        # Buy when price breaks below lower band
        merged.loc[merged['close'] < merged['lower_band'], 'signal'] = 1
        
        # Sell when price breaks above upper band
        merged.loc[merged['close'] > merged['upper_band'], 'signal'] = -1
        
        # Calculate returns
        merged['returns'] = merged['close'].pct_change()
        merged['strategy_returns'] = merged['signal'].shift(1) * merged['returns'] * position_size
        merged['strategy_returns'] = merged['strategy_returns'].fillna(0)
        
        return merged


class MOMOMentumStrategy(Strategy):
    """
    Simple momentum strategy: follow the trend
    - Buy when price rises more than threshold
    - Sell when price falls more than threshold
    """
    
    name = "Price Momentum"
    
    def calculate_signals(self):
        merged = self.stock_df.copy()
        
        # Get parameters
        momentum_period = self.params.get('momentum_period', 10)
        momentum_threshold = self.params.get('momentum_threshold', 0.02)  # 2%
        position_size = self.params.get('position_size', 1.0)
        
        if len(merged) < momentum_period:
            return None
        
        # Calculate momentum (% change over period)
        merged['momentum'] = merged['close'].pct_change(periods=momentum_period)
        
        # Generate signals based on momentum
        merged['signal'] = 0
        merged.loc[merged['momentum'] > momentum_threshold, 'signal'] = 1   # Buy
        merged.loc[merged['momentum'] < -momentum_threshold, 'signal'] = -1  # Sell
        
        # Calculate returns
        merged['returns'] = merged['close'].pct_change()
        merged['strategy_returns'] = merged['signal'].shift(1) * merged['returns'] * position_size
        merged['strategy_returns'] = merged['strategy_returns'].fillna(0)
        
        return merged
