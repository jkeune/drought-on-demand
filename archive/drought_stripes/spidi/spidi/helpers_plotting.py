# (C) Copyright 1996- ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.

import matplotlib.pyplot as plt
import matplotlib.colors as colors

def plot_precip_timeseries(sdate, precip, title):
    plt.figure(figsize=(12,4))
    plt.plot(sdate, precip)
    plt.ylabel('P [mm month-1]')
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
