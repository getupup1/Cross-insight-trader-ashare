import pandas as pd
import numpy as np

from pyfolio import timeseries
import pyfolio
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from copy import deepcopy

from preprocessor.tusharedownloader import Tushareloader
import config


def get_daily_return(df, value_col_name="account_value"):
    df = deepcopy(df)
    df["daily_return"] = df[value_col_name].pct_change(1)
    df["date"] = pd.to_datetime(df["date"])
    df.set_index("date", inplace=True, drop=True)
    df.index = df.index.tz_localize("UTC")
    return pd.Series(df["daily_return"], index=df.index)

def convert_daily_return_to_pyfolio_ts(df):
    strategy_ret= df.copy()
    strategy_ret['date'] = pd.to_datetime(strategy_ret['date'])
    strategy_ret.set_index('date', drop = False, inplace = True)
    strategy_ret.index = strategy_ret.index.tz_localize('UTC')
    del strategy_ret['date']
    ts = pd.Series(strategy_ret['daily_return'].values, index=strategy_ret.index)
    return ts

def backtest_stats(account_value, value_col_name="account_value"):
    dr_test = get_daily_return(account_value, value_col_name=value_col_name)
    perf_stats_all = timeseries.perf_stats(
        returns=dr_test,
        positions=None,
        transactions=None,
        turnover_denom="AGB",
    )
    print(perf_stats_all)
    return perf_stats_all


def backtest_plot(
    account_value,
    baseline_start=config.START_TRADE_DATE,
    baseline_end=config.END_DATE,
    baseline_ticker="^DJI",
    value_col_name="account_value",
):

    df = deepcopy(account_value)
    test_returns = get_daily_return(df, value_col_name=value_col_name)

    baseline_df = get_baseline(
        ticker=baseline_ticker, start=baseline_start, end=baseline_end
    )

    baseline_returns = get_daily_return(baseline_df, value_col_name="close")
    with pyfolio.plotting.plotting_context(font_scale=1.1):
        pyfolio.create_full_tear_sheet(
            returns=test_returns, benchmark_rets=baseline_returns, set_context=False
        )


def get_baseline(dataset, ticker, start, end):
    dji = Tushareloader(
        portfolio_name='baseline',
        start_date=start, 
        end_date=end, 
        ticker_list=[ticker]
    ).fetch_data()
    return dji


def trx_plot(df_trade,df_actions,ticker_list):    
    df_trx = pd.DataFrame(np.array(df_actions['transactions'].to_list()))
    df_trx.columns = ticker_list
    df_trx.index = df_actions['date']
    df_trx.index.name = ''
    
    for i in range(df_trx.shape[1]):
        df_trx_temp = df_trx.iloc[:,i]
        df_trx_temp_sign = np.sign(df_trx_temp)
        buying_signal = df_trx_temp_sign.apply(lambda x: True if x>0 else False)
        selling_signal = df_trx_temp_sign.apply(lambda x: True if x<0 else False)
        
        tic_plot = df_trade[(df_trade['tic']==df_trx_temp.name) & (df_trade['date'].isin(df_trx.index))]['close']
        tic_plot.index = df_trx_temp.index

        plt.figure(figsize = (10, 8))
        plt.plot(tic_plot, color='g', lw=2.)
        plt.plot(tic_plot, '^', markersize=10, color='m', label = 'buying signal', markevery = buying_signal)
        plt.plot(tic_plot, 'v', markersize=10, color='k', label = 'selling signal', markevery = selling_signal)
        plt.title(f"{df_trx_temp.name} Num Transactions: {len(buying_signal[buying_signal==True]) + len(selling_signal[selling_signal==True])}")
        plt.legend()
        plt.gca().xaxis.set_major_locator(mdates.DayLocator(interval=25)) 
        plt.xticks(rotation=45, ha='right')
        plt.show()


def plot_csv_vs_baseline(csv_path, baseline_df=None, baseline_ticker=None, save_path="results/cumulative_comparison.png"):
    """
    读取 CSV 并与 Baseline 对比
    :param baseline_df: 外部传入的基准数据 (DataFrame)，如果传入则不重新下载
    :param baseline_ticker: 如果 baseline_df 为 None，则根据此代码下载
    """
    # 1. 读取 Agent CSV 文件
    print(f"Loading agent data from {csv_path}...")
    df_agent = pd.read_csv(csv_path)
    
    # 格式清洗
    if 'date' not in df_agent.columns:
        # 尝试推断列名
        if len(df_agent.columns) >= 3:
            df_agent.rename(columns={df_agent.columns[1]: 'date', df_agent.columns[2]: 'daily_return'}, inplace=True)
            
    df_agent['date'] = pd.to_datetime(df_agent['date'])
    df_agent.set_index('date', inplace=True)
    
    # 计算复利
    agent_cumulative = (1 + df_agent['daily_return'].fillna(0)).cumprod()

    # 2. 获取 Baseline 数据 (复用逻辑)
    if baseline_df is None:
        # 如果没传数据，才去下载 (兼容旧逻辑)
        if baseline_ticker is None:
            raise ValueError("Must provide either baseline_df or baseline_ticker!")
            
        print(f"Downloading baseline data for {baseline_ticker}...")
        from preprocessor.yahoodownloader import YahooDownloader # 或 Tushareloader
        start_date = df_agent.index.min().strftime("%Y-%m-%d")
        end_date = df_agent.index.max().strftime("%Y-%m-%d")
        
        baseline_loader = YahooDownloader(
            portfolio_name="baseline_temp",
            start_date=start_date,
            end_date=end_date,
            ticker_list=[baseline_ticker]
        )
        df_baseline = baseline_loader.fetch_data()
        df_baseline = df_baseline[df_baseline.tic == baseline_ticker].copy()
    else:
        # 【关键点】如果传入了数据，直接使用
        print("Using provided baseline dataframe...")
        df_baseline = baseline_df.copy()

    # 3. 处理 Baseline 数据格式
    # 确保是 datetime 索引
    if 'date' in df_baseline.columns:
        df_baseline['date'] = pd.to_datetime(df_baseline['date'])
        df_baseline.set_index('date', inplace=True)
    
    # 重新计算基准收益 (防止传入的数据没有 daily_return 列)
    if 'daily_return' not in df_baseline.columns:
        df_baseline['daily_return'] = df_baseline['close'].pct_change().fillna(0)
        
    baseline_cumulative = (1 + df_baseline['daily_return']).cumprod()

    # 4. 对齐与绘图
    df_plot = pd.DataFrame({
        'Agent Strategy': agent_cumulative,
        'Baseline': baseline_cumulative
    }).dropna()

    plt.figure(figsize=(12, 6))
    plt.plot(df_plot.index, df_plot['Agent Strategy'], label='Agent Strategy', color='red', linewidth=1.5)
    plt.plot(df_plot.index, df_plot['Baseline'], label='Baseline', color='blue', linewidth=1.5)
    
    plt.title('Cumulative Return Comparison (Compound)')
    plt.xlabel('Date')
    plt.ylabel('Net Value (Initial=1.0)')
    plt.legend(loc='best')
    plt.grid(True, alpha=0.3)
    plt.gcf().autofmt_xdate()
    
    plt.savefig(save_path)
    print(f"Comparison plot saved to {save_path}")
    plt.close()