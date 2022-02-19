import logging

import backtrader as bt
from backtrader.feeds import PandasData

from datasource import datasource_factory
from example.backtest.data_loader import comply_backtrader_data_format
from utils import utils
import numpy as np
logger = logging.getLogger(__name__)


class TestStrategy(bt.Strategy):

    def __init__(self):
        self.value_history=[]
        self.dataclose = self.datas[0].close
        print("stock names:", [data._name for data in self.datas])

    # 订单状态通知，买入卖出都是下单
    def notify_order(self, order):
        pass

    # 交易状态通知，一买一卖算交易
    def notify_trade(self, trade):
        pass

    def next(self):
        # import pdb; pdb.set_trace()
        # print(self.datas[0]._name, self.datas[0].datetime.date(), self.datas[0].close[0])
        self.buy(self.datas[0], size=100)  # 第一只股票
        self.buy(self.datas[1], size=50)
        self.buy(self.datas[2], size=10)
        self.value_history.append(self.broker.getvalue())
        print("今日总资产:", self.broker.getvalue())
        print("总资产均值:", np.array(self.value_history).mean())
        print("总资标准差:", np.array(self.value_history).std())
        print("len:", len(self.data), ",buflen:", self.data.buflen())
        print("-"*80)


# python -m test.toy.test_multistocks_backtrader
if __name__ == '__main__':
    utils.init_logger()

    start_date = '20200101'
    end_date = '20201201'
    datasource = datasource_factory.get()
    stocks = datasource.index_weight('000905.SH', start_date, end_date)
    stocks = stocks[:5]
    d_start_date = utils.str2date(start_date)
    d_end_date = utils.str2date(end_date)

    cerebro = bt.Cerebro()
    cerebro.broker.setcash(100000)
    cerebro.broker.setcommission(commission=0)
    cerebro.addstrategy(TestStrategy)

    # 想脑波cerebro逐个追加每只股票的数据
    for stock_code in stocks:
        df_stock = datasource.daily(stock_code, start_date, end_date)
        df_stock = comply_backtrader_data_format(df_stock)
        data = PandasData(dataname=df_stock, fromdate=d_start_date, todate=d_end_date, plot=False)
        cerebro.adddata(data, name=stock_code)
        logger.debug("初始化股票[%s]数据到脑波cerebro：%d 条", stock_code, len(df_stock))

    cerebro.run(tradehistory=True)
