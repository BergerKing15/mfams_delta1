#!/usr/bin/env python3
"""
MFAMS Delta1 Backtesting Dashboard
Interactive Streamlit app for testing trading strategies with macro + equity data
"""

import sys
from pathlib import Path

# Paths are anchored to the repo root rather than the working directory, so the
# app behaves the same however it is launched.
APP_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = APP_DIR.parent
DB_PATH = PROJECT_ROOT / "data" / "financial_data.db"
CONFIG_PATH = PROJECT_ROOT / "config.json"

# `streamlit run` happens to put the script's directory on sys.path, but nothing
# else does - not AppTest, not `python app/dashboard.py`. Make the sibling
# imports work regardless.
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

import streamlit as st
import pandas as pd
import numpy as np
import sqlite3
from datetime import datetime, timedelta
import plotly.graph_objects as go
import plotly.express as px
from scipy import stats
from strategies import STRATEGIES
from optimize import PARAM_GRIDS, sweep, walk_forward, compare_symbols

# ============================================================================
# DATA LOADING
# ============================================================================

@st.cache_resource
def get_db_connection():
    """Get SQLite connection

    cache_resource shares one connection across sessions and script runs, which
    may land on different threads, so check_same_thread must be off.
    """
    if not DB_PATH.exists():
        st.error(f"❌ Database not found at {DB_PATH}. Run the C++ pipeline first!")
        st.stop()
    return sqlite3.connect(str(DB_PATH), check_same_thread=False)

@st.cache_data
def load_fred_data(series_id):
    """Load FRED economic data"""
    conn = get_db_connection()
    table_name = f"fred_{series_id}"
    try:
        df = pd.read_sql_query(f"SELECT * FROM {table_name} ORDER BY date", conn)
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        st.warning(f"⚠️ Could not load {series_id}: {e}")
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
    except Exception as e:
        st.warning(f"⚠️ Could not load {symbol}: {e}")
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

@st.cache_data
def get_latest_fed_funds():
    """Latest FEDFUNDS value, as a suggested risk-free rate. None if absent."""
    conn = get_db_connection()
    try:
        row = conn.execute("SELECT value FROM fred_FEDFUNDS ORDER BY date DESC LIMIT 1").fetchone()
        return row[0] if row else None
    except sqlite3.Error:
        return None

def run_strategy(strategy_class, stock_df, fred_df, params):
    """Execute a strategy and return results"""
    try:
        params = dict(params)
        risk_free_rate = params.pop('risk_free_rate', 0.0)
        strategy = strategy_class(stock_df, fred_df, **params)
        backtest_results = strategy.calculate_signals()
        
        # Check if strategy returned None (not enough data)
        if backtest_results is None:
            st.error(f"❌ Not enough data for {strategy_class.name}. Adjust parameters to use less data (e.g., reduce MA period).")
            return None, {}
        
        metrics = strategy.calculate_metrics(backtest_results, risk_free_rate=risk_free_rate)
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

strategy_params['transaction_cost_bps'] = st.sidebar.slider(
    "Transaction Cost (bps)",
    min_value=0.0, max_value=50.0, value=5.0, step=0.5,
    help="Cost charged per unit of exposure traded, in basis points. "
         "Set to 0 for frictionless results; real trading is never frictionless."
)

_fed_funds = get_latest_fed_funds()
strategy_params['risk_free_rate'] = st.sidebar.slider(
    "Risk-Free Rate (annual %)",
    min_value=0.0, max_value=10.0, value=0.0, step=0.25,
    help="Sharpe is computed on returns in excess of this rate. At 0 it measures "
         "raw volatility-adjusted return, which flatters a strategy whenever cash "
         "was paying something."
         + (f" Latest FEDFUNDS in your database: {_fed_funds:.2f}%." if _fed_funds is not None else "")
)

