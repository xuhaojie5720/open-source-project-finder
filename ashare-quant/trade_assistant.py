import pandas as pd
from data_engine import DataEngine
from strategies import QuantStrategyEngine, TechnicalIndicators
import config

class TradeAssistant:
    """A股股票实盘操作辅助诊股与风控计算器"""

    def __init__(self, capital: float = config.INITIAL_CAPITAL):
        self.capital = capital
        self.data_engine = DataEngine()

    def diagnose_stock(self, symbol: str) -> dict:
        """
        对单只股票进行全面的量化诊断并输出操作建议
        """
        df = self.data_engine.get_stock_daily(symbol)
        if df.empty:
            return {"error": f"无法获取股票 [{symbol}] 的历史数据，请检查代码。"}

        # 多因子量化打分
        factor_res = QuantStrategyEngine.calculate_multifactor_score(df)
        latest_price = factor_res["latest_close"]

        # 风控仓位计算 (按单股最大30%资金占比)
        max_alloc_cash = self.capital * config.MAX_POSITION_PCT
        suggested_shares = int(max_alloc_cash / latest_price / 100) * 100
        actual_capital_need = suggested_shares * latest_price

        # 动态止损与止盈位
        stop_loss_price = round(latest_price * (1 - config.DEFAULT_STOP_LOSS_PCT), 2)
        take_profit_price = round(latest_price * (1 + config.DEFAULT_TAKE_PROFIT_PCT), 2)

        # 推荐操作指令
        score = factor_res["score"]
        if score >= 80:
            action_code = "BUY_STRONG"
            action_msg = "建议买入 / 分批建仓"
        elif score >= 65:
            action_code = "BUY_LIGHT"
            action_msg = "轻仓试错 / 逢低关注"
        elif score >= 50:
            action_code = "HOLD"
            action_msg = "持股观望 / 暂不加仓"
        else:
            action_code = "SELL"
            action_msg = "规避观望 / 逢高减仓"

        report = {
            "symbol": symbol,
            "latest_price": latest_price,
            "pct_change": factor_res["pct_change"],
            "score": score,
            "rating": factor_res["rating"],
            "action_code": action_code,
            "action_msg": action_msg,
            "risk_management": {
                "suggested_shares": suggested_shares,
                "capital_required": round(actual_capital_need, 2),
                "stop_loss_price": stop_loss_price,
                "take_profit_price": take_profit_price,
                "max_risk_pct": f"{config.DEFAULT_STOP_LOSS_PCT*100}%"
            },
            "reasons": factor_res["reasons"]
        }
        return report

    def scan_watchlist(self, watchlist: dict = config.DEFAULT_WATCHLIST) -> pd.DataFrame:
        """批量扫描自选股池，输出量化评分与买卖建议清单"""
        results = []
        for symbol, name in watchlist.items():
            res = self.diagnose_stock(symbol)
            if "error" not in res:
                results.append({
                    "股票代码": symbol,
                    "股票名称": name,
                    "最新价": res["latest_price"],
                    "涨跌幅(%)": res["pct_change"],
                    "量化评分": res["score"],
                    "评级": res["rating"],
                    "建议操作": res["action_msg"],
                    "建议股数": res["risk_management"]["suggested_shares"],
                    "止损参考": res["risk_management"]["stop_loss_price"],
                    "止盈参考": res["risk_management"]["take_profit_price"]
                })

        df_scan = pd.DataFrame(results)
        if not df_scan.empty:
            df_scan = df_scan.sort_values("量化评分", ascending=False).reset_index(drop=True)
        return df_scan
