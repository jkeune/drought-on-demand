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
import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.colors import BoundaryNorm
from mpl_toolkits.basemap import Basemap
#from mpl_toolkits.basemap import shiftgrid

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


def plot_precip_timeseries(sdate, precip, title, ylabel='P [mm month-1]'):
    plt.figure(figsize=(12,4))
    plt.plot(sdate, precip)
    plt.ylabel(ylabel)
    plt.title(title)
    plt.show()

def plot_spi_timeseries(sdate, spi, title, new=True):
    if new:
        plt.figure(figsize=(12,8))
    plt.plot(sdate, spi, color='black')
    # hard-coded thresholds for SPI
    plt.axhline(y = 0, color = 'grey', linestyle = '-')
    plt.axhline(y = -1, color = 'red', linestyle = ':')
    plt.axhline(y = -1.5, color = 'red', linestyle = '-.')
    plt.axhline(y = -2, color = 'red', linestyle = '--')
    plt.axhline(y = 1, color = 'blue', linestyle = ':')
    plt.axhline(y = 1.5, color = 'blue', linestyle = '-.')
    plt.axhline(y = 2, color = 'blue', linestyle = '--')
    plt.ylabel('SPI')
    plt.title(title)
    plt.show()

def create_diverging_colorscheme(colorscheme_name, start_color=(102/255, 51/255, 0), mid_color=(1, 1., 1), end_color=(51/255, 102/255, 0), levels=range(10), levels4pcolormesh=True):
    # start_color, mid_color, end_color should be triples from 0-1, e.g., (1, 1., 1) is white
    assert len(levels) % 2 == 0, 'N levels must be even.'
    cmap = colors.LinearSegmentedColormap.from_list(name=colorscheme_name,
                                                 colors =[start_color,#(0, 0, 1),
                                                          mid_color,
                                                          end_color],#(1, 0, 0)],
                                                 N=len(levels)-1)
    if levels4pcolormesh:
        return cmap, BoundaryNorm(levels, ncolors=len(levels)-1, clip=True)
    else:
        return cmap, levels

def plot_droughtmap(grid_lon, grid_lat, map_2d,
        plot_type = "contourf",
        xlim=[-180,180], ylim=[-90,90], zlim=[-3,3],
        xlab="longitude ["+chr(176)+"]", ylab="latitude ["+chr(176)+"]", main_title="",
        legend_title="", colorscheme=None, levels=None, legend_ticks=None, legend_ticklabels=None,
        dfigsize=(10,10), figname="dummy.png"):

    fig = plt.figure(figsize=dfigsize)

    # adjust limits for plotting
    map_2d[map_2d <= zlim[0]] = zlim[0]
    map_2d[map_2d >= zlim[1]] = zlim[1]

    # basemap
    m = Basemap(projection='cyl', llcrnrlon=-180, \
        urcrnrlon=180.,llcrnrlat=grid_lat.min(),urcrnrlat=grid_lat.max(), \
        resolution='c')
    x, y = m(grid_lon, grid_lat)

    m.drawcoastlines()
    #m.fillcontinents()
    m.drawmapboundary()
    m.drawcountries()
    #m.shadedrelief()
    #m.drawrivers()
    #m.drawlsmask()

    if plot_type == "contourf":
        ax1 = m.contourf(x, y, map_2d, cmap=colorscheme, levels=levels)
    if plot_type == "pcolormesh":
        ax1 = m.pcolormesh(x, y, map_2d, shading='auto', cmap=colorscheme, norm=levels)

    plt.xlim(xlim)
    plt.xlabel(xlab)
    plt.ylim(ylim)
    plt.ylabel(ylab)
    plt.title(main_title)

    cbar = plt.colorbar(ax1, orientation='vertical', shrink=0.85)
    cbar.ax.set_title(legend_title)
    if legend_ticks is not None:
        cbar.set_ticks(legend_ticks)
    if legend_ticklabels is not None:
        cbar.set_ticklabels(legend_ticklabels)

    plt.savefig(figname, dpi='figure', format=None, metadata=None,
                bbox_inches=None, pad_inches=0.1,
                facecolor='auto', edgecolor='auto',
                backend=None)
    plt.show()

