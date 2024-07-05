"""
这个使用B站UP主的数据源导入后的mysql进行访问
"""
import logging
import time

import pandas as pd

from mfm_learner.datasource.datasource import DataSource, post_query
from mfm_learner.datasource.impl.tushare_datasource import TushareDataSource
from mfm_learner.utils import utils, logging_time, db_utils

logger = logging.getLogger(__name__)


class DatabaseDataSource(DataSource):
    def __init__(self):
        self.db_engine = utils.connect_db()
        self.tushare = TushareDataSource()

    # 返回每日行情数据，不限字段
    def __daliy_one(self, stock_code, start_date=None, end_date=None):
        if start_date is None or end_date is None:
            df = pd.read_sql(
                f'select * from daily_hfq where ts_code="{stock_code}"',
                self.db_engine)
            return df
        else:
            df = pd.read_sql(
                f'select * from daily_hfq where ts_code="{stock_code}" and trade_date>="{start_date}" and trade_date<="{end_date}"',
                self.db_engine)
            return df

    def __daily_batch(self, stock_codes, start_date=None, end_date=None):
        # Convert the list of stock codes into a format suitable for SQL IN clause
        stock_codes_str = ', '.join([f'"{code}"' for code in stock_codes])

        # Construct the SQL query based on whether start_date and end_date are provided
        if start_date is None or end_date is None:
            query = f'select * from daily_hfq where ts_code IN ({stock_codes_str})'
        else:
            query = f'select * from daily_hfq where ts_code IN ({stock_codes_str}) and trade_date>="{start_date}" and trade_date<="{end_date}"'

        # Execute the query and return the result
        df = pd.read_sql(query, self.db_engine)
        return df
    @post_query
    def daily(self, stock_code, start_date=None, end_date=None):
        if type(stock_code) == list:
            df_all = None
            start_time = time.time()
            df_all = []
            df_all = self.__daily_batch(stock_code, start_date, end_date)
            logger.debug("获取 %s ~ %s %d 只股票的交易数据：%d 条, 耗时 %.2f 秒",
                         start_date, end_date, len(stock_code), len(df_all), time.time() - start_time)
            return df_all
        else:
            df_one = self.__daliy_one(stock_code, start_date, end_date)
            logger.debug("获取 %s ~ %s 股票[%s]的交易数据：%d 条", start_date, end_date, stock_code, len(df_one))
            return df_one

    @logging_time
    @post_query
    def daily_basic(self, stock_code, start_date, end_date):
        assert type(stock_code) == list or type(stock_code) == str, type(stock_code)
        if type(stock_code) == list:
            start_time = time.time()
            df = self._daily_basic_batch(stock_code, start_date, end_date)
            logger.debug("获取%d只股票的每日基本信息数据%d条，耗时 : %.2f秒", len(stock_code), len(df), time.time() - start_time)
            # print(df_basics)
            return df
        return self.__daily_basic_one(stock_code, start_date, end_date)

    def __daily_basic_one(self, stock_code, start_date, end_date):
        """返回每日的其他信息，主要是市值啥的"""
        df = pd.read_sql(
            f'select * from daily_basic \
                where ts_code="{stock_code}" and trade_date>="{start_date}" and trade_date<="{end_date}"',
            self.db_engine)
        return df

    def _daily_basic_batch(self, stock_codes, start_date, end_date):
        # Convert the list of stock codes into a format suitable for SQL IN clause
        stock_codes_str = ', '.join([f'"{code}"' for code in stock_codes])
        # Construct the SQL query based on whether start_date and end_date are provided
        query = f'select * from daily_basic where ts_code IN ({stock_codes_str}) and trade_date>="{start_date}" and trade_date<="{end_date}"'
        # Execute the query and return the result
        df = pd.read_sql(query, self.db_engine)
        return df

    # 指数日线行情
    @post_query
    def index_daily(self, index_code, start_date, end_date):
        df = pd.read_sql(
            f'select * from index_daily \
                where ts_code="{index_code}" and trade_date>="{start_date}" and trade_date<="{end_date}"',
            self.db_engine)
        return df

    # 返回指数包含的股票
    @post_query
    def index_weight(self, index_code, start_date, end_date):
        df = pd.read_sql(
            f'select * from index_weight \
                where index_code="{index_code}" and trade_date>="{start_date}" and trade_date<="{end_date}"',
            self.db_engine)
        return df['con_code'].unique().tolist()

    # 获得财务数据
    @post_query
    def fina_indicator(self, stock_code, start_date, end_date):
        stock_codes = db_utils.list_to_sql_format(stock_code)
        df = pd.read_sql(
            f'select * from fina_indicator \
                where ts_code in ({stock_codes}) and ann_date>="{start_date}" and ann_date<="{end_date}"', self.db_engine)
        return df

    # 获得现金流量
    @post_query
    def income(self, stock_code, start_date, end_date):
        stock_codes = db_utils.list_to_sql_format(stock_code)
        df = pd.read_sql(
            f'select * from income \
                where ts_code in ({stock_codes}) and ann_date>="{start_date}" and ann_date<="{end_date}"', self.db_engine)
        return df

    @post_query
    def trade_cal(self, start_date, end_date, exchange='SSE'):
        df = pd.read_sql(
            f'select * from trade_cal \
                where exchange="{exchange}" and cal_date>="{start_date}" and cal_date<="{end_date}" and is_open=1', self.db_engine)
        return df['cal_date']

    @post_query
    def stock_basic(self, ts_code):
        stock_codes = db_utils.list_to_sql_format(ts_code)
        df = pd.read_sql(f'select * from stock_basic where ts_code in ({stock_codes})', self.db_engine)
        return df

    @post_query
    def index_classify(self, level='', src='SW2014'):
        df = pd.read_sql(f'select * from index_classify where src = \'{src}\'', self.db_engine)
        return df

    @post_query
    def get_factor(self, name, stock_codes, start_date, end_date):
        if not db_utils.is_table_exist(self.db_engine,f"factor_{name}"):
            # raise ValueError(f"因子表factor_{name}在数据库中不存在")
            logger.warning(f"因子表factor_{name}在数据库中不存在")
            return None
        stock_codes = db_utils.list_to_sql_format(stock_codes)
        sql = f"""
            select * 
            from factor_{name} 
            where datetime>=\'{start_date}\' and 
                  datetime<=\'{end_date}\' and
                  code in ({stock_codes})
        """
        df = pd.read_sql(sql,self.db_engine)
        return df

