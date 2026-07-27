import sys
import os
import pandas as pd
from data_engine import DataEngine
from trade_assistant import TradeAssistant
from strategies import QuantStrategyEngine
from backtest_engine import BacktestEngine
import config

def print_banner():
    print("=" * 65)
    print("      🚀 AShare-Quant (A股开源量化交易与股票操作助手) v1.0      ")
    print("=" * 65)

def option_scan_watchlist(assistant: TradeAssistant):
    print("\n[系统提示] 正在拉取自选股池的行情并进行多因子量化评分...")
    df_scan = assistant.scan_watchlist()
    if df_scan.empty:
        print("未成功拉取到自选股数据。")
        return
    print("\n📊 【自选股池多因子量化选股与操作建议排行榜】")
    print("-" * 80)
    print(df_scan.to_string(index=False))
    print("-" * 80)

def option_diagnose_stock(assistant: TradeAssistant):
    symbol = input("\n请输入要诊断的6位A股代码 (例如 600519 贵州茅台 / 000651 格力电器): ").strip()
    if not symbol:
        symbol = "600519"
    report = assistant.diagnose_stock(symbol)
    if "error" in report:
        print(f"❌ {report['error']}")
        return

    print("\n" + "★" * 50)
    print(f" 📈 股票诊断报告: [{report['symbol']}]  最新价: {report['latest_price']} 元 (涨跌幅: {report['pct_change']}%)")
    print("★" * 50)
    print(f"【综合评分】: {report['score']} / 100 分")
    print(f"【综合评级】: {report['rating']}")
    print(f"【操作建议】: 🔥 {report['action_msg']}")
    print("\n【逻辑依据分析】:")
    for reason in report['reasons']:
        print(f"  • {reason}")

    rm = report['risk_management']
    print("\n【风控与实盘操作建议】:")
    print(f"  • 建议建仓股数: {rm['suggested_shares']} 股 (预计需资金 {rm['capital_required']} 元)")
    print(f"  • 推荐止损离场线: 🛑 {rm['stop_loss_price']} 元 (止损风控比例 -5%)")
    print(f"  • 推荐止盈目标线: 🎯 {rm['take_profit_price']} 元 (目标获利比例 +15%)")
    print("★" * 50)

def option_run_backtest():
    symbol = input("\n请输入用于回测的6位A股代码 (默认 600519): ").strip() or "600519"
    print(f"\n[系统提示] 正在获取 [{symbol}] 历史K线并执行【均线金叉策略】回测...")

    engine = DataEngine()
    df = engine.get_stock_daily(symbol, start_date="20230101")
    if df.empty:
        print("未成功获取数据，无法执行回测。")
        return

    df_signals = QuantStrategyEngine.apply_ma_cross_strategy(df)
    bt = BacktestEngine(initial_capital=100000.0)
    res = bt.run_backtest(df_signals)

    print("\n" + "=" * 55)
    print(f" 📈 策略历史回测报告: [{symbol}] (测试周期 2023至今)")
    print("=" * 55)
    print(f" 初始资金   : {res['initial_capital']:,.2f} 元")
    print(f" 期末总资产 : {res['final_equity']:,.2f} 元")
    print(f" 策略总收益 : 🚀 {res['total_return']}")
    print(f" 基准(持股) : 📉 {res['benchmark_return']}")
    print(f" 夏普比率   : {res['sharpe_ratio']}")
    print(f" 最大回撤   : ⚠️ {res['max_drawdown']}")
    print(f" 交易次数   : {res['total_trades']} 次")
    print(f" 胜率     : 🏆 {res['win_rate']}")
    print("=" * 55)

def main():
    print_banner()
    assistant = TradeAssistant()

    while True:
        print("\n【功能菜单选项】")
        print(" [1] 扫描自选股池 (量化打分与操作建议)")
        print(" [2] 深度诊断单只股票 (查看买卖点与止损线)")
        print(" [3] 运行量化策略历史回测 (评估策略获利能力)")
        print(" [0] 退出系统")

        choice = input("\n请选择功能编号 [0-3]: ").strip()
        if choice == "1":
            option_scan_watchlist(assistant)
        elif choice == "2":
            option_diagnose_stock(assistant)
        elif choice == "3":
            option_run_backtest()
        elif choice == "0":
            print("\n感谢使用 AShare-Quant 量化交易助手，祝您投资顺利！")
            break
        else:
            print("输入选项无效，请重新选择。")

if __name__ == "__main__":
    main()
