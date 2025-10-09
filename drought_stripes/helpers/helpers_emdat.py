# (C) Copyright 1996- ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.

import pandas as pd
from dateutil import relativedelta

def fix_column_names(df):
    # remove special characters from column names
    df.columns = df.columns.str.replace("\'000 US\$", '1000 USD', regex=True)

def fix_nan2int(df):
    # handle additional columns that are supposedly integer but have missing values individually; due to issues with NaN in pandas: https://pandas.pydata.org/pandas-docs/stable/user_guide/gotchas.html
    for icolumn in ['Total Deaths', 'No Injured', 'No Affected', 'No Homeless', 'Total Affected',
                    'Reconstruction Costs (1000 USD)', 'Reconstruction Costs, Adjusted (1000 USD)', 'Insured Damages (1000 USD)',
                    'Insured Damages, Adjusted (1000 USD)', 'Total Damages (1000 USD)', 'Total Damages, Adjusted (1000 USD)']:
        df[icolumn] = df[icolumn].fillna(0)
        df[icolumn] = df[icolumn].astype(int)

def fill_unknown_duration(df):
    # set nan to 1 and 12 for start and end month, respectively
    df['Start Month']   = df['Start Month'].fillna(1)
    df['Start Month']   = df['Start Month'].astype(int)
    df['End Month']     = df['End Month'].fillna(12)
    df['End Month']     = df['End Month'].astype(int)

def convert2datetime(df):
    # add leading zero to all months
    df['Start Month']   = df['Start Month'].astype(str).str.zfill(2)
    df['End Month']     = df['End Month'].astype(str).str.zfill(2)
    # create datetime object for start and end dates
    df['start_date']    = df[ ['Start Year','Start Month'] ].apply(lambda x: '-'.join(x.values.astype(str)), axis="columns")
    df['start_date']    = pd.to_datetime(df['start_date'])
    df['end_date']      = df[ ['End Year','End Month'] ].apply(lambda x: '-'.join(x.values.astype(str)), axis="columns")
    df['end_date']      = pd.to_datetime(df['end_date'])

def adjust_dates(df, log_unknown=True):
    # handle unknown start/end months: log unknowns and then set start=1 and end=12
    if log_unknown:
        df['start_unknown'] = df['Start Month'].isna().astype(int)
        df['end_unknown'] = df['End Month'].isna().astype(int)
    # set nan to 1 and 12 for start and end month, respectively   
    fill_unknown_duration(df)
    # convert to datetime objects
    convert2datetime(df)

def calculate_duration_months(df):
    duration_months  = []
    for i in range(len(df['start_date'])):
        duration_months.append( relativedelta.relativedelta(df['end_date'][i], df['start_date'][i]).years * 12 +
                                relativedelta.relativedelta(df['end_date'][i], df['start_date'][i]).months + 1 ) # adding one month, because always working with first day
    df['duration_months'] = duration_months

def df2ts(df, colnames, colname_start='start_date', colname_end='end_date', fill_value=0, **kwargs):
    ts_df = pd.DataFrame({'time': pd.date_range(df[colname_start].min(), df[colname_end].max(), **kwargs)})
    df_ts = ts_df.merge(df, how='left', left_on='time', right_on=colname_start).fillna(method='pad')
    df_ts.loc[(df_ts.time < df_ts[colname_start]) | (df_ts.time > df_ts[colname_end]), colnames] = fill_value
    # issue if one (short) event is defined within a longer event; then the value of the short event is used for the remaining long event...
    return df_ts

def list_of_unique_values(df, colnames):
    uvals = pd.concat([df[col] for col in colnames]).dropna().unique().tolist()
    return uvals

def legend_without_duplicate_labels(ax, **kwargs):
    handles, labels = ax.get_legend_handles_labels()
    unique = [(h, l) for i, (h, l) in enumerate(zip(handles, labels)) if l not in labels[:i]]
    ax.legend(*zip(*unique), **kwargs)

def plot_events_background(ax, events_df, color='lightgrey', **kwargs):
    for ievent in range(events_df.shape[0]):
        # get dates, including full end month
        edate = pd.date_range( events_df['start_date'].iloc[ievent], events_df['end_date'].iloc[ievent] + relativedelta.relativedelta(months=1, day=1), freq='MS', **kwargs )
        # background shading
        ax.axvspan(edate[0], edate[-1], facecolor=color, alpha=1)
