import pandas as pd
import numpy as np
import scipy.stats as stats
import statsmodels.api as statsmodels
from itertools import groupby

def pointer_distribution(distribution = 'gamma'):
    distr  = getattr(stats, str(distribution))
    return distr

#def count_missing(timeseries):
#    pzeros             = len(np.where(timeseries == 0)[0]) / len(timeseries)       # numpy
#    #pzeros            = (timeseries == 0.0).sum() / (timeseries.notnull()).sum()  # pandas only
#    #pzeros            = (timeseries.isnull()).sum() / len(timeseries)             # pandas only
#    return pzeros

# cdf2ppf
def convert_cdf2ppf(cdfv):
    #cdfv[cdfv > 0.999] = (np.float64(1.0)-(1e-16))
    #cdfv[cdfv < 0.001] = 0.001
    ppfv = stats.norm.ppf(cdfv)
    ppfv[np.isposinf(ppfv)] = stats.norm.ppf(1-(1e-16))
    ppfv[np.isneginf(ppfv)] = stats.norm.ppf((1e-16))
    return ppfv

# fit distribution (ignore nans)
def fit_distribution(timeseries, distr):
    *pars, loc, scale = distr.fit(timeseries)
    #*pars, loc, scale = distr.fit(timeseries.dropna().values) # pandas only
    #pars              = fit_params[:-2]
    #loc               = fit_params[-2]
    #scale             = fit_params[-1]
    return pars, loc, scale

def calc_sse_fit(timeseries, distr, bins=200):
    y, x = np.histogram(timeseries, bins=bins, density=True)
    x = (x + np.roll(x, -1))[:-1] / 2.0
    # Calculate fitted PDF and error with fit in distribution
    pars, loc, scale = fit_distribution(timeseries, distr)
    pdf = distr.pdf(x, loc=loc, scale=scale, *pars)
    sse = np.sum(np.power(y - pdf, 2.0))
    return sse

# calculate cdf values
def calc_cdf(timeseries, distr, pars, loc, scale, pzero_replace, pzero_ref, pzero_center_mass, pzero_ref_adj):
    if pzero_replace:
        # Lloyd-Hughes and Saunders, 2002
        cdfv    = pzero_ref + (1-pzero_ref) * distr.cdf(timeseries, loc=loc, scale=scale, *pars)
        if pzero_center_mass:
            # Stagge et al., 2015 (as Lloyd-Huges and Saunders, 2002, but with a different pzero_ref above, and replacing pzero values with pzero_ref_adj):
            cdfv[timeseries == 0]               = pzero_ref_adj
    else:
        # no adjustments for pzero at all
        cdfv    = distr.cdf(timeseries, loc=loc, scale=scale, *pars)
    return cdfv

def pointer_significance_test(significance_test = 'kstest'):
    try:
        sigtest  = getattr(stats, str(significance_test))
    except:
        sigtest  = getattr(statsmodels.stats.diagnostic, str(significance_test), None)
    return sigtest

# perform significance test
def is_significant(timeseries, sigtest, alpha=0.05, *args):
    # supports: kstest, normaltest, shapiro, lilliefors, anderson, cramervonmises
    if sigtest is None:
        return "NaN"
    else:
        try:
            # kstest, cramervonmises
            pval = sigtest(timeseries, 'norm').pvalue

        except TypeError:
            # normaltest, shapiro
            pval = sigtest(timeseries).pvalue
        except AttributeError:
            try:
                # lilliefors
                _, pval = sigtest(timeseries, dist='norm', pvalmethod='table')
            except:
                # anderson
                s = sigtest(timeseries)
                pval  = s.critical_values[s.significance_level==100*alpha]
                alpha = s.statistic
        if pval > alpha:
            return 1
        else:
            return 0

def check_refdata(dfdata, dfdata_ref):
    if dfdata_ref is None:
        dfdata_ref = dfdata.copy(deep = True) # pandas only
        #dfdata_ref = np.copy(dfdata) # numpy only
    if dfdata.shape[1] != dfdata_ref.shape[1]:
        raise ValueError('Shape mismatch: dfdata and dfdata_ref should have the same shape!')
    else:
        return dfdata_ref

def count_duplicates(datelist):
    return [sum(1 for _ in group) for _, group in groupby(datelist)]

