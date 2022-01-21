import logging
import time

import pandas as pd

from example.backtest.strategy_multifactors import MultiFactorStrategy
from example.backtest.strategy_synthesis import SynthesizedFactorStrategy
from utils import utils

utils.init_logger()

from backtrader.feeds import PandasData

from datasource import datasource_factory, datasource_utils
from example import factor_synthesizer, factor_utils
import backtrader as bt  # 引入backtrader框架
import backtrader.analyzers as bta  # 添加分析函数

"""
用factor_tester.py中合成的多因子，做选择股票的策略 ，去选择中证500的股票，跑收益率回测。使用backtrader来做回测框架。
参考：
- https://zhuanlan.zhihu.com/p/351751730
"""

logger = logging.getLogger(__name__)

datasource = datasource_factory.get()


class Percent(bt.Sizer):
    """
    定义每次卖出的股票的百分比
    """
    params = (
        ('percents', 10),
        ('retint', False),  # 返回整数
    )

    def __init__(self):
        pass

    def _getsizing(self, comminfo, cash, data, isbuy):
        position = self.broker.getposition(data)
        if not position:
            size = cash / data.close[0] * (self.params.percents / 100)
        else:
            size = position.size

        if self.p.retint:
            size = int(size)

        return size


# # 自定义数据
# class FactorData(PandasData):
#     lines = ('market_value', 'momentum', 'peg', 'clv',)
#     params = (('market_value', 7), ('momentum', 8), ('peg', 9), ('clv', 10),)


# 按照backtrader要求的数据格式做数据整理,格式化成backtrader要求：索引日期；列名叫vol和datetime
def comply_backtrader_data_format(df):
    df = df.rename(columns={'vol': 'volume', 'datetime': 'datetime', 'trade_date': 'code'})  # 列名准从backtrader的命名规范
    df['openinterest'] = 0  # backtrader需要这列，所以给他补上
    df = datasource_utils.reset_index(df, date_only=True)  # 只设置日期列为索引
    df = df.sort_index(ascending=True)
    return df


def __load_strategy_and_data(stock_codes, start_date, end_date, factor_names, factor_policy):

    factor_dict = factor_utils.get_factors(stock_codes, factor_names, start_date, end_date)

    if factor_policy == "synthesis":
        synthesized_factor = factor_synthesizer.synthesize_by_jaqs(stock_codes, factor_dict, start_date, end_date)
        synthesized_factor.index = pd.to_datetime(synthesized_factor.index, format="%Y%m%d")
        logger.debug("合成的多因子为：%d 行\n%r", len(synthesized_factor), synthesized_factor)
        return SynthesizedFactorStrategy, synthesized_factor
    if factor_policy == "single":
        return MultiFactorStrategy, factor_dict

    raise ValueError("无效的因子处理策略：" + factor_policy)


