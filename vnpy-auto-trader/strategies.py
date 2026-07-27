"""
A股量化交易策略库 - 包含多种经典量化策略的信号生成与回测逻辑
可独立运行回测，也可输出信号对接 VeighNa 实盘引擎
"""
import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Literal
import logging

logger = logging.getLogger(__name__)


# ============================================================
# 技术指标计算
# ============================================================
class Indicators:
    """向量化技术指标计算器"""

    @staticmethod
    def sma(series: pd.Series, window: int) -> pd.Series:
        return series.rolling(window=window).mean()

    @staticmethod
    def ema(series: pd.Series, span: int) -> pd.Series:
        return series.ewm(span=span, adjust=False).mean()

    @staticmethod
    def macd(close: pd.Series, fast=12, slow=26, signal=9):
        ema_fast = close.ewm(span=fast, adjust=False).mean()
        ema_slow = close.ewm(span=slow, adjust=False).mean()
        dif = ema_fast - ema_slow
        dea = dif.ewm(span=signal, adjust=False).mean()
        hist = 2 * (dif - dea)
        return dif, dea, hist

    @staticmethod
    def rsi(close: pd.Series, period=14) -> pd.Series:
        delta = close.diff()
        gain = delta.where(delta > 0, 0).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        return 100 - (100 / (1 + rs))

    @staticmethod
    def bollinger(close: pd.Series, window=20, num_std=2):
        mid = close.rolling(window).mean()
        std = close.rolling(window).std()
        upper = mid + num_std * std
        lower = mid - num_std * std
        return upper, mid, lower

    @staticmethod
    def atr(high: pd.Series, low: pd.Series, close: pd.Series, period=14) -> pd.Series:
        tr1 = high - low
        tr2 = (high - close.shift(1)).abs()
        tr3 = (low - close.shift(1)).abs()
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        return tr.rolling(window=period).mean()


# ============================================================
# 交易信号 & 回测数据结构
# ============================================================
@dataclass
class TradeSignal:
    date: str
    symbol: str
    action: Literal["BUY", "SELL", "HOLD"]
    price: float
    reason: str
    confidence: float = 0.0  # 0-1 置信度


@dataclass
class BacktestResult:
    strategy_name: str
    symbol: str
    initial_capital: float
    final_equity: float
    total_return_pct: float
    annual_return_pct: float
    sharpe_ratio: float
    max_drawdown_pct: float
    win_rate_pct: float
    total_trades: int
    trades: list = field(default_factory=list)


# ============================================================
# 策略 1：双均线金叉死叉
# ============================================================
class MACrossStrategy:
    """均线金叉/死叉策略"""

    def __init__(self, fast_window=5, slow_window=20):
        self.fast = fast_window
        self.slow = slow_window
        self.name = f"MA_Cross({fast_window}/{slow_window})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["ma_fast"] = Indicators.sma(df["close"], self.fast)
        df["ma_slow"] = Indicators.sma(df["close"], self.slow)
        df["signal"] = 0

        # 金叉：快线上穿慢线
        golden = (df["ma_fast"] > df["ma_slow"]) & (df["ma_fast"].shift(1) <= df["ma_slow"].shift(1))
        # 死叉：快线下穿慢线
        death = (df["ma_fast"] < df["ma_slow"]) & (df["ma_fast"].shift(1) >= df["ma_slow"].shift(1))

        df.loc[golden, "signal"] = 1
        df.loc[death, "signal"] = -1
        return df


# ============================================================
# 策略 2：MACD 金叉策略
# ============================================================
class MACDStrategy:
    """MACD 金叉策略"""

    def __init__(self, fast=12, slow=26, signal=9):
        self.fast = fast
        self.slow = slow
        self.signal_period = signal
        self.name = f"MACD({fast}/{slow}/{signal})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["dif"], df["dea"], df["macd_hist"] = Indicators.macd(df["close"], self.fast, self.slow, self.signal_period)
        df["signal"] = 0

        golden = (df["dif"] > df["dea"]) & (df["dif"].shift(1) <= df["dea"].shift(1))
        death = (df["dif"] < df["dea"]) & (df["dif"].shift(1) >= df["dea"].shift(1))

        df.loc[golden, "signal"] = 1
        df.loc[death, "signal"] = -1
        return df


# ============================================================
# 策略 3：海龟交易法
# ============================================================
class TurtleStrategy:
    """海龟交易突破策略"""

    def __init__(self, entry_window=20, exit_window=10, atr_window=20):
        self.entry_window = entry_window
        self.exit_window = exit_window
        self.atr_window = atr_window
        self.name = f"Turtle({entry_window}/{exit_window})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["entry_high"] = df["high"].shift(1).rolling(self.entry_window).max()
        df["exit_low"] = df["low"].shift(1).rolling(self.exit_window).min()
        df["atr"] = Indicators.atr(df["high"], df["low"], df["close"], self.atr_window)
        df["signal"] = 0

        # 突破 20 日最高 -> 买入
        df.loc[df["close"] > df["entry_high"], "signal"] = 1
        # 跌破 10 日最低 -> 卖出
        df.loc[df["close"] < df["exit_low"], "signal"] = -1
        return df


