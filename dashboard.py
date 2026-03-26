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
from strategies import STRATEGIES

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
# STRATEGY EXECUTION
# ============================================================================

def run_strategy(strategy_class, stock_df, fred_df, params):
    """Execute a strategy and return results"""
    try:
        strategy = strategy_class(stock_df, fred_df, **params)
        backtest_results = strategy.calculate_signals()
        
        # Check if strategy returned None (not enough data)
        if backtest_results is None:
            st.error(f"❌ Not enough data for {strategy_class.name}. Adjust parameters to use less data (e.g., reduce MA period).")
            return None, {}
        
        metrics = strategy.calculate_metrics(backtest_results)
        return backtest_results, metrics
    except Exception as e:
        st.error(f"❌ {strategy_class.name} strategy error:\n{str(e)}\n\nTip: Try adjusting parameters or check your data.")
        return None, {}

# ============================================================================
# STREAMLIT UI
# ============================================================================

st.set_page_config(page_title="MFAMS Delta1 Backtest", layout="wide")

st.title("📊 MFAMS Delta1 Backtesting Dashboard")
st.markdown("**Interactive strategy testing with macro + equity data**")

# Sidebar controls
st.sidebar.header("⚙️ Strategy Configuration")

# Data selection
stock_options = get_available_symbols()
fred_options = get_available_fred_series()

selected_stock = st.sidebar.selectbox("📈 Stock Symbol", stock_options, index=0)
selected_fred = st.sidebar.selectbox("📉 FRED Indicator", fred_options, index=0)

# Strategy selection
st.sidebar.subheader("Strategy Type")
strategy_name = st.sidebar.selectbox(
    "Select Strategy",
    list(STRATEGIES.keys()),
    help="Choose from pre-built strategies or upload custom code"
)
strategy_class = STRATEGIES[strategy_name]

# Dynamic parameters based on strategy
st.sidebar.subheader("Strategy Parameters")
strategy_params = {'position_size': st.sidebar.slider(
    "Position Size",
    min_value=0.1, max_value=3.0, value=1.0, step=0.1,
    help="Position multiplier (1.0 = full position, 2.0 = 2x leverage)"
)}

if strategy_name == 'Z-Score (Macro Signal)':
    strategy_params['ma_period'] = st.sidebar.slider(
        "Moving Average Period",
        min_value=5, max_value=100, value=20, step=5
    )
    strategy_params['zscore_threshold'] = st.sidebar.slider(
        "Z-Score Threshold",
        min_value=0.5, max_value=5.0, value=2.0, step=0.5
    )

elif strategy_name == 'MA Crossover':
    strategy_params['fast_ma'] = st.sidebar.slider(
        "Fast MA Period",
        min_value=5, max_value=50, value=20, step=5
    )
    strategy_params['slow_ma'] = st.sidebar.slider(
        "Slow MA Period",
        min_value=20, max_value=100, value=50, step=10
    )

elif strategy_name == 'RSI (Overbought/Oversold)':
    strategy_params['rsi_period'] = st.sidebar.slider(
        "RSI Period",
        min_value=5, max_value=50, value=14, step=1
    )
    strategy_params['oversold'] = st.sidebar.slider(
        "Oversold Threshold",
        min_value=5, max_value=50, value=30, step=5
    )
    strategy_params['overbought'] = st.sidebar.slider(
        "Overbought Threshold",
        min_value=50, max_value=95, value=70, step=5
    )

elif strategy_name == 'Mean Reversion':
    strategy_params['ma_period'] = st.sidebar.slider(
        "Moving Average Period",
        min_value=5, max_value=100, value=20, step=5
    )
    strategy_params['std_dev_threshold'] = st.sidebar.slider(
        "Standard Deviation Threshold",
        min_value=0.5, max_value=5.0, value=2.0, step=0.5
    )

# Load data
stock_data = load_stock_data(selected_stock)
fred_data = load_fred_data(selected_fred)

if stock_data.empty or fred_data.empty:
    st.error("❌ No data available. Check database.")
    st.stop()

# Run backtest
backtest_results, metrics = run_strategy(strategy_class, stock_data, fred_data, strategy_params)

if backtest_results is None:
    st.error("❌ Strategy execution failed. Check parameters and data.")
    st.stop()

# Add cumulative returns columns for visualization
if 'cumulative_returns' not in backtest_results.columns:
    backtest_results['cumulative_returns'] = (1 + backtest_results['strategy_returns']).cumprod()
if 'buy_hold' not in backtest_results.columns:
    backtest_results['buy_hold'] = (1 + backtest_results['returns']).cumprod()

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

