import pandas as pd
import numpy as np

class BacktestEngine:
    """轻量级高效率A股策略回测引擎"""

    def __init__(self, initial_capital: float = 500000.0, commission_rate: float = 0.0003, stamp_duty: float = 0.0005):
        """
        :param initial_capital: 初始资金 (默认50万元，支持贵州茅台等高价股一手门槛)
        :param commission_rate: 券商佣金万三 (0.03%)
        :param stamp_duty: 印花税千0.5 (卖出时收取 0.05%)
        """
        self.initial_capital = initial_capital
        self.commission_rate = commission_rate
        self.stamp_duty = stamp_duty

    def run_backtest(self, df_with_signals: pd.DataFrame) -> dict:
        """
        根据带有 'Signal' 列 (1: 买入信号, -1: 卖出信号) 的 DataFrame 进行回测模拟
        """
        df = df_with_signals.copy()
        if 'Signal' not in df.columns:
            raise ValueError("传入的 DataFrame 必须包含 'Signal' 列！")

        cash = self.initial_capital
        position = 0.0 # 持股数量
        equity_curve = [] # 净值曲线
        trades = [] # 交易记录

        for i, row in df.iterrows():
            close_price = row['Close']
            date = row['Date']
            signal = row['Signal']

            # 执行买入信号 (全仓或按比例买入)
            if signal == 1 and position == 0:
                # 买入100股的倍数
                max_shares = int((cash * (1 - self.commission_rate)) / close_price / 100) * 100
                if max_shares > 0:
                    cost = max_shares * close_price
                    fee = cost * self.commission_rate
                    cash -= (cost + fee)
                    position = max_shares
                    trades.append({
                        "type": "BUY", "date": date, "price": close_price,
                        "shares": max_shares, "cost": cost, "fee": fee
                    })

            # 执行卖出信号
            elif signal == -1 and position > 0:
                revenue = position * close_price
                fee = revenue * (self.commission_rate + self.stamp_duty)
                cash += (revenue - fee)
                trades.append({
                    "type": "SELL", "date": date, "price": close_price,
                    "shares": position, "revenue": revenue, "fee": fee
                })
                position = 0

            # 当前总资产 (现金 + 持仓市值)
            total_equity = cash + (position * close_price)
            equity_curve.append(total_equity)

        df['Equity'] = equity_curve
        df['Market_Return'] = (df['Close'] / df['Close'].iloc[0]) * self.initial_capital

        # 统计核心指标
        total_return = (equity_curve[-1] - self.initial_capital) / self.initial_capital
        benchmark_return = (df['Close'].iloc[-1] - df['Close'].iloc[0]) / df['Close'].iloc[0]

        # 日收益率
        df['Daily_Return'] = df['Equity'].pct_change().fillna(0)
        sharpe_ratio = 0.0
        if df['Daily_Return'].std() != 0:
            # 年化夏普比率 (假设无风险利率 2%)
            sharpe_ratio = (df['Daily_Return'].mean() * 252 - 0.02) / (df['Daily_Return'].std() * np.sqrt(252))

        # 最大回撤 (Max Drawdown)
        df['CumMax'] = df['Equity'].cummax()
        df['Drawdown'] = (df['CumMax'] - df['Equity']) / df['CumMax']
        max_drawdown = df['Drawdown'].max()

        # 胜率计算
        win_trades = 0
        total_trade_pairs = len(trades) // 2
        for t_idx in range(0, len(trades) - 1, 2):
            if trades[t_idx]['type'] == 'BUY' and trades[t_idx+1]['type'] == 'SELL':
                buy_cost = trades[t_idx]['cost'] + trades[t_idx]['fee']
                sell_revenue = trades[t_idx+1]['revenue'] - trades[t_idx+1]['fee']
                if sell_revenue > buy_cost:
                    win_trades += 1

        win_rate = (win_trades / total_trade_pairs) if total_trade_pairs > 0 else 0.0

        return {
            "initial_capital": self.initial_capital,
            "final_equity": round(equity_curve[-1], 2),
            "total_return": f"{total_return * 100:.2f}%",
            "benchmark_return": f"{benchmark_return * 100:.2f}%",
            "sharpe_ratio": round(sharpe_ratio, 2),
            "max_drawdown": f"{max_drawdown * 100:.2f}%",
            "total_trades": total_trade_pairs,
            "win_rate": f"{win_rate * 100:.2f}%",
            "trades_detail": trades,
            "equity_df": df
        }