if strategy_name == 'Z-Score (Macro Signal)':
    strategy_params['ma_period'] = st.sidebar.slider(
        "Moving Average Period",
        min_value=5, max_value=100, value=20, step=5
    )
    strategy_params['fred_lag_days'] = st.sidebar.slider(
        "FRED Release Lag (days)",
        min_value=0, max_value=90, value=30, step=5,
        help="FRED data is published weeks after the period it describes. This "
             "delays the series so signals only use data that was public at the "
             "time. Setting it to 0 reintroduces lookahead bias."
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

# The free Alpha Vantage tier returns ~100 trading days. Sharpe, win rate and
# drawdown are all noisy on a sample that short, so say so rather than letting
# the numbers imply more confidence than they carry.
if len(stock_data) < 250:
    st.warning(
        f"⚠️ Only {len(stock_data)} trading days of {selected_stock} data "
        f"(~{len(stock_data) / 21:.0f} months). Metrics below are indicative, not "
        "predictive: Sharpe and win rate are unstable on samples this short, and a "
        "single trade can dominate the result. Treat these as a way to compare "
        "parameter choices, not as evidence a strategy works."
    )

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
col1, col2, col3, col4, col5 = st.columns(5)

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
        delta=f"{int(metrics.get('num_trades', 0))} trades",
        help="Share of completed trades that were profitable. A trade is one "
             f"unbroken stretch of exposure. Profitable days: "
             f"{metrics.get('win_rate_days', 0):.1f}%"
    )

with col4:
    st.metric(
        "Max Drawdown",
        f"{metrics.get('max_drawdown', 0):.2f}%",
        delta="Peak-to-trough decline"
    )

