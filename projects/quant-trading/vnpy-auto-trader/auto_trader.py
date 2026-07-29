"""
全自动交易调度器 - 定时执行选股 → 生成信号 → 风控检查 → 下单执行
支持模式: paper (模拟盘) / live (实盘, 需要 miniQMT)
"""
import os
import sys
import time
import json
import logging
from datetime import datetime, date
from typing import Optional

import pandas as pd

from config import STOCK_POOL, RISK_CONTROL, BROKER_CONFIG
from data_loader import AShareDataLoader
from strategies import (
    MACrossStrategy,
    MACDStrategy,
    TurtleStrategy,
    RSIStrategy,
    Indicators,
    BacktestEngine,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("auto_trader.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger(__name__)


class RiskManager:
    """风控引擎"""

    def __init__(self, config: dict = RISK_CONTROL):
        self.config = config
        self.daily_pnl = 0.0
        self.positions: dict = {}  # {symbol: {"shares": int, "avg_price": float}}

    @property
    def total_position_value(self) -> float:
        return sum(p["shares"] * p.get("current_price", p["avg_price"]) for p in self.positions.values())

    def can_open_position(self, symbol: str, price: float, capital: float) -> tuple[bool, str]:
        """检查是否可以开新仓位"""
        # 检查当日最大亏损
        if self.daily_pnl < -capital * self.config["max_daily_loss_pct"]:
            return False, f"当日亏损已达 {self.config['max_daily_loss_pct']*100}% 上限，停止交易"

        # 检查持仓数量上限
        if len(self.positions) >= self.config["max_stocks"]:
            return False, f"持仓已达 {self.config['max_stocks']} 只上限"

        # 检查单股仓位占比
        max_alloc = capital * self.config["max_position_pct"]
        if symbol in self.positions:
            current_value = self.positions[symbol]["shares"] * price
            if current_value >= max_alloc:
                return False, f"[{symbol}] 仓位已达 {self.config['max_position_pct']*100}% 上限"

        return True, "通过风控检查"

    def check_stop_loss(self, symbol: str, current_price: float) -> bool:
        """检查是否触发止损"""
        if symbol not in self.positions:
            return False
        avg_price = self.positions[symbol]["avg_price"]
        loss_pct = (current_price - avg_price) / avg_price
        return loss_pct <= -self.config["stop_loss_pct"]

    def check_take_profit(self, symbol: str, current_price: float) -> bool:
        """检查是否触发止盈"""
        if symbol not in self.positions:
            return False
        avg_price = self.positions[symbol]["avg_price"]
        gain_pct = (current_price - avg_price) / avg_price
        return gain_pct >= self.config["take_profit_pct"]


class AutoTrader:
    """全自动交易调度器"""

    def __init__(self, mode: str = "paper"):
        self.mode = mode  # "paper" 或 "live"
        self.data_loader = AShareDataLoader()
        self.risk_manager = RiskManager()
        self.capital = RISK_CONTROL["initial_capital"]

        # 初始化策略组合（多策略投票机制）
        self.strategies = [
            MACrossStrategy(5, 20),
            MACDStrategy(),
            TurtleStrategy(),
        ]

        # 交易日志
        self.trade_log = []
        self.log_file = "trade_history.json"

        logger.info(f"AutoTrader 初始化完成 | 模式: {mode} | 初始资金: {self.capital:,.0f} 元")

    def analyze_stock(self, symbol: str) -> dict:
        """
        对单只股票执行多策略分析，返回综合信号
        使用投票机制：多数策略看多则买入，多数看空则卖出
        """
        df = self.data_loader.load_local_data(symbol)
        if df.empty or len(df) < 60:
            return {"symbol": symbol, "action": "SKIP", "reason": "数据不足"}

        votes_buy = 0
        votes_sell = 0
        reasons = []

        for strategy in self.strategies:
            df_sig = strategy.generate_signals(df)
            last_signal = df_sig["signal"].iloc[-1]

            if last_signal == 1:
                votes_buy += 1
                reasons.append(f"✅ {strategy.name}: 买入信号")
            elif last_signal == -1:
                votes_sell += 1
                reasons.append(f"❌ {strategy.name}: 卖出信号")
            else:
                reasons.append(f"⬜ {strategy.name}: 观望")

        latest_price = df["close"].iloc[-1]

        # 多数投票决策
        total = len(self.strategies)
        if votes_buy > total / 2:
            action = "BUY"
        elif votes_sell > total / 2:
            action = "SELL"
        else:
            action = "HOLD"

        return {
            "symbol": symbol,
            "action": action,
            "price": latest_price,
            "votes_buy": votes_buy,
            "votes_sell": votes_sell,
            "reasons": reasons,
        }

    def execute_trade(self, symbol: str, action: str, price: float, reason: str = ""):
        """执行交易（模拟盘或实盘）"""
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if action == "BUY":
            can_buy, msg = self.risk_manager.can_open_position(symbol, price, self.capital)
            if not can_buy:
                logger.warning(f"[{symbol}] 风控拦截: {msg}")
                return

            max_alloc = self.capital * RISK_CONTROL["max_position_pct"]
            shares = int(max_alloc / price / 100) * 100
            if shares < 100:
                logger.warning(f"[{symbol}] 资金不足以买入 100 股")
                return

            cost = shares * price
            fee = max(cost * 0.0003, 5.0)

            if self.mode == "paper":
                self.capital -= (cost + fee)
                self.risk_manager.positions[symbol] = {"shares": shares, "avg_price": price}
                logger.info(f"📈 [模拟买入] {symbol} | {shares}股 × {price}元 = {cost:,.0f}元 | 手续费 {fee:.2f}元")
            elif self.mode == "live":
                logger.info(f"📈 [实盘买入] {symbol} | {shares}股 × {price}元 （需要 miniQMT 接口）")
                # TODO: 对接 miniQMT / xtquant 实盘下单
                # from xtquant import xttrader
                # trader.order_stock(symbol, xtconstant.STOCK_BUY, shares, xtconstant.FIX_PRICE, price)

            self.trade_log.append({
                "time": now, "symbol": symbol, "action": "BUY",
                "price": price, "shares": shares, "reason": reason
            })

        elif action == "SELL":
            if symbol not in self.risk_manager.positions:
                return

            pos = self.risk_manager.positions[symbol]
            shares = pos["shares"]
            revenue = shares * price
            fee = max(revenue * 0.0003, 5.0) + revenue * 0.0005

            if self.mode == "paper":
                self.capital += (revenue - fee)
                pnl = (price - pos["avg_price"]) * shares - fee
                self.risk_manager.daily_pnl += pnl
                del self.risk_manager.positions[symbol]
                emoji = "🚀" if pnl > 0 else "📉"
                logger.info(f"{emoji} [模拟卖出] {symbol} | {shares}股 × {price}元 | 盈亏 {pnl:+,.0f}元")
            elif self.mode == "live":
                logger.info(f"📉 [实盘卖出] {symbol} | {shares}股 × {price}元 （需要 miniQMT 接口）")
                # TODO: 对接 miniQMT / xtquant 实盘卖出

            self.trade_log.append({
                "time": now, "symbol": symbol, "action": "SELL",
                "price": price, "shares": shares, "reason": reason
            })

    def run_daily_scan(self):
        """每日全自动扫描 + 交易执行"""
        logger.info("=" * 60)
        logger.info(f"🔍 开始每日全市场扫描 | {datetime.now().strftime('%Y-%m-%d %H:%M')}")
        logger.info("=" * 60)

        # 1. 先检查止损/止盈
        for symbol in list(self.risk_manager.positions.keys()):
            df = self.data_loader.load_local_data(symbol)
            if df.empty:
                continue
            current_price = df["close"].iloc[-1]

            if self.risk_manager.check_stop_loss(symbol, current_price):
                logger.warning(f"🛑 [{symbol}] 触发止损! 当前价 {current_price}")
                self.execute_trade(symbol, "SELL", current_price, reason="触发止损线")
            elif self.risk_manager.check_take_profit(symbol, current_price):
                logger.info(f"🎯 [{symbol}] 触发止盈! 当前价 {current_price}")
                self.execute_trade(symbol, "SELL", current_price, reason="触发止盈线")

        # 2. 扫描股票池，生成信号并执行
        scan_results = []
        for symbol, name in STOCK_POOL.items():
            result = self.analyze_stock(symbol)
            result["name"] = name
            scan_results.append(result)
            action = result["action"]

            if action in ("BUY", "SELL"):
                reason = " | ".join(result["reasons"])
                self.execute_trade(symbol, action, result["price"], reason=reason)

        # 2.5 输出全市场扫描诊断报告
        print(f"\n{'='*75}")
        print(f"  📋 全市场多策略扫描诊断报告 | {datetime.now().strftime('%Y-%m-%d')}")
        print(f"{'='*75}")
        print(f"  {'股票':<12} {'最新价':>8} {'多头票':>6} {'空头票':>6} {'决策':>8}  信号详情")
        print(f"  {'─'*70}")
        for r in scan_results:
            action_emoji = {"BUY": "🟢买入", "SELL": "🔴卖出", "HOLD": "⚪观望", "SKIP": "⏭跳过"}
            action_str = action_emoji.get(r["action"], r["action"])
            price_str = f"{r.get('price', 0):.2f}" if r.get("price") else "N/A"
            reasons_short = " ".join(["✅" if "买入" in rr else "❌" if "卖出" in rr else "⬜" for rr in r.get("reasons", [])])
            print(f"  {r['name']:<10} {price_str:>10} {r.get('votes_buy',0):>6} {r.get('votes_sell',0):>6} {action_str:>10}  {reasons_short}")

        # 统计
        buy_count = sum(1 for r in scan_results if r["action"] == "BUY")
        sell_count = sum(1 for r in scan_results if r["action"] == "SELL")
        print(f"  {'─'*70}")
        print(f"  汇总: {buy_count} 只触发买入 | {sell_count} 只触发卖出 | {len(scan_results)-buy_count-sell_count} 只观望")
        print(f"{'='*75}")

        # 3. 输出账户状态
        self._print_account_summary()

        # 4. 保存交易日志
        self._save_trade_log()

    def _print_account_summary(self):
        """输出当前账户状态"""
        pos_value = self.risk_manager.total_position_value
        total = self.capital + pos_value

        print(f"\n{'─'*50}")
        print(f"  💰 账户状态汇总")
        print(f"{'─'*50}")
        print(f"  现金余额: {self.capital:>15,.2f} 元")
        print(f"  持仓市值: {pos_value:>15,.2f} 元")
        print(f"  总资产:   {total:>15,.2f} 元")
        print(f"  总收益率: {(total/RISK_CONTROL['initial_capital']-1)*100:>+14.2f}%")
        print(f"  当前持仓: {len(self.risk_manager.positions)} 只")

        if self.risk_manager.positions:
            print(f"\n  持仓明细:")
            for sym, pos in self.risk_manager.positions.items():
                name = STOCK_POOL.get(sym, sym)
                print(f"    {name}({sym}): {pos['shares']}股 × 均价{pos['avg_price']:.2f}元")
        print(f"{'─'*50}\n")

    def _save_trade_log(self):
        """保存交易历史到 JSON"""
        with open(self.log_file, "w", encoding="utf-8") as f:
            json.dump(self.trade_log, f, ensure_ascii=False, indent=2)
        logger.info(f"交易日志已保存 -> {self.log_file}")


# ============================================================
# 主入口
# ============================================================
def main():
    print("=" * 60)
    print("  🚀 VeighNa A股全自动量化交易系统 v1.0")
    print("=" * 60)

    mode = BROKER_CONFIG.get("trading_mode", "paper")
    trader = AutoTrader(mode=mode)

    print("\n【功能菜单】")
    print(" [1] 下载/更新股票池历史数据")
    print(" [2] 运行多策略回测对比")
    print(" [3] 执行一次每日自动扫描 + 交易 (模拟盘)")
    print(" [4] 查看当前账户状态")
    print(" [0] 退出")

    while True:
        choice = input("\n请选择 [0-4]: ").strip()

        if choice == "1":
            print("\n正在下载股票池数据...")
            trader.data_loader.download_stock_pool(STOCK_POOL, start_date="2023-01-01")
            print("✅ 数据下载完成！")

        elif choice == "2":
            symbol = input("输入回测股票代码 (默认 600519): ").strip() or "600519"
            from strategies import run_all_backtests
            run_all_backtests(symbol)

        elif choice == "3":
            print("\n⚡ 开始执行每日自动扫描...")
            # 先更新数据
            trader.data_loader.download_stock_pool(STOCK_POOL, start_date="2024-01-01")
            # 执行扫描 + 交易
            trader.run_daily_scan()

        elif choice == "4":
            trader._print_account_summary()

        elif choice == "0":
            print("\n感谢使用 VeighNa A股全自动量化交易系统！")
            break
        else:
            print("无效选项，请重新选择。")


if __name__ == "__main__":
    main()
