import os 
import sys
import netCDF4 as nc4
import numpy as np
import xarray as xr
import cartopy.crs as ccrs
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
import matplotlib.pyplot as plt
import cartopy.feature
#import cartopy.io.shapereader as shapereader
from cartopy.io import shapereader
import cartopy
import cartopy.feature as feature

mylevels     = [-10000,-1000,-2,-1.5,-1,1,1.5,2,1000]
mycollisthex = ['#bebebe','#663300','#8c6640','#b29980','#ffffff','#99b280','#668c40','#336600']
legnames     = ["masked","extremely dry", "severely dry", "moderately dry", "near normal", "moderately wet", "severely wet", "extremely wet"]

def hex2rgb(hexs):
   return tuple(int(hexs[i:i+2], 16)/255 for i in (0, 2, 4))

countries = shapereader.natural_earth(resolution='110m',
                              category='cultural',
                              name='admin_0_countries')


def worldmap_drought(
    data_2d,
    collist_hex,
    levels,
    legnames,
    plot_borders=False,
    highlight_countries=[],
    myextent=[-170000, 180, -50, 82],  # [x0, x1, y0, y1]
    figx=9, figy=4,
    figname="figures/SPEI12_global_19000000.png",
    latlines=[-30, 30],
    plot_latlines=False,
    mytitle="",
    subtitle=""
):
    """
    Plot a drought map in Robinson projection with customizable title and subtitle.

    Parameters
    ----------
    data_2d : xarray.DataArray or similar
        Gridded data containing 'lat' and 'lon' coordinates.
    collist_hex : list
        List of color hex codes.
    levels : list
        Contour/level boundaries for plotting.
    legnames : list
        Labels for the legend.
    plot_borders : bool
        Whether to draw national borders.
    highlight_countries : list
        Names of countries to outline in black.
    myextent : list
        Map extent [x0, x1, y0, y1].
    figx, figy : float
        Figure size in inches.
    figname : str
        Output filename for the saved figure.
    plot_latlines : bool
        Whether to draw horizontal reference lines.
    mytitle : str
        Main title (bold).
    subtitle : str
        Optional smaller subtitle.
    """

    # --- Font setup ---
    plt.rcParams["font.family"] = "Arial"
    #plt.rcParams["font.family"] = "Helvetica"
    plt.rcParams["font.size"] = 10

    # --- Figure setup ---
    plt.figure(figsize=(figx, figy))
    ax = plt.axes(projection=ccrs.Robinson(), frameon=False)
    ax.coastlines(color="black", lw=0.25)

    # --- Plot data ---
    data_2d.plot(
        ax=ax,
        transform=ccrs.PlateCarree(),
        x="lon", y="lat",
        add_colorbar=False,
        colors=collist_hex,
        levels=levels,
        vmin=-3, vmax=3,
    )

    # --- Titles ---
    if mytitle:
        plt.title(mytitle, fontsize=14, fontweight="bold", loc="center", pad=6)
    if subtitle:
        plt.suptitle(subtitle, fontsize=10, fontweight="normal", y=0.92)

    # --- Optional latitude lines ---
    if plot_latlines:
        geodetic = ccrs.Geodetic()
        robinson = ccrs.Robinson()
        for ilat in latlines:
            ilon_1, ilat_1 = robinson.transform_point(-179, ilat, geodetic)
            ilon_2, ilat_2 = robinson.transform_point(+179, ilat, geodetic)
            ax.plot(
                [ilon_1, ilon_2], [ilat_1, ilat_2],
                color="grey", linewidth=0.5, transform=robinson, linestyle=":"
            )

    # --- Borders and highlighted countries ---
    ax.set_extent(myextent)
    if plot_borders:
        ax.add_feature(cartopy.feature.BORDERS, color="black", lw=0.3)
    if highlight_countries:
        countries = shapereader.natural_earth(resolution="110m", category="cultural", name="admin_0_countries")
        for country in shapereader.Reader(countries).records():
            if country.attributes["ADMIN"] in highlight_countries:
                ax.add_geometries(
                    [country.geometry],
                    edgecolor="black",
                    facecolor="none",
                    linewidth=0.85,
                    crs=ccrs.PlateCarree(),
                )

    # --- Legend ---
    legend_elements = [
        Line2D([0], [0], marker="s", color="w", label=legnames[i],
               markerfacecolor=collist_hex[i], markersize=8)
        for i in range(len(legnames))
    ]
    plt.legend(handles=legend_elements, fontsize="8", loc="lower left", ncol=1)

    plt.tight_layout()
    plt.savefig(
        figname,
        dpi=300,
        bbox_inches="tight",
        pad_inches=0.1,
    )
    plt.show()


