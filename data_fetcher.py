"""
Data Fetching Module
Fetch data from FRED and Alpha Vantage APIs and store in SQLite database
"""

import requests
import pandas as pd
import sqlite3
from datetime import datetime
import streamlit as st


class DataFetcher:
    """Handles fetching data from external APIs"""
    
    @staticmethod
    def fetch_fred_series(api_key: str, series_id: str, start_date: str = "1900-01-01", end_date: str = "2099-12-31"):
        """
        Fetch FRED data for a specific series
        
        Args:
            api_key: FRED API key
            series_id: FRED series ID (e.g., 'UNRATE', 'CPIAUCSL')
            start_date: Start date (YYYY-MM-DD)
            end_date: End date (YYYY-MM-DD)
        
        Returns:
            DataFrame with columns [date, value] or None if failed
        """
        try:
            url = f"https://api.stlouisfed.org/fred/series/observations"
            params = {
                'series_id': series_id,
                'api_key': api_key,
                'from_date': start_date,
                'to_date': end_date,
                'file_type': 'json'
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            if 'error_code' in data:
                st.error(f"❌ FRED API Error: {data.get('error_message', 'Unknown error')}")
                return None
            
            if 'observations' not in data:
                st.error(f"❌ No data returned for {series_id}")
                return None
            
            # Convert to DataFrame
            observations = []
            for obs in data['observations']:
                obs_dict = {
                    'date': obs['date'],
                    'value': None if obs['value'] == '.' else float(obs['value'])
                }
                observations.append(obs_dict)
            
            df = pd.DataFrame(observations)
            df['date'] = pd.to_datetime(df['date'])
            
            st.success(f"✅ Fetched {len(df)} observations for {series_id}")
            return df
        
        except Exception as e:
            st.error(f"❌ Error fetching FRED {series_id}: {str(e)}")
            return None
    
    @staticmethod
    def fetch_alpha_vantage_stock(api_key: str, symbol: str):
        """
        Fetch stock data from Alpha Vantage (TIME_SERIES_DAILY, free tier = ~100 days)
        
        Args:
            api_key: Alpha Vantage API key
            symbol: Stock symbol (e.g., 'AAPL', 'GDX')
        
        Returns:
            DataFrame with columns [date, open, high, low, close, volume] or None if failed
        """
        try:
            url = "https://www.alphavantage.co/query"
            params = {
                'function': 'TIME_SERIES_DAILY',
                'symbol': symbol,
                'apikey': api_key
            }
            
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            
            data = response.json()
            
            # Check for errors
            if 'Error Message' in data:
                st.error(f"❌ API Error: {data['Error Message']}")
                return None
            
            if 'Note' in data:
                st.error(f"❌ API Rate Limit: {data['Note']}")
                return None
            
            if 'Information' in data:
                st.error(f"❌ API Info: {data['Information']}")
                return None
            
            if 'Time Series (Daily)' not in data:
                st.error(f"❌ No time series data returned for {symbol}")
                return None
            
            # Convert to DataFrame
            time_series = data['Time Series (Daily)']
            rows = []
            
            for date_str, day_data in time_series.items():
                row = {
                    'date': date_str,
                    'open': float(day_data['1. open']),
                    'high': float(day_data['2. high']),
                    'low': float(day_data['3. low']),
                    'close': float(day_data['4. close']),
                    'volume': int(day_data['5. volume'])
                }
                rows.append(row)
            
            df = pd.DataFrame(rows)
            df['date'] = pd.to_datetime(df['date'])
            df = df.sort_values('date').reset_index(drop=True)
            
            st.success(f"✅ Fetched {len(df)} days for {symbol}")
            return df
        
        except Exception as e:
            st.error(f"❌ Error fetching {symbol}: {str(e)}")
            return None


class DatabaseManager:
    """Manage SQLite database operations"""
    
    @staticmethod
    def create_fred_table(db_path: str, series_id: str):
        """Create FRED data table if it doesn't exist"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            table_name = f"fred_{series_id}"
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    value REAL,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"❌ Database error: {str(e)}")
            return False
    
    @staticmethod
    def create_stock_table(db_path: str, symbol: str):
        """Create stock data table if it doesn't exist"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            table_name = f"stock_{symbol}"
            cursor.execute(f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT UNIQUE NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            st.error(f"❌ Database error: {str(e)}")
            return False
    
    @staticmethod
    def insert_fred_data(db_path: str, series_id: str, df: pd.DataFrame):
        """Insert FRED data into database"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            table_name = f"fred_{series_id}"
            count = 0
            
            for _, row in df.iterrows():
                if pd.isna(row['value']):
                    continue
                
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {table_name} (date, value)
                    VALUES (?, ?)
                """, (row['date'].strftime('%Y-%m-%d'), row['value']))
                count += 1
            
            conn.commit()
            conn.close()
            
            return count
        except Exception as e:
            st.error(f"❌ Error inserting data: {str(e)}")
            return 0
    
    @staticmethod
    def insert_stock_data(db_path: str, symbol: str, df: pd.DataFrame):
        """Insert stock data into database"""
        try:
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            table_name = f"stock_{symbol}"
            count = 0
            
            for _, row in df.iterrows():
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {table_name} 
                    (date, open, high, low, close, volume)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    row['date'].strftime('%Y-%m-%d'),
                    row['open'],
                    row['high'],
                    row['low'],
                    row['close'],
                    row['volume']
                ))
                count += 1
            
            conn.commit()
            conn.close()
            
            return count
        except Exception as e:
            st.error(f"❌ Error inserting data: {str(e)}")
            return 0
