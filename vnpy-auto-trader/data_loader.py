"""
A股数据下载引擎 - 基于 BaoStock 下载历史 K 线数据供 VeighNa 回测使用
"""
import os
import sys
import baostock as bs
import pandas as pd
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

# 清除代理（防止网络问题）
for key in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"]:
    os.environ.pop(key, None)


class AShareDataLoader:
    """A 股历史数据下载器（BaoStock 数据源）"""

    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        os.makedirs(data_dir, exist_ok=True)

    def download_stock_daily(
        self,
        symbol: str,
        start_date: str = None,
        end_date: str = None,
    ) -> pd.DataFrame:
        """
        下载单只股票的日线数据 (前复权)
        :param symbol: 6位股票代码 (如 600519)
        :param start_date: 开始日期 YYYY-MM-DD
        :param end_date: 结束日期 YYYY-MM-DD
        """
        if not end_date:
            end_date = datetime.now().strftime("%Y-%m-%d")
        if not start_date:
            start_date = (datetime.now() - timedelta(days=365 * 3)).strftime("%Y-%m-%d")

        # 判断交易所
        if symbol.startswith(("6", "9")):
            bs_code = f"sh.{symbol}"
        else:
            bs_code = f"sz.{symbol}"

        lg = bs.login()
        if lg.error_code != '0':
            logger.error(f"BaoStock 登录失败: {lg.error_msg}")
            return pd.DataFrame()

        logger.info(f"正在下载 [{symbol}] 日线数据 ({start_date} ~ {end_date})...")

        rs = bs.query_history_k_data_plus(
            bs_code,
            "date,open,high,low,close,volume,amount,pctChg,turn",
            start_date=start_date,
            end_date=end_date,
            frequency="d",
            adjustflag="2",  # 前复权
        )

        rows = []
        while rs.error_code == '0' and rs.next():
            rows.append(rs.get_row_data())
        bs.logout()

        if not rows:
            logger.warning(f"[{symbol}] 无数据返回")
            return pd.DataFrame()

        df = pd.DataFrame(rows, columns=rs.fields)

        # 类型转换
        df["date"] = pd.to_datetime(df["date"])
        for col in ["open", "high", "low", "close", "volume", "amount", "pctChg", "turn"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")

        # 过滤无效行（停牌日等）
        df = df[df["volume"] > 0].reset_index(drop=True)

        # 保存到本地 CSV
        csv_path = os.path.join(self.data_dir, f"{symbol}_daily.csv")
        df.to_csv(csv_path, index=False)
        logger.info(f"[{symbol}] 保存 {len(df)} 条数据 -> {csv_path}")

        return df

    def download_stock_pool(self, stock_pool: dict, start_date: str = None) -> dict:
        """批量下载股票池的历史数据"""
        results = {}
        total = len(stock_pool)
        for i, (symbol, name) in enumerate(stock_pool.items(), 1):
            logger.info(f"[{i}/{total}] 下载 {name} ({symbol})...")
            df = self.download_stock_daily(symbol, start_date=start_date)
            if not df.empty:
                results[symbol] = df
        logger.info(f"批量下载完成，成功 {len(results)}/{total} 只")
        return results

    def load_local_data(self, symbol: str) -> pd.DataFrame:
        """从本地 CSV 加载数据"""
        csv_path = os.path.join(self.data_dir, f"{symbol}_daily.csv")
        if not os.path.exists(csv_path):
            logger.warning(f"本地无 [{symbol}] 数据，尝试下载...")
            return self.download_stock_daily(symbol)
        df = pd.read_csv(csv_path)
        df["date"] = pd.to_datetime(df["date"])
        return df


if __name__ == "__main__":
    from config import STOCK_POOL

    loader = AShareDataLoader()
    loader.download_stock_pool(STOCK_POOL, start_date="2023-01-01")
    print("\n✅ 全部数据下载完成！")
