import os
import logging
import pandas as pd
from datetime import datetime, timedelta
import baostock as bs
import akshare as ak

# 清除可能导致AKShare/网络请求失败的代理环境变量
os.environ.pop("HTTP_PROXY", None)
os.environ.pop("HTTPS_PROXY", None)
os.environ.pop("http_proxy", None)
os.environ.pop("https_proxy", None)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class DataEngine:
    """A股量化双数据引擎 (AKShare + BaoStock)"""

    @staticmethod
    def _fetch_from_baostock(symbol: str, start_date: str, end_date: str, adjust: str = "2") -> pd.DataFrame:
        """
        使用 BaoStock 获取历史K线
        adjust: "3"-不复权, "1"-后复权, "2"-前复权
        """
        code = f"sh.{symbol}" if symbol.startswith("6") or symbol.startswith("9") else f"sz.{symbol}"
        if symbol.startswith("688"):
            code = f"sh.{symbol}"
        elif symbol.startswith("300") or symbol.startswith("301"):
            code = f"sz.{symbol}"

        lg = bs.login()
        if lg.error_code != '0':
            logging.error(f"BaoStock 登录失败: {lg.error_msg}")
            return pd.DataFrame()

        # 格式化日期格式为 YYYY-MM-DD
        s_date = f"{start_date[:4]}-{start_date[4:6]}-{start_date[6:]}" if len(start_date) == 8 else start_date
        e_date = f"{end_date[:4]}-{end_date[4:6]}-{end_date[6:]}" if len(end_date) == 8 else end_date

        rs = bs.query_history_k_data_plus(
            code,
            "date,open,high,low,close,volume,amount,pctChg,turn",
            start_date=s_date, end_date=e_date,
            frequency="d", adjustflag=adjust
        )

        data_list = []
        while (rs.error_code == '0') & rs.next():
            data_list.append(rs.get_row_data())
        bs.logout()

        if not data_list:
            return pd.DataFrame()

        df = pd.DataFrame(data_list, columns=rs.fields)
        df = df.rename(columns={
            "date": "Date", "open": "Open", "high": "High", "low": "Low",
            "close": "Close", "volume": "Volume", "amount": "Amount",
            "pctChg": "PctChg", "turn": "Turnover"
        })

        # 类型转换
        numeric_cols = ["Open", "High", "Low", "Close", "Volume", "Amount", "PctChg", "Turnover"]
        for col in numeric_cols:
            df[col] = pd.to_numeric(df[col], errors='coerce')

        df['Date'] = pd.to_datetime(df['Date'])
        return df.sort_values('Date').reset_index(drop=True)

    @staticmethod
    def get_stock_daily(symbol: str, start_date: str = None, end_date: str = None, adjust: str = "qfq") -> pd.DataFrame:
        """
        获取单只股票日线 (优先使用 BaoStock 稳定传输，备选 AKShare)
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y%m%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365*2)).strftime("%Y%m%d")

        # 1. 尝试 BaoStock
        try:
            adjust_flag = "2" if adjust == "qfq" else ("1" if adjust == "hfq" else "3")
            df = DataEngine._fetch_from_baostock(symbol, start_date, end_date, adjust=adjust_flag)
            if not df.empty and len(df) > 10:
                logging.info(f"成功使用 BaoStock 获取 [{symbol}] K线数据 {len(df)} 条。")
                return df
        except Exception as e:
            logging.warning(f"BaoStock 获取数据失败: {e}，尝试切换至 AKShare...")

        # 2. 备选 AKShare
        try:
            df = ak.stock_zh_a_hist(symbol=symbol, period="daily", start_date=start_date, end_date=end_date, adjust=adjust)
            if not df.empty:
                df = df.rename(columns={
                    "日期": "Date", "开盘": "Open", "收盘": "Close",
                    "最高": "High", "最低": "Low", "成交量": "Volume",
                    "成交额": "Amount", "涨跌幅": "PctChg", "换手率": "Turnover"
                })
                df['Date'] = pd.to_datetime(df['Date'])
                logging.info(f"成功使用 AKShare 获取 [{symbol}] K线数据 {len(df)} 条。")
                return df.sort_values('Date').reset_index(drop=True)
        except Exception as e:
            logging.error(f"AKShare 获取股票 [{symbol}] 数据失败: {e}")

        return pd.DataFrame()

if __name__ == "__main__":
    df = DataEngine.get_stock_daily("600519")
    print(df.tail())
