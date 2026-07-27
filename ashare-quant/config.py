import os

# 项目基础路径
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# 默认初始资金 (人民币)
INITIAL_CAPITAL = 500000.0

# 默认风控参数
DEFAULT_STOP_LOSS_PCT = 0.05    # 止损线 5%
DEFAULT_TAKE_PROFIT_PCT = 0.15  # 止盈线 15%
MAX_POSITION_PCT = 0.3          # 单只股票最大建仓比例 30%

# 示例自选股清单 (股票代码: 股票名称)
DEFAULT_WATCHLIST = {
    "600519": "贵州茅台",
    "000001": "平安银行",
    "000651": "格力电器",
    "300750": "宁德时代",
    "601318": "中国平安",
    "600036": "招商银行",
    "002594": "比亚迪",
    "601899": "紫金矿业"
}