def check_timescale(dates_integration_frequency):
    dups = count_duplicates(list(dates_integration_frequency))
    if any(d > 1 for d in dups):
        raise AttributeError('Data is not at the correct time scale for selected integration frequency')

# main, overarching
def calculate_si(dfdata, dfdata_ref = None, window = 1, distribution = 'gamma', n_events_min = 5, max_zeros = 0.3, remove_zeros = True, pzero_replace = True, pzero_center_mass = True, integration_frequency_string = '%m-%d'):

    assert integration_frequency_string in ['%m', '%m-%d'], "Selected integration frequency currently not supported"

    dfdata_ref    = check_refdata(dfdata, dfdata_ref)

    distr    = pointer_distribution(distribution)

    p_colnames    = list(pd.DataFrame(dfdata).columns.values)

    # initialise empty df with index
    sidata            = pd.DataFrame(index=dfdata.index)

    # loop over columns
    for icol in p_colnames:

        # 1 get column data
        pdata             = dfdata[icol]
        pdata_ref         = dfdata_ref[icol]
        standardised_index= pd.Series(index=dfdata.index, dtype=float)
        
        # timescale check
        check_timescale(pdata.index.strftime(integration_frequency_string))
        check_timescale(pdata_ref.index.strftime(integration_frequency_string))

        # 2 rolling sum
        pdata             = pdata.rolling(window=window, win_type=None, center=False).sum()
        pdata_ref         = pdata_ref.rolling(window=window, win_type=None, center=False).sum()

        # 3 loop over unique dates from dfdata
        unique_dates      = dfdata.index.strftime(integration_frequency_string).unique().tolist()
        for idate in unique_dates:

            ind_dates          = np.where(pdata.index.strftime(integration_frequency_string) == idate)[0]
            ind_dates_ref      = np.where(pdata_ref.index.strftime(integration_frequency_string) == idate)[0]
            timeseries        = np.asarray(pdata[ind_dates])
            timeseries_ref    = np.asarray(pdata_ref[ind_dates_ref])

            # remove zeros
            if remove_zeros:
                ind_include     = np.where( (~np.isnan(timeseries)) )[0] # ATTN, using also 0 here, just for the fit with ref data, we need to neglect 0s?
                ind_include_ref = np.where( (timeseries_ref != 0) & (~np.isnan(timeseries_ref)) )[0]
            else:
                ind_include     = np.where( (~np.isnan(timeseries)) )[0]
                ind_include_ref = np.where( (~np.isnan(timeseries_ref)) )[0]
            
            # pzero calculation; check how many zeros there are
            if pzero_replace:
                if pzero_center_mass:
                    pzero_ref       = 1 - len(ind_include_ref) / (len(timeseries_ref) + 1)
                    pzero_ref_adj   = ( len(timeseries_ref) - len(ind_include_ref) + 1 ) / ( 2 * (len(timeseries_ref) + 1) )
                else:
                    pzero_ref       = 1 - len(ind_include_ref) / len(timeseries_ref)
                    pzero_ref_adj   = np.nan
            else:
                pzero_ref       = np.nan
                pzero_ref_adj   = np.nan

            # fit distribution and calculate CDF values
            if (pzero_ref > max_zeros) or (len(ind_include_ref) < n_events_min):
                standardised_index[ind_dates] = np.asarray([np.nan] * len(timeseries))
            else:

                cdfv = np.asarray([np.nan] * len(timeseries))
                # 4 fit distribution (ignore nans)
                pars, loc, scale = fit_distribution(timeseries_ref[ind_include_ref], distr)
                # 5 calculate cdf values
                cdfv[ind_include] = calc_cdf(timeseries[ind_include], distr, pars, loc, scale, pzero_replace, pzero_ref, pzero_center_mass, pzero_ref_adj)
                #print(cdfv)

                # 6 cdf2ppf
                ppfv = convert_cdf2ppf(cdfv)

                #if np.isinf(ppfv).any():
                #    print("INF value in col "+str(icol)+" and at dates "+str(idate))
                #    print(ppfv)
                #    print(cdfv)
                #    print(timeseries)
                #if np.isnan(ppfv).all():
                #    print("ONLY NAN values in col "+str(icol)+" and at dates "+str(idate))
                #    print(pzeros)
                #if np.isnan(ppfv).any():
                #    print("NAN value in col "+str(icol)+" and at dates "+str(idate))
                #    print(ppfv)
                #    print(cdfv)
                #    print(timeseries)

                # 8 write back to standardised_index, significance_index
                standardised_index[ind_dates] = ppfv

        # write back to dataframe
        ncol  = f"si{window}_{icol}"
        sidata[ncol] = standardised_index

    return sidata

