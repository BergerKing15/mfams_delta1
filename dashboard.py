#!/usr/bin/env python3
"""
MFAMS Delta1 Backtesting Dashboard
Interactive Streamlit app for testing trading strategies with macro + equity data
"""

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats

# ============================================================================
# DATA LOADING
# ============================================================================

@st.cache_resource
def get_db_connection():
    """Get SQLite connection"""
    db_path = Path("financial_data.db")
    if not db_path.exists():
        st.error("❌ Database not found. Run the C++ pipeline first!")
        st.stop()
    return sqlite3.connect(str(db_path))

@st.cache_data
def load_fred_data(series_id):
    """Load FRED economic data"""
    conn = get_db_connection()
    table_name = f"fred_{series_id}"
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY date", conn)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except:
        st.warning(f"⚠️ Could not load {series_id}")
        return pd.DataFrame()

@st.cache_data
def load_stock_data(symbol):
    """Load stock price data"""
    conn = get_db_connection()
    table_name = f"stock_{symbol}"
    try:
        df = pd.read_sql_query(f"SELECT date, open, high, low, close, volume FROM {table_name} ORDER BY date", conn)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except:
        st.warning(f"⚠️ Could not load {symbol}")
        return pd.DataFrame()

@st.cache_data
def get_available_symbols():
    """Get list of available stock symbols"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'stock_%'")
    tables = cursor.fetchall()
    return [t[0].replace('stock_', '') for t in tables]

@st.cache_data
def get_available_fred_series():
    """Get list of available FRED series"""
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'fred_%'")
    tables = cursor.fetchall()
    return [t[0].replace('fred_', '') for t in tables]

# ============================================================================
# BACKTESTING LOGIC
# ============================================================================

class BacktestEngine:
    def __init__(self, stock_df, fred_df, ma_period=20, zscore_threshold=2.0, position_size=1.0):
        self.stock_df = stock_df.copy()
        self.fred_df = fred_df.copy()
        self.ma_period = ma_period
        self.zscore_threshold = zscore_threshold
        self.position_size = position_size
        
    def calculate_signals(self):
        """Generate trading signals based on Z-score"""
        # Merge data on date
        merged = pd.merge(
            self.stock_df,
            self.fred_df[['date', 'value']],
            on='date',
            how='inner'
        ).sort_values('date')
        
        if len(merged) < self.ma_period:
            st.warning("Not enough data for backtesting")
            return None
        
        # Calculate moving average of close price
        merged['ma'] = merged['close'].rolling(window=self.ma_period).mean()
        
        # Calculate price deviation
        merged['deviation'] = merged['close'] - merged['ma']
        
        # Calculate Z-score of FRED value
        merged['fred_zscore'] = stats.zscore(merged['value'].fillna(merged['value'].mean()))
        
        # Trading signal: FRED high (Z > threshold) = bullish for stocks
        merged['signal'] = 0  # 0 = no position
        merged.loc[merged['fred_zscore'] > self.zscore_threshold, 'signal'] = 1   # Long
        merged.loc[merged['fred_zscore'] < -self.zscore_threshold, 'signal'] = -1  # Short
        
        # Calculate returns
        merged['returns'] = merged['close'].pct_change()
        merged['strategy_returns'] = merged['signal'].shift(1) * merged['returns'] * self.position_size
        
        return merged
    
    def calculate_metrics(self, backtest_df):
        """Calculate performance metrics"""
        if backtest_df is None or len(backtest_df) == 0:
            return {}
        
        # Cumulative returns
        backtest_df['cumulative_returns'] = (1 + backtest_df['strategy_returns']).cumprod()
        backtest_df['buy_hold'] = (1 + backtest_df['returns']).cumprod()
        
        # Metrics
        total_return = (backtest_df['cumulative_returns'].iloc[-1] - 1) * 100
        buy_hold_return = (backtest_df['buy_hold'].iloc[-1] - 1) * 100
        
        sharpe = (backtest_df['strategy_returns'].mean() / backtest_df['strategy_returns'].std()) * np.sqrt(252) if backtest_df['strategy_returns'].std() > 0 else 0
        
        win_rate = (backtest_df[backtest_df['strategy_returns'] > 0].shape[0] / 
                   backtest_df[backtest_df['strategy_returns'] != 0].shape[0] * 100) if backtest_df[backtest_df['strategy_returns'] != 0].shape[0] > 0 else 0
        
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

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="MFAMS Delta1 Backtest", layout="wide")

st.title("📊 MFAMS Delta1 Backtesting Dashboard")
st.markdown("**Interactive strategy testing with macro + equity data**")

# Sidebar controls
st.sidebar.header("⚙️ Strategy Parameters")

# Data selection
stock_options = get_available_symbols()
fred_options = get_available_fred_series()

selected_stock = st.sidebar.selectbox("📈 Stock Symbol", stock_options, index=0)
selected_fred = st.sidebar.selectbox("📉 FRED Indicator", fred_options, index=0)

# Strategy parameters
ma_period = st.sidebar.slider(
    "Moving Average Period",
    min_value=5, max_value=100, value=20, step=5,
    help="Period for calculating moving average of stock price"
)

zscore_threshold = st.sidebar.slider(
    "Z-Score Threshold",
    min_value=0.5, max_value=5.0, value=2.0, step=0.5,
    help="Trigger trading signal when FRED Z-score exceeds this threshold"
)

position_size = st.sidebar.slider(
    "Position Size",
    min_value=0.1, max_value=3.0, value=1.0, step=0.1,
    help="Multiplier for position (1.0 = full position, 2.0 = 2x leverage)"
)

# Load data
stock_data = load_stock_data(selected_stock)
fred_data = load_fred_data(selected_fred)

if stock_data.empty or fred_data.empty:
    st.error("No data available. Check database.")
    st.stop()

# Run backtest
engine = BacktestEngine(stock_data, fred_data, ma_period, zscore_threshold, position_size)
backtest_results = engine.calculate_signals()
metrics = engine.calculate_metrics(backtest_results)

# Display metrics in columns
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        "Total Return",
        f"{metrics.get('total_return', 0):.2f}%",
        delta=f"vs B&H: {metrics.get('total_return', 0) - metrics.get('buy_hold_return', 0):.2f}%"
    )

with col2:
    st.metric(
        "Sharpe Ratio",
        f"{metrics.get('sharpe_ratio', 0):.2f}",
        delta=f"Risk-adjusted return"
    )

with col3:
    st.metric(
        "Win Rate",
        f"{metrics.get('win_rate', 0):.1f}%",
        delta=f"{int(metrics.get('num_trades', 0))} trades"
    )

with col4:
    st.metric(
        "Max Drawdown",
        f"{metrics.get('max_drawdown', 0):.2f}%",
        delta="Peak-to-trough decline"
    )

# Charts
st.subheader("📈 Equity Curve")

fig_equity = go.Figure()
fig_equity.add_trace(go.Scatter(
    x=backtest_results['date'],
    y=backtest_results['cumulative_returns'],
    mode='lines',
    name='Strategy',
    line=dict(color='#00D9FF', width=2)
))
fig_equity.add_trace(go.Scatter(
    x=backtest_results['date'],
    y=backtest_results['buy_hold'],
    mode='lines',
    name='Buy & Hold',
    line=dict(color='#FF6B6B', width=2, dash='dash')
))
fig_equity.update_layout(
    title=f"Strategy vs Buy & Hold ({selected_stock})",
    xaxis_title="Date",
    yaxis_title="Cumulative Value",
    hovermode='x unified',
    height=400
)
st.plotly_chart(fig_equity, use_container_width=True)

# Price and signals
st.subheader("📊 Price & Trading Signals")

fig_signals = go.Figure()

# Price
fig_signals.add_trace(go.Scatter(
    x=backtest_results['date'],
    y=backtest_results['close'],
    mode='lines',
    name='Close Price',
    line=dict(color='#9C27B0', width=2)
))

# Moving average
fig_signals.add_trace(go.Scatter(
    x=backtest_results['date'],
    y=backtest_results['ma'],
    mode='lines',
    name=f'{ma_period}-Day MA',
    line=dict(color='#FF9800', width=2, dash='dot')
))

# Buy signals
buy_signals = backtest_results[backtest_results['signal'] == 1]
fig_signals.add_trace(go.Scatter(
    x=buy_signals['date'],
    y=buy_signals['close'],
    mode='markers',
    name='Buy Signal',
    marker=dict(color='#4CAF50', size=10, symbol='triangle-up')
))

# Sell signals
sell_signals = backtest_results[backtest_results['signal'] == -1]
fig_signals.add_trace(go.Scatter(
    x=sell_signals['date'],
    y=sell_signals['close'],
    mode='markers',
    name='Sell Signal',
    marker=dict(color='#F44336', size=10, symbol='triangle-down')
))

fig_signals.update_layout(
    title=f"{selected_stock} Price with Trading Signals",
    xaxis_title="Date",
    yaxis_title="Price ($)",
    hovermode='x unified',
    height=400
)
st.plotly_chart(fig_signals, use_container_width=True)

# FRED indicator
st.subheader("📉 Macro Indicator (FRED)")

fig_fred = go.Figure()
fig_fred.add_trace(go.Scatter(
    x=fred_data['date'],
    y=fred_data['value'],
    mode='lines',
    name=selected_fred,
    line=dict(color='#2196F3', width=2)
))

fig_fred.update_layout(
    title=f"{selected_fred} Historical Values",
    xaxis_title="Date",
    yaxis_title="Value",
    hovermode='x unified',
    height=300
)
st.plotly_chart(fig_fred, use_container_width=True)

# Returns distribution
st.subheader("📊 Returns Distribution")

col1, col2 = st.columns(2)

with col1:
    fig_hist = go.Figure()
    fig_hist.add_trace(go.Histogram(
        x=backtest_results['strategy_returns'] * 100,
        nbinsx=50,
        name='Strategy Returns',
        marker_color='#00D9FF'
    ))
    fig_hist.update_layout(
        title="Strategy Daily Returns Distribution",
        xaxis_title="Daily Return (%)",
        yaxis_title="Frequency",
        height=350
    )
    st.plotly_chart(fig_hist, use_container_width=True)

with col2:
    fig_scatter = go.Figure()
    fig_scatter.add_trace(go.Scatter(
        x=backtest_results['fred_zscore'],
        y=backtest_results['returns'] * 100,
        mode='markers',
        marker=dict(
            size=5,
            color=backtest_results['returns'] * 100,
            colorscale='RdYlGn',
            showscale=True,
            colorbar=dict(title="Return (%)")
        ),
        text=backtest_results['date'],
        hovertemplate='<b>%{text}</b><br>FRED Z-Score: %{x:.2f}<br>Return: %{y:.2f}%'
    ))
    fig_scatter.update_layout(
        title="FRED Z-Score vs Stock Returns",
        xaxis_title="FRED Z-Score",
        yaxis_title="Daily Return (%)",
        height=350
    )
    st.plotly_chart(fig_scatter, use_container_width=True)

# Data table
st.subheader("📋 Recent Trading Activity")

display_cols = ['date', 'close', 'ma', 'signal', 'fred_zscore', 'strategy_returns']
st.dataframe(
    backtest_results[display_cols].tail(20).assign(strategy_returns=lambda x: x['strategy_returns'] * 100),
    use_container_width=True,
    column_config={
        'date': st.column_config.DateColumn(format='YYYY-MM-DD'),
        'close': st.column_config.NumberColumn(format='$%.2f'),
        'ma': st.column_config.NumberColumn(format='$%.2f'),
        'signal': st.column_config.NumberColumn(format='%.0f'),
        'fred_zscore': st.column_config.NumberColumn(format='%.2f'),
        'strategy_returns': st.column_config.NumberColumn(format='%.2f%%')
    }
)

# Footer
st.markdown("---")
st.caption("🔬 MFAMS Delta1 | Data Pipeline: FRED API + Alpha Vantage | Last Updated: March 2026")