# ============================================================
# 策略 4：RSI 超买超卖
# ============================================================
class RSIStrategy:
    """RSI 超买超卖策略"""

    def __init__(self, period=14, oversold=30, overbought=70):
        self.period = period
        self.oversold = oversold
        self.overbought = overbought
        self.name = f"RSI({period})"

    def generate_signals(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        df["rsi"] = Indicators.rsi(df["close"], self.period)
        df["signal"] = 0

        # RSI 从下方穿过超卖线 -> 买入
        df.loc[(df["rsi"] > self.oversold) & (df["rsi"].shift(1) <= self.oversold), "signal"] = 1
        # RSI 从上方穿过超买线 -> 卖出
        df.loc[(df["rsi"] < self.overbought) & (df["rsi"].shift(1) >= self.overbought), "signal"] = -1
        return df


# ============================================================
# 通用回测引擎
# ============================================================
class BacktestEngine:
    """通用策略回测引擎（支持 A 股 T+1 规则）"""

    def __init__(self, initial_capital=500000.0, commission=0.0003, stamp_duty=0.0005):
        self.initial_capital = initial_capital
        self.commission = commission       # 券商佣金 万三
        self.stamp_duty = stamp_duty       # 印花税 千0.5（卖出收取）

    def run(self, df: pd.DataFrame, strategy, symbol: str = "unknown") -> BacktestResult:
        """对带有 signal 列的 DataFrame 执行回测"""
        df_signals = strategy.generate_signals(df)

        cash = self.initial_capital
        position = 0
        trades = []
        equity_curve = []

        for i, row in df_signals.iterrows():
            price = row["close"]
            signal = row["signal"]
            date = row["date"]

            # 买入
            if signal == 1 and position == 0:
                max_shares = int((cash * 0.95) / price / 100) * 100  # 留 5% 现金缓冲
                if max_shares >= 100:
                    cost = max_shares * price
                    fee = max(cost * self.commission, 5.0)  # 最低 5 元佣金
                    cash -= (cost + fee)
                    position = max_shares
                    trades.append({"type": "BUY", "date": str(date), "price": price, "shares": max_shares, "fee": fee})

            # 卖出
            elif signal == -1 and position > 0:
                revenue = position * price
                fee = max(revenue * self.commission, 5.0) + revenue * self.stamp_duty
                cash += (revenue - fee)
                trades.append({"type": "SELL", "date": str(date), "price": price, "shares": position, "fee": fee})
                position = 0

            equity_curve.append(cash + position * price)

        final_equity = equity_curve[-1] if equity_curve else self.initial_capital
        total_return = (final_equity - self.initial_capital) / self.initial_capital

        # 计算年化收益
        if len(df_signals) > 0:
            days = (df_signals["date"].iloc[-1] - df_signals["date"].iloc[0]).days
            annual_return = ((1 + total_return) ** (365 / max(days, 1))) - 1 if days > 0 else 0
        else:
            annual_return = 0

        # 夏普比率
        eq_series = pd.Series(equity_curve)
        daily_returns = eq_series.pct_change().dropna()
        sharpe = 0.0
        if daily_returns.std() > 0:
            sharpe = (daily_returns.mean() * 252 - 0.02) / (daily_returns.std() * np.sqrt(252))

        # 最大回撤
        cummax = eq_series.cummax()
        drawdown = (cummax - eq_series) / cummax
        max_dd = drawdown.max() if len(drawdown) > 0 else 0

        # 胜率
        win_count = 0
        trade_pairs = len(trades) // 2
        for j in range(0, len(trades) - 1, 2):
            if trades[j]["type"] == "BUY" and trades[j + 1]["type"] == "SELL":
                if trades[j + 1]["price"] > trades[j]["price"]:
                    win_count += 1

        win_rate = (win_count / trade_pairs * 100) if trade_pairs > 0 else 0

        return BacktestResult(
            strategy_name=strategy.name,
            symbol=symbol,
            initial_capital=self.initial_capital,
            final_equity=round(final_equity, 2),
            total_return_pct=round(total_return * 100, 2),
            annual_return_pct=round(annual_return * 100, 2),
            sharpe_ratio=round(sharpe, 2),
            max_drawdown_pct=round(max_dd * 100, 2),
            win_rate_pct=round(win_rate, 2),
            total_trades=trade_pairs,
            trades=trades,
        )


# ============================================================
# 主入口：批量回测所有策略
# ============================================================
def run_all_backtests(symbol: str = "600519", start_date: str = "2023-01-01"):
    """对指定股票运行全部策略回测"""
    from data_loader import AShareDataLoader

    loader = AShareDataLoader()
    df = loader.download_stock_daily(symbol, start_date=start_date)
    if df.empty:
        print(f"❌ 无法获取 [{symbol}] 的数据")
        return

    strategies = [
        MACrossStrategy(5, 20),
        MACrossStrategy(10, 60),
        MACDStrategy(),
        TurtleStrategy(),
        RSIStrategy(),
    ]

    engine = BacktestEngine(initial_capital=500000.0)

    print(f"\n{'='*70}")
    print(f"  📊 A 股策略回测报告: [{symbol}]  回测区间: {start_date} ~ 至今")
    print(f"{'='*70}")

    results = []
    for strategy in strategies:
        result = engine.run(df, strategy, symbol=symbol)
        results.append(result)
        print(f"\n策略: {result.strategy_name}")
        print(f"  期末资产: {result.final_equity:,.2f} 元")
        print(f"  总收益率: {'🚀' if result.total_return_pct > 0 else '📉'} {result.total_return_pct:+.2f}%")
        print(f"  年化收益: {result.annual_return_pct:+.2f}%")
        print(f"  夏普比率: {result.sharpe_ratio}")
        print(f"  最大回撤: ⚠️ {result.max_drawdown_pct:.2f}%")
        print(f"  交易次数: {result.total_trades} 次 | 胜率: {result.win_rate_pct:.1f}%")

    # 找出最佳策略
    best = max(results, key=lambda r: r.total_return_pct)
    print(f"\n{'='*70}")
    print(f"  🏆 最佳策略: {best.strategy_name} (收益 {best.total_return_pct:+.2f}%)")
    print(f"{'='*70}")

    return results


if __name__ == "__main__":
    run_all_backtests("600519", start_date="2023-01-01")
