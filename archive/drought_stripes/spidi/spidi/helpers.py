# (C) Copyright 1996- ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.

from itertools import groupby
import numpy as np
import calendar

def days_in_month(date):
    yyyy = date.strftime('%Y')
    m = date.strftime('%-m')
    ndays = calendar.monthrange(int(yyyy), int(m))[1]
    return ndays

def convert_mmperday_to_mmpermonth(dfdata, ncols):
    ndays = (dfdata.index.to_series()).apply(days_in_month)
    for icol in ncols:
        dfdata[icol] = ndays * dfdata[icol]
    return dfdata

def count_events(index, thresh_min, thresh_max):
    # returns integer indicating the number of events in list
    # events defined by min and max thresholds
    count = len([i for i in index if i < thresh_max and i > thresh_min])
    return count

def identify_events(index, thresh_min, thresh_max):
    # returns list of 0,1, with 0 indicating no-event and 1 being an event
    events = [ int( (thresh_min < x < thresh_max) == 1 ) for x in index ]
    return events

def sum_dict_lists(idict):
    # returns a list that contains an element-wise sum of all key-lists in a dictionary
    # [2 4 6] = {a:[1 2 3], b:[1 2 3]}
    sum_list = [0]*len(idict[list(idict.keys())[0]])
    for name, x in idict.items():
        sum_list = [a + b for a, b in zip(sum_list, x)]
    return sum_list

def get_event_duration(ilist, val=1):
    # counts consecutive occurrences of event (defined by val) and returns a list of length of events
    lengths = []
    for v, group in groupby(ilist):
        if v==val:
            lengths.append(sum(1 for x in list(group)))
    return lengths

def count_occurrences(ilist):
    # counts number of occurrences of unique numbers and returns a dict
    rdict = {}
    for uniques in set(ilist):
        rdict[uniques] = ilist.count(uniques)
    return rdict

def area_in_drought(spi_2d, thresh_min=-9999, thresh_max=-1.0):
    # input array of SPI values with dimension date x points, here calculating proportion over points
    # attn, hardcoded axes
    in_drought   = spi_2d.apply(lambda x: identify_events(x, thresh_min, thresh_max), axis=0)
    p_in_drought = 100 * np.sum(in_drought, axis=1) /  (in_drought.shape[1])
    return p_in_drought