# significance testing (normal distribution of si values during reference period but signed back to dfdata)
def check_significance_si(dfdata, dfdata_ref, window = 1, distribution = 'gamma',  significance_test = 'shapiro', alpha = 0.05, n_events_min = 5, max_zeros = 0.3, remove_zeros = True, pzero_replace = True, pzero_center_mass = True, integration_frequency_string = '%m-%d'):

    assert integration_frequency_string in ['%m', '%m-%d'], "Selected integration frequency currently not supported"

    dfdata_ref    = check_refdata(dfdata, dfdata_ref)

    distr    = pointer_distribution(distribution)
    sigtest  = pointer_significance_test(significance_test)

    p_colnames    = list(pd.DataFrame(dfdata).columns.values)

    # initialise empty df with index
    sidata            = pd.DataFrame(index=dfdata.index)

    # loop over columns
    for icol in p_colnames:

        # 1 get column data
        pdata             = dfdata[icol]
        pdata_ref         = dfdata_ref[icol]
        significance_index= pd.Series(index=dfdata.index, dtype=float) # output of dimension of dfdata
        
        # timescale check
        check_timescale(pdata.index.strftime(integration_frequency_string))
        check_timescale(pdata_ref.index.strftime(integration_frequency_string))

        # 2 rolling sum
        pdata_ref         = pdata_ref.rolling(window=window, win_type=None, center=False).sum()

        # 3 loop over unique dates from dfdata (only time steps needed)
        unique_dates      = dfdata.index.strftime(integration_frequency_string).unique().tolist()
        for idate in unique_dates:

            # now, numpy
            ind_dates         = np.where(pdata.index.strftime(integration_frequency_string) == idate)[0]
            ind_dates_ref     = np.where(pdata_ref.index.strftime(integration_frequency_string) == idate)[0]
            timeseries_ref    = np.asarray(pdata_ref[ind_dates_ref])

            # remove zeros
            if remove_zeros:
                ind_include_ref = np.where( (timeseries_ref != 0) & (~np.isnan(timeseries_ref)) )[0]
            else:
                ind_include_ref = np.where( (~np.isnan(timeseries_ref)) )[0]

            # pzero calculation; check how many zeros there are
            if pzero_replace:
                if pzero_center_mass:
                    pzero_ref       = 1 - len(ind_include_ref) / (len(timeseries_ref) + 1)
                else:
                    pzero_ref       = 1 - len(ind_include_ref) / len(timeseries_ref)
            else:
                pzero_ref       = np.nan

            # 4 fit distribution (ignore nans)
            if (pzero_ref > max_zeros) or (len(ind_include_ref) < n_events_min):
                significance_index[ind_dates] = np.asarray([np.nan] * len(ind_dates))
            else:
                try:
                    pars, loc, scale = fit_distribution(timeseries_ref[ind_include_ref], distr)
                except:
                    print("Issue in col "+str(icol)+" with idate "+str(idate))
                    print(timeseries_ref[ind_include_ref])
                    print(ind_include_ref)
                    pars = np.nan

                # 7 check significance using SI values over the reference period
                if ~np.isnan(pars):
                    #print("Processing col "+str(icol)+" with idate "+str(idate)+"!")
                    cdfv    = np.asarray([np.nan] * len(timeseries_ref))
                    # apply sign. test only to P!=0 values, rather than replacing P=0 with normally distributed index values as in Stagge et al., 2015
                    cdfv[ind_include_ref]    = calc_cdf(timeseries_ref[ind_include_ref], distr, pars, loc, scale, pzero_replace = False, pzero_ref = np.nan, pzero_center_mass = False, pzero_ref_adj = np.nan)
                    ppfv    = convert_cdf2ppf(cdfv)
                    significance = is_significant(ppfv, sigtest, alpha)
                    #print(significance)
                    if (significance not in [1,0]):
                        print(significance)
                else:
                    significance = np.nan

                # 8 write back to significance_index
                significance_index[ind_dates] = np.asarray([significance] * len(ind_dates))

        # write back to dataframe
        scol  = f"sig_si{window}_{icol}"
        sidata[scol] = significance_index

    return sidata
