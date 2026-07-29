import pandas as pd
import numpy as np

class TechnicalIndicators:
    """技术指标计算工具类"""

    @staticmethod
    def add_ma(df: pd.DataFrame, windows=[5, 10, 20, 60]) -> pd.DataFrame:
        """添加简单移动平均线 (MA)"""
        df = df.copy()
        for w in windows:
            df[f'MA_{w}'] = df['Close'].rolling(window=w).mean()
        return df

    @staticmethod
    def add_macd(df: pd.DataFrame, fast=12, slow=26, signal=9) -> pd.DataFrame:
        """添加 MACD 指标"""
        df = df.copy()
        exp1 = df['Close'].ewm(span=fast, adjust=False).mean()
        exp2 = df['Close'].ewm(span=slow, adjust=False).mean()
        df['MACD_DIF'] = exp1 - exp2
        df['MACD_DEA'] = df['MACD_DIF'].ewm(span=signal, adjust=False).mean()
        df['MACD_Hist'] = 2 * (df['MACD_DIF'] - df['MACD_DEA'])
        return df

    @staticmethod
    def add_bollinger(df: pd.DataFrame, window=20, num_std=2) -> pd.DataFrame:
        """添加布林带指标"""
        df = df.copy()
        df['BOLL_Mid'] = df['Close'].rolling(window=window).mean()
        std = df['Close'].rolling(window=window).std()
        df['BOLL_Upper'] = df['BOLL_Mid'] + (num_std * std)
        df['BOLL_Lower'] = df['BOLL_Mid'] - (num_std * std)
        return df

    @staticmethod
    def add_rsi(df: pd.DataFrame, period=14) -> pd.DataFrame:
        """添加 RSI 相对强弱指标"""
        df = df.copy()
        delta = df['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        rs = gain / loss
        df['RSI'] = 100 - (100 / (1 + rs))
        return df


class QuantStrategyEngine:
    """量化策略与信号计算引擎"""

    @classmethod
    def apply_ma_cross_strategy(cls, df: pd.DataFrame, fast_period=5, slow_period=20) -> pd.DataFrame:
        """
        均线金叉/死叉策略
        Signal: 1 (买入), -1 (卖出), 0 (持仓/观望)
        """
        df = TechnicalIndicators.add_ma(df, windows=[fast_period, slow_period])
        df['Signal'] = 0

        # 金叉：5日上穿20日
        golden_cross = (df[f'MA_{fast_period}'] > df[f'MA_{slow_period}']) & \
                       (df[f'MA_{fast_period}'].shift(1) <= df[f'MA_{slow_period}'].shift(1))

        # 死叉：5日下穿20日
        death_cross = (df[f'MA_{fast_period}'] < df[f'MA_{slow_period}']) & \
                      (df[f'MA_{fast_period}'].shift(1) >= df[f'MA_{slow_period}'].shift(1))

        df.loc[golden_cross, 'Signal'] = 1
        df.loc[death_cross, 'Signal'] = -1
        return df

    @classmethod
    def apply_macd_strategy(cls, df: pd.DataFrame) -> pd.DataFrame:
        """MACD 金叉买入策略"""
        df = TechnicalIndicators.add_macd(df)
        df['Signal'] = 0

        # MACD 金叉 (DIF 上穿 DEA)
        macd_golden = (df['MACD_DIF'] > df['MACD_DEA']) & (df['MACD_DIF'].shift(1) <= df['MACD_DEA'].shift(1))
        # MACD 死叉
        macd_death = (df['MACD_DIF'] < df['MACD_DEA']) & (df['MACD_DIF'].shift(1) >= df['MACD_DEA'].shift(1))

        df.loc[macd_golden, 'Signal'] = 1
        df.loc[macd_death, 'Signal'] = -1
        return df

    @classmethod
    def calculate_multifactor_score(cls, df: pd.DataFrame) -> dict:
        """
        多因子量化选股评分算法 (满分 100 分)
        考虑因素: 均线排列、MACD状态、RSI指标、成交量突破、20日涨跌幅
        """
        if len(df) < 60:
            return {"score": 0, "rating": "数据不足", "reasons": ["K线数量不足60个交易日"]}

        df_calc = TechnicalIndicators.add_ma(df, windows=[5, 10, 20, 60])
        df_calc = TechnicalIndicators.add_macd(df_calc)
        df_calc = TechnicalIndicators.add_rsi(df_calc)
        df_calc = TechnicalIndicators.add_bollinger(df_calc)

        latest = df_calc.iloc[-1]
        prev = df_calc.iloc[-2]

        score = 50 # 基础起步分
        reasons = []

        # 1. 均线多头排列 (MA5 > MA10 > MA20 > MA60) +20分
        if latest['MA_5'] > latest['MA_10'] > latest['MA_20'] > latest['MA_60']:
            score += 20
            reasons.append("【均线多头】MA5 > MA10 > MA20 > MA60 强多头格局 (+20)")
        elif latest['MA_5'] > latest['MA_20']:
            score += 10
            reasons.append("【短期站上均线】股价站上20日均线 (+10)")

        # 2. MACD 状态评分 (+15分)
        if latest['MACD_DIF'] > latest['MACD_DEA'] and latest['MACD_Hist'] > 0:
            score += 15
            reasons.append("【MACD红柱】DIF在DEA上方且红柱放大 (+15)")
        elif latest['MACD_DIF'] > latest['MACD_DEA']:
            score += 8
            reasons.append("【MACD水上】DIF呈金叉状态 (+8)")

        # 3. RSI 状态评分 (+15分)
        rsi = latest['RSI']
        if 50 <= rsi <= 70:
            score += 15
            reasons.append(f"【RSI健康强势】RSI={rsi:.1f} 位于50-70黄金拉升区 (+15)")
        elif 30 <= rsi < 50:
            score += 10
            reasons.append(f"【RSI蓄势区间】RSI={rsi:.1f} 处于中位区域 (+10)")
        elif rsi > 80:
            score -= 10
            reasons.append(f"【RSI超买警告】RSI={rsi:.1f} > 80 短期防范回调 (-10)")

        # 4. 成交量量比评分 (+15分)
        ma_vol_5 = df_calc['Volume'].tail(5).mean()
        if latest['Volume'] > 1.5 * ma_vol_5:
            score += 15
            reasons.append(f"【放量放能】当日成交量突破5日均量1.5倍 (+15)")

        # 5. 价格突破布林带中轨 (+15分)
        if latest['Close'] > latest['BOLL_Mid'] and prev['Close'] <= prev['BOLL_Mid']:
            score += 15
            reasons.append("【布林带突破】价格有效上穿布林带中轨 (+15)")

        # 综合评级
        if score >= 80:
            rating = "强烈推荐 (Strong Buy)"
        elif score >= 65:
            rating = "偏多买入 (Buy)"
        elif score >= 50:
            rating = "中性观望 (Hold)"
        else:
            rating = "偏空建议规避 (Sell)"

        return {
            "score": min(score, 100),
            "rating": rating,
            "latest_close": latest['Close'],
            "pct_change": latest.get('PctChg', 0.0),
            "reasons": reasons
        }
