"""Contains methods and classes to collect data from
Yahoo Finance API
"""
import os
import pandas as pd
import sys
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config
import tushare as ts

class Tushareloader:
    """Provides methods for retrieving daily stock data from
    Yahoo Finance API

    Attributes
    ----------
        start_date : str
            start date of the data (modified from config.py)
        end_date : str
            end date of the data (modified from config.py)
        ticker_list : list
            a list of stock tickers (modified from config.py)

    Methods
    -------
    fetch_data()
        Fetches data from yahoo API

    """

    def __init__(self, portfolio_name: str, start_date: str, end_date: str, ticker_list: list):

        self.portfolio_name = portfolio_name
        self.start_date = start_date
        self.end_date = end_date
        self.ticker_list = ticker_list
        ts.set_token(config.TUSHARE_TOKEN)
        self.pro = ts.pro_api()

    def fetch_data(self) -> pd.DataFrame:
        """Fetches data from Yahoo API
        Parameters
        ----------

        Returns
        -------
        `pd.DataFrame`
            7 columns: A date, open, high, low, close, volume and tick symbol
            for the specified stock ticker
        """
        # Download and save the data in a pandas DataFrame:
        data_df = pd.DataFrame()
        portfolio_save_path = "./data_ashare" + '/' + self.portfolio_name
        if os.path.exists(portfolio_save_path) and len(os.listdir(portfolio_save_path)) > 0:
            standard_file = pd.read_csv(portfolio_save_path + '/' + self.ticker_list[0] + '.csv',index_col=False)
            standard_date = pd.to_datetime(standard_file['date'], errors='coerce')
            dfs = []
            for tic in self.ticker_list:
                temp_df = pd.read_csv(portfolio_save_path + '/' + tic + '.csv',index_col=False)
                temp_df["tic"] = tic
                condition1 = temp_df['date']>=self.start_date
                condition2 = temp_df['date']<=self.end_date
                temp_df = temp_df[condition1 & condition2]
                temp_df['date'] = pd.to_datetime(temp_df['date'], errors='coerce')
                temp_df = pd.merge(standard_date, temp_df, how='left', on="date")
                temp_df = temp_df.ffill().bfill()
                temp_df.set_index('date',inplace=True)
                dfs.append(temp_df)
            data_df = pd.concat(dfs)
        else:
            save_path = "./data_ashare/" + self.portfolio_name
            if not os.path.exists(save_path):
                os.makedirs(save_path)
            ts_start_date = self.start_date.replace('-', '')
            ts_end_date = self.end_date.replace('-', '')
            dfs = []
            INDEX_CODES = ["000016.SH", "000300.SH", "000001.SH"]
            for tic in self.ticker_list:
                is_index = tic in INDEX_CODES
                if is_index:
                    # 指数接口
                    df_tic = self.pro.index_daily(ts_code=tic, start_date=ts_start_date, end_date=ts_end_date)
                    if df_tic is not None and not df_tic.empty:
                        df_tic = df_tic.rename(columns={
                            'trade_date': 'trade_date',
                            'open': 'open',
                            'high': 'high',
                            'low': 'low',
                            'close': 'close',
                            'amount': 'vol'  # 指数用 amount 表示成交量
                        })
                else:
                    df_tic = ts.pro_bar(
                            ts_code=tic, 
                            api=self.pro, 
                            adj='qfq', 
                            start_date=ts_start_date, 
                            end_date=ts_end_date
                        )
                df_tic = df_tic.sort_values('trade_date').reset_index(drop=True)
                df_tic = df_tic.rename(columns={
                        'trade_date': 'date',
                        'open': 'open',
                        'high': 'high',
                        'low': 'low',
                        'close': 'close',
                        'vol': 'volume'
                    })
                df_tic['date'] = pd.to_datetime(df_tic['date'], format='%Y%m%d')
                output_columns = ['date', 'open', 'high', 'low', 'close', 'volume']
                df_save = df_tic[output_columns].copy()
                csv_file_path = f"{save_path}/{tic}.csv"
                df_save.to_csv(csv_file_path, index=False)
                df_save['tic'] = tic
                df_save.set_index('date', inplace=True) 
                dfs.append(df_save)
            data_df = pd.concat(dfs)

        # exit()
        # reset the index, we want to use numbers as index instead of dates
        # print(data_df.head(5))
        if data_df.index.name is not None:
            data_df = data_df.reset_index()  # 有名字的索引（如'date'）转为列
        else:
            data_df = data_df.reset_index(drop=True)
        # print(temp_df.head(5))
       
        # create day of the week column (monday = 0)
        data_df["day"] = data_df["date"].dt.dayofweek
        # convert date to standard string format, easy to filter
        data_df["date"] = data_df.date.apply(lambda x: x.strftime("%Y-%m-%d"))
        # drop missing data
        data_df = data_df.dropna()
        data_df = data_df.reset_index(drop=True)
        print("Shape of DataFrame: ", data_df.shape)
        # print("Display DataFrame: ", data_df.head())

        data_df = data_df.sort_values(by=['date','tic']).reset_index(drop=True)


        return data_df

    def select_equal_rows_stock(self, df):
        df_check = df.tic.value_counts()
        df_check = pd.DataFrame(df_check).reset_index()
        df_check.columns = ["tic", "counts"]
        mean_df = df_check.counts.mean()
        equal_list = list(df.tic.value_counts() >= mean_df)
        names = df.tic.value_counts().index
        select_stocks_list = list(names[equal_list])
        df = df[df.tic.isin(select_stocks_list)]
        return df
    
if __name__ == "__main__":
    TEST_TICKERS = ["000016.SH", "000300.SH", "000001.SH"]
    df = Tushareloader(
            portfolio_name='baseline',
            start_date=config.START_DATE,
            end_date=config.END_DATE,
            ticker_list=TEST_TICKERS,
        ).fetch_data()
    # df.to_csv("test_tushare_data2.csv", index=False)