with col5:
    st.metric(
        "Transaction Costs",
        f"{metrics.get('total_costs', 0):.2f}%",
        delta="Drag on returns",
        delta_color="inverse",
        help="Total cost of trading over the period, already deducted from Total Return."
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
# VALIDATION: PARAMETER SWEEP AND WALK-FORWARD
# ============================================================================

st.markdown("---")
st.subheader("🔬 Validation: Parameter Sweep & Walk-Forward")

st.markdown(
    "Tuning parameters until the equity curve looks good is how a backtest lies to you. "
    "This compares the **best in-sample result** (what you get by hunting for the best "
    "setting and quoting it) against **walk-forward** performance, where parameters are "
    "chosen using only past data and scored on the period that follows. The gap between "
    "them is the overfitting premium."
)

if strategy_name not in PARAM_GRIDS:
    st.info(f"No parameter grid defined for {strategy_name}.")
elif st.button("Run validation", help="Sweeps the grid, then runs walk-forward folds"):
    with st.spinner("Sweeping parameters and running walk-forward folds..."):
        cost_bps = strategy_params.get('transaction_cost_bps', 5.0)
        rf = strategy_params.get('risk_free_rate', 0.0)

        sweep_table = sweep(strategy_name, stock_data, fred_data, cost_bps, rf)
        folds = walk_forward(strategy_name, stock_data, fred_data,
                             cost_bps=cost_bps, risk_free_rate=rf)

    if sweep_table.empty:
        st.warning("No parameter combination produced a result on this data.")
    else:
        grid_cols = [c for c in PARAM_GRIDS[strategy_name] if c in sweep_table.columns]
        show = grid_cols + ['sharpe_ratio', 'total_return', 'max_drawdown', 'num_trades']

        st.markdown(f"**In-sample sweep** — {len(sweep_table)} combinations, best first")
        st.dataframe(sweep_table[show].head(10), use_container_width=True)

        if folds.empty:
            st.warning(
                "Not enough data for walk-forward folds. With ~100 trading days there is "
                "barely enough history to split; this is a limitation of the free data "
                "tier, not of the method."
            )
        else:
            st.markdown("**Walk-forward** — parameters chosen on past data only")
            st.dataframe(folds, use_container_width=True)

            best_is = sweep_table['sharpe_ratio'].iloc[0]
            mean_oos = folds['out_of_sample_sharpe'].mean()
            premium = best_is - mean_oos

            c1, c2, c3 = st.columns(3)
            c1.metric("Best in-sample Sharpe", f"{best_is:.2f}")
            c2.metric("Mean out-of-sample Sharpe", f"{mean_oos:.2f}")
            c3.metric("Overfitting premium", f"{premium:.2f}", delta_color="inverse",
                      help="In-sample minus out-of-sample. Large means the in-sample "
                           "result came from fitting the sample, not from an edge.")

            if premium > 1.0:
                st.error(
                    f"The in-sample Sharpe of {best_is:.2f} does not survive out of sample "
                    f"({mean_oos:.2f}). Treat the tuned parameters as fitted to this "
                    "particular sample."
                )
            else:
                st.success("In-sample and out-of-sample results are close on this data.")

    # ---- cross-symbol check -------------------------------------------------
    st.markdown("**Same parameters, every symbol** — does the result generalise?")
    with st.spinner("Running across all symbols..."):
        best_params = {k: sweep_table[k].iloc[0] for k in grid_cols} if not sweep_table.empty else {}
        cross = compare_symbols(strategy_name, best_params, get_available_symbols(),
                                load_stock_data, fred_data,
                                cost_bps=strategy_params.get('transaction_cost_bps', 5.0),
                                risk_free_rate=strategy_params.get('risk_free_rate', 0.0))
    if not cross.empty:
        st.dataframe(cross, use_container_width=True)
        st.caption(
            "Agreement across these symbols is weaker evidence than it looks: the default "
            "universe is mostly gold miners, whose daily returns correlate about 0.77 with "
            "one another over this window. Eight symbols at that correlation carry roughly "
            "two independent bets, not eight."
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
            
            # Generate your signals...
            merged['signal'] = 0  # Your logic here
            
            # Returns, position lag and transaction costs are handled centrally.
            # Always finish with this instead of computing strategy_returns by hand.
            merged = self.apply_returns(merged)
            
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

# ============================================================================
# ADD CUSTOM DATA
# ============================================================================

st.markdown("---")
st.subheader("📥 Add Custom Stock or FRED Data")

with st.expander("🔧 Fetch Additional Data"):
    st.markdown("""
    Add more stocks or FRED economic indicators to your database:
    - **Alpha Vantage** provides ~100 days of daily stock data (free tier)
    - **FRED** provides historical economic data back to 1948+
    
    Enter a symbol/series ID and fetch the latest data.
    """)
    
    # Get API keys from config
    try:
        import json
        with open(CONFIG_PATH) as f:
            config = json.load(f)
        fred_api_key = config['fredApi']['apiKey']
        alpha_key = config['alphaVantage']['apiKey']
    except FileNotFoundError:
        fred_api_key = None
        alpha_key = None
        st.warning("⚠️ config.json not found. Copy config.example.json and add your API keys.")
    except (KeyError, ValueError) as e:
        fred_api_key = None
        alpha_key = None
        st.warning(f"⚠️ Could not read API keys from config.json: {e}")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("📈 Add Stock Data")
        stock_symbol = st.text_input(
            "Stock Symbol",
            placeholder="e.g., AAPL, GDX, NEM",
            key="add_stock_symbol",
            help="Enter stock ticker symbol"
        ).upper()
        
        if st.button("📊 Fetch Stock Data", key="fetch_stock_btn"):
            if not stock_symbol:
                st.error("❌ Please enter a stock symbol")
            elif not alpha_key:
                st.error("❌ Alpha Vantage API key not configured")
            else:
                with st.spinner(f"Fetching {stock_symbol} data..."):
                    from data_fetcher import DataFetcher, DatabaseManager
                    
                    # Fetch data
                    df = DataFetcher.fetch_alpha_vantage_stock(alpha_key, stock_symbol)
                    
                    if df is not None and not df.empty:
                        # Create table and insert data
                        if DatabaseManager.create_stock_table(str(DB_PATH), stock_symbol):
                            rows_inserted = DatabaseManager.insert_stock_data(str(DB_PATH), stock_symbol, df)
                            st.success(f"✅ Added {stock_symbol}: {rows_inserted} records stored")
                            
                            # Clear cache to refresh symbol list
                            st.cache_data.clear()
                            st.rerun()
    
    with col2:
        st.subheader("📊 Add FRED Series")
        fred_series = st.text_input(
            "FRED Series ID",
            placeholder="e.g., UNRATE, CPIAUCSL, FEDFUNDS",
            key="add_fred_series",
            help="Enter FRED series ID (https://fred.stlouisfed.org/)"
        ).upper()
        
        if st.button("📈 Fetch FRED Data", key="fetch_fred_btn"):
            if not fred_series:
                st.error("❌ Please enter a FRED series ID")
            elif not fred_api_key:
                st.error("❌ FRED API key not configured")
            else:
                with st.spinner(f"Fetching {fred_series} data..."):
                    from data_fetcher import DataFetcher, DatabaseManager
                    
                    # Fetch data
                    df = DataFetcher.fetch_fred_series(fred_api_key, fred_series)
                    
                    if df is not None and not df.empty:
                        # Create table and insert data
                        if DatabaseManager.create_fred_table(str(DB_PATH), fred_series):
                            rows_inserted = DatabaseManager.insert_fred_data(str(DB_PATH), fred_series, df)
                            st.success(f"✅ Added {fred_series}: {rows_inserted} records stored")
                            
                            # Clear cache to refresh series list
                            st.cache_data.clear()
                            st.rerun()

# Footer
st.markdown("---")
st.caption("🔬 MFAMS Delta1 | Data Pipeline: FRED API + Alpha Vantage | Last Updated: March 2026")