##############
## MAIN
##############

yyyy      = 2025
mm        = "09"

ref_syyyy = 1991
ref_eyyyy = 2020
dataset   = "era5t"
stream    = "moda"

for indicator in ["SPI", "SPEI"]:
    #indicator = "SPEI"
    #indicator = "SPI"

    for window in [1,3,6,12,24,36,48]:

        if indicator == "SPEI":
            distribut = "genlogistic"
        if indicator == "SPI":
            distribut = "gamma"

        ifile_name= f"{indicator}{window}_{distribut}_global_{dataset}_{stream}_ref{ref_syyyy}to{ref_eyyyy}_{yyyy}{str(mm).zfill(2)}.nc"
        ipath     = f"/ec/ws4/tc/emos/work/cems/dryfall/emos/dryfall_monthly/ens/runs/era5t/{yyyy}{mm}01/hr"
        ifile     = f"{ipath}/{ifile_name}"
        print(ifile)

        drought_2d = xr.open_dataset(ifile)
        drought_2d_masked = xr.where(drought_2d[f'{indicator}{window}'] == -9999, np.nan, drought_2d[f'{indicator}{window}'])

        vfile = "/home/nejk/code/dryfall_oper/helpers_oper/barren_mask.nc"
        bmask = xr.open_dataset(vfile)
        drought_2d_masked = xr.where( (bmask['barren_mask'][0,:,:] == 1) & (~np.isnan(drought_2d_masked)) , -9999, drought_2d_masked)


        worldmap_drought(drought_2d_masked, 
                 collist_hex = mycollisthex, 
                 levels = [-10000,-1000,-2,-1.5,-1,1,1.5,2,1000],
                 legnames = ["masked","extremely dry", "severely dry", "moderately dry", 
                             "near normal", "moderately wet", "severely wet", "extremely wet"],
                 plot_borders=False,
                 myextent = [-170000, 180, -50, 82], # (x0, x1, y0, y1)
                 #figname = f"figures/{indicator}{window}_Global_map.pdf",
                 figname = f"figures/{indicator}{window}_Global_map.png",
                 latlines = [-30,30], 
                 plot_latlines =False, 
                 mytitle       = f"State of drought, Global | {indicator}-{window}",
                 subtitle      = f"Update {yyyy}-{mm}")

        worldmap_drought(drought_2d_masked, 
                 collist_hex = mycollisthex, 
                 levels = [-10000,-1000,-2,-1.5,-1,1,1.5,2,1000],
                 legnames = ["masked","extremely dry", "severely dry", "moderately dry", 
                             "near normal", "moderately wet", "severely wet", "extremely wet"],
                 plot_borders=False,
                 myextent = [-130000, 60, 30, 72],# (x0, x1, y0, y1)
                 #figname = f"figures/{indicator}{window}_Europe_map.pdf",
                 figname = f"figures/{indicator}{window}_Europe_map.png",
                 latlines = [-30,30], 
                 plot_latlines =False, 
                 mytitle       = f"State of drought, Europe | {indicator}-{window}",
                 subtitle      = f"Update {yyyy}-{mm}")