def main(start_date, end_date, index_code, period, stock_num, factor_names, factor_policy):
    """
    datetime    open    high    low     close   volume  openi..
    2016-06-24	0.16	0.002	0.085	0.078	0.173	0.214
    2016-06-27	0.16	0.003	0.063	0.048	0.180	0.202
    2016-06-28	0.13	0.010	0.059	0.034	0.111	0.122
    2016-06-29	0.06	0.019	0.058	0.049	0.042	0.053
    2016-06-30	0.03	0.012	0.037	0.027	0.010	0.077
    """

    cerebro = bt.Cerebro()  # 初始化cerebro

    stock_codes = datasource.index_weight(index_code, start_date)
    stock_codes = stock_codes.tolist()
    stock_codes = stock_codes[:stock_num]

    d_start_date = utils.str2date(start_date)  # 开始日期
    d_end_date = utils.str2date(end_date)  # 结束日期

    # 加载上证指数，就是为了当日期占位符,在Cerebro中添加上证股指数据,格式: datetime,open,high,low,close,volume,openi..
    # 把上证指数，作为股票的第一个，排头兵，主要是为了用它来做时间对齐
    df_index = datasource.index_daily(index_code, start_date, end_date)
    df_index = comply_backtrader_data_format(df_index)
    data = PandasData(dataname=df_index, fromdate=d_start_date, todate=d_end_date)  # , plot=False)
    cerebro.adddata(data, name="000001.SH")
    logger.debug("初始化上证数据到脑波：%d 条", len(df_index))

    # 想脑波cerebro逐个追加每只股票的数据
    for stock_code in stock_codes:
        df_stock = datasource.daily(stock_code, start_date, end_date)

        trade_days = datasource.trade_cal(start_date, end_date)
        if len(df_stock) / len(trade_days) < 0.9:
            logger.warning("股票[%s] 缺失交易日[%d/总%d]天，超过10%%，忽略此股票",
                           stock_code, len(df_stock), len(trade_days))
            continue

        df_stock = comply_backtrader_data_format(df_stock)
        data = PandasData(dataname=df_stock, fromdate=d_start_date, todate=d_end_date)  # , plot=False)
        cerebro.adddata(data, name=stock_code)
        logger.debug("初始化股票[%s]数据到脑波cerebro：%d 条", stock_code, len(df_stock))
    logger.debug("合计追加 %d 只股票数据到脑波cerebro", len(stock_codes) + 1)

    ################## cerebro 整体设置 #####################

    # 设置启动资金
    start_cash = 100000.0
    cerebro.broker.setcash(start_cash)

    # https://baike.baidu.com/item/%E8%82%A1%E7%A5%A8%E4%BA%A4%E6%98%93%E6%89%8B%E7%BB%AD%E8%B4%B9/9080806
    # 设置交易手续费：印花税0.001+证管费0.00002+证券交易经手费0.0000487+券商交易佣金0.003
    cerebro.broker.setcommission(commission=0.004)

    # 设置订单份额,设置每笔交易交易的股票数量,比如" cerebro.addsizer(bt.sizers.FixedSize, stake=10)"
    # 告诉平台，我们是每次买卖股票数量固定的，stake=10就是10股。
    # 实际过程中，我们不可能如此简单的制定买卖的数目，而是要根据一定的规则，这就需要自己写一个sizers
    # cerebro.addsizer(Percent)

    strategy_class, factor_data = __load_strategy_and_data(stock_codes, start_date, end_date, factor_names,
                                                           factor_policy)

    # 将交易策略加载到回测系统中
    cerebro.addstrategy(strategy_class, period, factor_data)

    # 添加分析对象
    cerebro.addanalyzer(bta.SharpeRatio, _name="sharpe")  # ,timeframe=bt.TimeFrame.Days)  # 夏普指数
    cerebro.addanalyzer(bt.analyzers.DrawDown, _name='DW')  # 回撤分析

    # 打印
    logger.debug('回测期间：%r ~ %r , 初始资金: %r', start_date, end_date, start_cash)
    # 运行回测
    results = cerebro.run()
    # 打印最后结果
    portvalue = cerebro.broker.getvalue()
    pnl = portvalue - start_cash
    # 打印结果
    logger.debug("=" * 80)
    logger.debug("股票个数: %d 只", len(stock_codes))
    logger.debug("投资期间: %s~%s, %d 天", start_date, end_date, (d_end_date - d_start_date).days)
    logger.debug("因子策略: %s", factor_policy)
    logger.debug('期初投资: %.2f', start_cash)
    logger.debug('期末总额: %.2f', portvalue)
    logger.debug('剩余头寸: %.2f', cerebro.broker.getcash())
    logger.debug('净收益额: %.2f', pnl)
    logger.debug('收益率: %.2f%%', pnl / portvalue * 100)
    logger.debug("夏普比: %r", results[0].analyzers.sharpe.get_analysis())
    logger.debug("回撤:   %.2f%%", results[0].analyzers.DW.get_analysis().drawdown)
    # cerebro.plot(style="candlestick",iplot=False)
    # bt.AutoOrderedDict


# python -m example.factor_backtester
if __name__ == '__main__':
    start_time = time.time()
    start_date = "20130101"  # 开始日期
    end_date = "20171231"  # 结束日期
    stock_pool_index = '000905.SH'  # 股票池为中证500
    period = 22  # 调仓周期
    stock_num = 50  # 用股票池中的几只，初期调试设置小10，后期可以调成全部
    factor_names = list(factor_utils.FACTORS.keys())
    factor_policy = "synthesis"  # synthesis| single 是合成，还是单独使用
    main(start_date, end_date, stock_pool_index, period, stock_num, factor_names, factor_policy)
    logger.debug("共耗时: %.0f 秒", time.time() - start_time)