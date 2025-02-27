# (C) Copyright 1996- ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.

import matplotlib.pyplot as plt
import matplotlib.colors as colors
from matplotlib.colors import BoundaryNorm
from mpl_toolkits.basemap import Basemap
#from mpl_toolkits.basemap import shiftgrid

def hex2rgb(hexs):
   return tuple(int(hexs[i:i+2], 16)/255 for i in (0, 2, 4))


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

    #plt.axis('off')
  
    fig = plt.figure(figsize=dfigsize, frameon=False)
    #fig.patch.set_visible(False)
    #for spine in plt.gca().spines.values():
    #    spine.set_visible(False)    
          
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
    #plt.title(main_title)
    plt.text(.01, .01, main_title,
             horizontalalignment='left',
             verticalalignment='bottom',
             size = 15,
             transform = plt.gca().transAxes)

    cbar = plt.colorbar(ax1, orientation='vertical', shrink=0.85)
    cbar.ax.set_title(legend_title)
    if legend_ticks is not None:
        cbar.set_ticks(legend_ticks)
    if legend_ticklabels is not None:
        cbar.set_ticklabels(legend_ticklabels)

    plt.savefig(figname, format=None, metadata=None,
                bbox_inches=None, pad_inches=0.1, dpi=300,
                facecolor='auto', edgecolor='auto',
                backend=None, frameon=False)
    plt.show()