# Moving average (if it exists)
if 'ma' in backtest_results.columns:
    ma_label = f"MA({strategy_params.get('ma_period', 'N/A')})"
    fig_signals.add_trace(go.Scatter(
        x=backtest_results['date'],
        y=backtest_results['ma'],
        mode='lines',
        name=ma_label,
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
    # Show FRED Z-Score scatter only if it exists (Z-Score strategy)
    if 'fred_zscore' in backtest_results.columns:
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
    else:
        st.info(f"📊 FRED analysis only available for Z-Score strategy")

# Data table
st.subheader("📋 Recent Trading Activity")

# Build column list dynamically based on available columns
display_cols = ['date', 'close', 'signal', 'strategy_returns']
if 'ma' in backtest_results.columns:
    display_cols.insert(2, 'ma')
if 'fred_zscore' in backtest_results.columns:
    display_cols.insert(3, 'fred_zscore')

column_config = {
    'date': st.column_config.DateColumn(format='YYYY-MM-DD'),
    'close': st.column_config.NumberColumn(format='$%.2f'),
    'signal': st.column_config.NumberColumn(format='%.0f'),
    'strategy_returns': st.column_config.NumberColumn(format='%.2f%%')
}
if 'ma' in backtest_results.columns:
    column_config['ma'] = st.column_config.NumberColumn(format='$%.2f')
if 'fred_zscore' in backtest_results.columns:
    column_config['fred_zscore'] = st.column_config.NumberColumn(format='%.2f')

st.dataframe(
    backtest_results[display_cols].tail(20).assign(strategy_returns=lambda x: x['strategy_returns'] * 100),
    use_container_width=True,
    column_config=column_config
)

# ============================================================================
# CUSTOM STRATEGY UPLOAD
# ============================================================================

st.markdown("---")
st.subheader("🚀 Upload Custom Strategy (Advanced)")

with st.expander("📖 How to Create a Custom Strategy"):
    st.markdown("""
    Create a Python file with your custom strategy class:
    
    ```python
    from strategies import Strategy
    import pandas as pd
    import numpy as np
    
    class MyStrategy(Strategy):
        name = "My Custom Strategy"
        
        def calculate_signals(self):
            # Your implementation here
            # Must return DataFrame with columns:
            # - date, close, returns, signal, strategy_returns
            
            merged = self.stock_df.copy()
            
            # Access parameters: self.params['position_size'], etc.
            position_size = self.params.get('position_size', 1.0)
            
            # Generate your signals...
            merged['signal'] = 0  # Your logic here
            
            # Calculate returns
            merged['returns'] = merged['close'].pct_change()
            merged['strategy_returns'] = merged['signal'].shift(1) * merged['returns'] * position_size
            merged['strategy_returns'] = merged['strategy_returns'].fillna(0)
            
            return merged
    ```
    
    Save as `custom_strategy.py` and upload below.
    """)

uploaded_file = st.file_uploader("Upload custom strategy (.py)", type=['py'])

if uploaded_file is not None:
    try:
        # Read and execute custom strategy
        strategy_code = uploaded_file.read().decode()
        
        # Create namespace for execution
        namespace = {'Strategy': Strategy, 'pd': pd, 'np': np}
        exec(strategy_code, namespace)
        
        # Find custom strategy class
        custom_class = None
        for name, obj in namespace.items():
            if isinstance(obj, type) and issubclass(obj, Strategy) and obj != Strategy:
                custom_class = obj
                break
        
        if custom_class:
            st.success(f"✅ Loaded strategy: {custom_class.name}")
            
            # Allow user to test custom strategy
            if st.button("📊 Test Custom Strategy"):
                custom_params = {'position_size': st.slider(
                    "Custom Position Size",
                    min_value=0.1, max_value=3.0, value=1.0, step=0.1,
                    key='custom_pos_size'
                )}
                
                custom_results, custom_metrics = run_strategy(custom_class, stock_data, fred_data, custom_params)
                
                if custom_results is not None:
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Return", f"{custom_metrics.get('total_return', 0):.2f}%")
                    with col2:
                        st.metric("Sharpe Ratio", f"{custom_metrics.get('sharpe_ratio', 0):.2f}")
                    with col3:
                        st.metric("Max Drawdown", f"{custom_metrics.get('max_drawdown', 0):.2f}%")
                    
                    st.write(custom_results[['date', 'close', 'signal', 'strategy_returns']].tail(10))
        else:
            st.error("❌ No Strategy class found in uploaded file")
    except Exception as e:
        st.error(f"❌ Error loading strategy: {str(e)}")

# Footer
st.markdown("---")
st.caption("🔬 MFAMS Delta1 | Data Pipeline: FRED API + Alpha Vantage | Last Updated: March 2026")
