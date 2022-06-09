import logging
from datetime import datetime

import baostock as bs
import pandas as pd

from datasource.datasource import DataSource, post_query

logger = logging.getLogger(__name__)


class BaostockDataSource(DataSource):
    """
    baostock.com, 不需要注册的股票数据源，真好！
    TODO: 由于一些接口，目前处于废弃状态，未实现完整
    """

    def __init__(self):
        bs.login()

    def __date_format(self, s_date: str):
        """
        YYYYMMDD=>YYYY-MM-DD
        """
        assert len(s_date) == 8  # 格式YYYYMMDD
        return datetime.strftime(datetime.strptime(s_date, "%Y%m%d"), "%Y-%m-%d")

    """
    还没实现，抽空实现一下
    """

    def __daily_one(self, stock_code, start_date, end_date):
        """
        #### 获取沪深A股历史K线数据 ####
        # 详细指标参数，参见“历史行情指标参数”章节；“分钟线”参数与“日线”参数不同。“分钟线”不包含指数。
        # 分钟线指标：date,time,code,open,high,low,close,volume,amount,adjustflag
        # 周月线指标：date,code,open,high,low,close,volume,amount,adjustflag,turn,pctChg
        http://baostock.com/baostock/index.php/A%E8%82%A1K%E7%BA%BF%E6%95%B0%E6%8D%AE
        """
        rs = self.bs.query_history_k_data_plus(stock_code,
                                               "date,code,open,high,low,close,preclose,volume,amount,adjustflag,turn,tradestatus,pctChg,isST",
                                               start_date=self.__date_format(start_date),
                                               end_date=self.__date_format(end_date),
                                               frequency="d",
                                               adjustflag="3")  # 默认不复权：3；1：后复权；2：前复权。
        return rs

    @post_query
    def daily(self, stock_code, start_date, end_date):
        if type(stock_code) == list:
            logger.debug("获取多只股票的交易数据：%r", ",".join(stock_code))
            df_basics = [self.__daily_one(stock, start_date, end_date) for stock in stock_code]
            print(df_basics)
            return pd.concat(df_basics)
        return self.__daily_one(stock_code, start_date, end_date)

    # 返回每日的其他信息，主要是市值啥的
    @post_query
    def daily_basic(self, stock_code, start_date, end_date):
        pass

    # 指数日线行情
    @post_query
    def index_daily(self, index_code, start_date, end_date):
        pass

    # 返回指数包含的股票
    @post_query
    def index_weight(self, index_code, start_date):
        pass

    # 获得财务数据
    @post_query
    def fina_indicator(self, stock_code, start_date, end_date):
        pass

    @post_query
    def trade_cal(self, start_date, end_date, exchange='SSE'):
        pass
