"""
Data reader for longitudinal databases LTDB, geolytics NCDB and NHGIS
"""

import os
import zipfile
import quilt
from warnings import warn
try:
    from quilt.data.knaaptime import census
except ImportError:
    warn("Fetching data. This should only happen once")
    quilt.install("spatialucr/census")
    quilt.install("spatialucr/census_cartographic")
    from quilt.data.knaaptime import census
import matplotlib.pyplot as plt
import pandas as pd
from shapely import wkt, wkb

import geopandas as gpd

# Variables


def _convert_gdf(df):
    if 'wkt' in df.columns.tolist():
        df['geometry'] = df.wkt.apply(wkt.loads)
        df.drop(columns=['wkt'], inplace=True)
    else:
        df['geometry'] = df.wkb.apply(lambda x: wkb.loads(x, hex=True))
        df.drop(columns=['wkb'], inplace=True)
    df = gpd.GeoDataFrame(df)
    df.crs = {"init": "epsg:4326"}
    return df


_package_directory = os.path.dirname(os.path.abspath(__file__))
_variables = pd.read_csv(os.path.join(_package_directory, "variables.csv"))

states = pd.read_parquet(os.path.join(_package_directory, 'states.parquet'))

counties = pd.read_parquet(
    os.path.join(_package_directory, 'counties.parquet.gzip'))
#_counties = _convert_gdf(_counties)
#_counties = _counties[['geoid', 'geometry']]

tracts = census.tracts_2010
#tracts = tracts.rename(columns={"GEOID": "geoid"})
#_tracts = _tracts[['geoid', 'geometry', 'point']]

metros = pd.read_parquet(os.path.join(_package_directory, 'msas.parquet'))
metros = _convert_gdf(metros)

# LTDB importer


def read_ltdb(sample, fullcount):
    """
    Read data from Brown's Longitudinal Tract Database (LTDB) and store it for later use.

    Parameters
    ----------
    sample : str
        file path of the zip file containing the standard Sample CSV files downloaded from
        https://s4.ad.brown.edu/projects/diversity/Researcher/LTBDDload/Default.aspx

    fullcount: str
        file path of the zip file containing the standard Fullcount CSV files downloaded from
        https://s4.ad.brown.edu/projects/diversity/Researcher/LTBDDload/Default.aspx

    Returns
    -------
    DataFrame

    """
    sample_zip = zipfile.ZipFile(sample)
    fullcount_zip = zipfile.ZipFile(fullcount)

    def _ltdb_reader(path, file, year, dropcols=None):

        df = pd.read_csv(
            path.open(file),
            na_values=["", " ", 99999, -999],
            converters={
                0: str,
                "placefp10": str
            },
            low_memory=False,
            encoding="latin1",
        )

        if dropcols:
            df.drop(dropcols, axis=1, inplace=True)
        df.columns = df.columns.str.lower()
        names = df.columns.values.tolist()
        names[0] = "geoid"
        newlist = []

        # ignoring the first 4 columns, remove year suffix from column names
        for name in names[4:]:
            newlist.append(name[:-2])
        colnames = names[:4] + newlist
        df.columns = colnames

        # prepend a 0 when FIPS is too short
        df["geoid"] = df["geoid"].str.rjust(11, "0")
        df.set_index("geoid", inplace=True)

        df["year"] = year

        inflate_cols = ["mhmval", "mrent", "hinc"]
        try:
            df = _adjust_inflation(df, inflate_cols, year)
        except:
            pass

        return df

    # read in Brown's LTDB data, both the sample and fullcount files for each
    # year population, housing units & occupied housing units appear in both
    # "sample" and "fullcount" files-- currently drop sample and keep fullcount

    sample70 = _ltdb_reader(
        sample_zip,
        "ltdb_std_all_sample/ltdb_std_1970_sample.csv",
        dropcols=["POP70SP1", "HU70SP", "OHU70SP"],
        year=1970,
    )

    fullcount70 = _ltdb_reader(
        fullcount_zip, "LTDB_Std_1970_fullcount.csv", year=1970)

    sample80 = _ltdb_reader(
        sample_zip,
        "ltdb_std_all_sample/ltdb_std_1980_sample.csv",
        dropcols=["pop80sf3", "pop80sf4", "hu80sp", "ohu80sp"],
        year=1980,
    )

    fullcount80 = _ltdb_reader(
        fullcount_zip, "LTDB_Std_1980_fullcount.csv", year=1980)

    sample90 = _ltdb_reader(
        sample_zip,
        "ltdb_std_all_sample/ltdb_std_1990_sample.csv",
        dropcols=["POP90SF3", "POP90SF4", "HU90SP", "OHU90SP"],
        year=1990,
    )

    fullcount90 = _ltdb_reader(
        fullcount_zip, "LTDB_Std_1990_fullcount.csv", year=1990)

    sample00 = _ltdb_reader(
        sample_zip,
        "ltdb_std_all_sample/ltdb_std_2000_sample.csv",
        dropcols=["POP00SF3", "HU00SP", "OHU00SP"],
        year=2000,
    )

    fullcount00 = _ltdb_reader(
        fullcount_zip, "LTDB_Std_2000_fullcount.csv", year=2000)

    sample10 = _ltdb_reader(
        sample_zip, "ltdb_std_all_sample/ltdb_std_2010_sample.csv", year=2010)

    # join the sample and fullcount variables into a single df for the year
    ltdb_1970 = sample70.drop(columns=['year']).join(
        fullcount70.iloc[:, 7:], how="left")
    ltdb_1980 = sample80.drop(columns=['year']).join(
        fullcount80.iloc[:, 7:], how="left")
    ltdb_1990 = sample90.drop(columns=['year']).join(
        fullcount90.iloc[:, 7:], how="left")
    ltdb_2000 = sample00.drop(columns=['year']).join(
        fullcount00.iloc[:, 7:], how="left")
    ltdb_2010 = sample10

    df = pd.concat(
        [ltdb_1970, ltdb_1980, ltdb_1990, ltdb_2000, ltdb_2010], sort=True)

    renamer = dict(
        zip(_variables['ltdb'].tolist(), _variables['variable'].tolist()))

    df.rename(renamer, axis="columns", inplace=True)

    # compute additional variables from lookup table
    for row in _variables['formula'].dropna().tolist():
        df.eval(row, inplace=True)

    df = df.round(0)

    keeps = df.columns[df.columns.isin(_variables['variable'].tolist() +
                                       ['year'])]
    df = df[keeps]

    df.to_parquet(
        os.path.join(_package_directory, "ltdb.parquet.gzip"),
        compression='gzip')

    return df


def read_ncdb(filepath):
    """
    Read data from Geolytics's Neighborhood Change Database (NCDB) and store it for later use.

    Parameters
    ----------
    input_dir : str
        location of the input CSV file extracted from your Geolytics DVD

    Returns
    -------
    DataFrame

    """

    ncdb_vars = _variables["ncdb"].dropna()[1:].values

    names = []
    for name in ncdb_vars:
        for suffix in ['7', '8', '9', '0', '1', '2']:
            names.append(name + suffix)
    names.append('GEO2010')
    df = pd.read_csv(
        filepath,
        engine='c',
        na_values=["", " ", 99999, -999],
        converters={
            "GEO2010": str,
            "COUNTY": str,
            "COUSUB": str,
            "DIVISION": str,
            "REGION": str,
            "STATE": str,
        },
    )

    cols = df.columns
    fixed = []
    for col in cols:
        if col.endswith("D"):
            fixed.append("D" + col[:-1])
        elif col.endswith("N"):
            fixed.append("N" + col[:-1])
        elif col.endswith("1A"):
            fixed.append(col[:-2] + "2")

    orig = []
    for col in cols:
        if col.endswith("D"):
            orig.append(col)
        elif col.endswith("N"):
            orig.append(col)
        elif col.endswith("1A"):
            orig.append(col)

    renamer = dict(zip(orig, fixed))
    df.rename(renamer, axis="columns", inplace=True)

    df = df[df.columns[df.columns.isin(names)]]

    df = pd.wide_to_long(
        df, stubnames=ncdb_vars, i="GEO2010", j="year",
        suffix="(7|8|9|0|1|2)").reset_index()

    df["year"] = df["year"].replace({
        7: 1970,
        8: 1980,
        9: 1990,
        0: 2000,
        1: 2010,
        2: 2010
    })
    df = df.groupby(["GEO2010", "year"]).first()

    mapper = dict(zip(_variables.ncdb, _variables.variable))

    df.reset_index(inplace=True)

    df = df.rename(mapper, axis="columns")

    df = df.set_index("geoid")

    for row in _variables['formula'].dropna().tolist():
        try:
            df.eval(row, inplace=True)
        except:
            pass

    df = df.round(0)

    keeps = df.columns[df.columns.isin(_variables['variable'].tolist() +
                                       ['year'])]

    df = df[keeps]

    df = df.loc[df.n_total_pop != 0]

    df.to_parquet(
        os.path.join(_package_directory, "ncdb.parquet.gzip"),
        compression='gzip')

    return df


# TODO NHGIS reader


class Dataset(object):
    """Container for storing neighborhood data for a study region

    Parameters
    ----------
    name : str
        name or title of dataset.
    source : str
        database from which to query attribute data. must of one of ['ltdb', 'ncdb', 'census', 'external'].
    states : list-like
        list of two-digit State FIPS codes that define a study region. These will be used to select tracts or blocks that fall within the region.
    counties : list-like
                list of three-digit County FIPS codes that define a study region. These will be used to select tracts or blocks that fall within the region.
    add_indices : list-like
        list of additional indices that should be included in the region. This is likely a list of additional tracts that are relevant to the study area but do not fall inside the passed boundary
    boundary : GeoDataFrame
        A GeoDataFrame that defines the extent of the boundary in question.
         If a boundary is passed, it will be used to clip the tracts or blocks that fall within it and the 
         state and county lists will be ignored

    Attributes
    ----------
    data : Pandas DataFrame
        long-form dataframe containing attribute variables for each unit of analysis.
    name : str
        name or title of dataset
    boundary : GeoDataFrame
        outer boundary of the study area
    tracts
        GeoDataFrame containing tract boundaries
    counties
        GeoDataFrame containing County boundaries
    states
        GeoDataFrame containing State boundaries
    """

    def __init__(self,
                 name,
                 source,
                 statefips=None,
                 countyfips=None,
                 add_indices=None,
                 boundary=None,
                 **kwargs):

        # If a boundary is passed, use it to clip out the appropriate tracts
        tracts = census.tracts_2010().copy()
        tracts.columns = tracts.columns.str.lower()
        self.name = name
        self.states = states.copy()
        self.tracts = tracts.copy()
        self.counties = counties.copy()
        if boundary is not None:
            self.tracts = _convert_gdf(self.tracts)
            self.boundary = boundary
            if boundary.crs != self.tracts.crs:
                self.tracts = self.tracts.to_crs(boundary.crs)
                self.counties = self.counties.to_crs(boundary.crs)
                self.states = self.states.to_crs(boundary.crs)

            self.tracts = self.tracts[self.tracts.centroid.within(
                self.boundary.unary_union)]
            self.counties = self.counties[counties.geoid.isin(
                self.tracts.geoid.str[0:5])]
            self.states = self.states[states.geoid.isin(
                self.tracts.geoid.str[0:2])]
            self.counties = _convert_gdf(self.counties)
            self.states = _convert_gdf(self.states)
        # If county and state lists are passed, use them to filter based on geoid
        else:
            statelist = []
            if isinstance(statefips, (list, )):
                statelist.extend(statefips)
            else:
                statelist.append(statefips)
            countylist = []
            if isinstance(countyfips, (list, )): countylist.extend(countyfips)
            else: countylist.append(countyfips)
            geo_filter = {'state': statelist, 'county': countylist}
            fips = []
            for state in geo_filter['state']:
                if countyfips is not None:
                    for county in geo_filter['county']:
                        fips.append(state + county)
                else:
                    fips.append(state)
            self.states = self.states[states.geoid.isin(statelist)]
            if countyfips is not None:
                self.counties = self.counties[self.ounties.geoid.str[:5].isin(
                    fips)]
                self.tracts = self.tracts[self.tracts.geoid.str[:5].isin(fips)]
            else:
                self.counties = self.counties[self.counties.geoid.str[:2].isin(
                    fips)]
            self.tracts = self.tracts[self.tracts.geoid.str[:2].isin(fips)]
            self.tracts = _convert_gdf(self.tracts)
            self.counties = _convert_gdf(self.counties)
            self.states = _convert_gdf(self.states)
        if source == "ltdb":
            try:
                _df = pd.read_parquet(
                    os.path.join(_package_directory, "ltdb.parquet.gzip"))
            except OSError:
                warn(
                    "Unable to locate LTDB data. Please import the database with the `read_ltdb` function"
                )
        elif source == "ncdb":
            try:
                _df = pd.read_parquet(
                    os.path.join(_package_directory, "ncdb.parquet.gzip"))
            except OSError:
                warn(
                    "Unable to locate NCDB data. Please import the database with the `read_ncdb` function"
                )
        elif source == "external":
            _df = data
        else:
            raise ValueError(
                "source must be one of 'ltdb', 'ncdb', 'census', 'external'")

        self.data = _df[_df.index.isin(self.tracts.geoid)]
        if add_indices:
            for index in add_indices:
                self.data = self.data.append(
                    _df[_df.index.str.startswith(index)])
                self.tracts = self.tracts.append(
                    _convert_gdf(tracts[tracts.geoid.str.startswith(index)]))

    def plot(self,
             column=None,
             year=2010,
             ax=None,
             plot_counties=True,
             title=None,
             **kwargs):
        """
        convenience function for plotting tracts in the metro area
        """
        assert column, "You must choose a column to plot"
        if ax is not None:
            ax = ax
        else:
            fig, ax = plt.subplots(figsize=(15, 15))
            colname = column.replace("_", " ")
            colname = colname.title()
            if title:
                plt.title(title, fontsize=20)
            else:
                plt.title(
                    self.name + ": " + colname + ", " + str(year), fontsize=20)
            plt.axis("off")

        ax.set_aspect("equal")
        plotme = self.tracts.merge(
            self.data[self.data.year == year],
            left_on="geoid",
            right_index=True)
        plotme = plotme.dropna(subset=[column])
        plotme.plot(column=column, alpha=0.8, ax=ax)

        if plot_counties is True:
            self.counties.plot(
                edgecolor="#5c5353", linewidth=0.8, facecolor="none", ax=ax)

        return ax

    def to_crs(self, crs=None, epsg=None, inplace=False):
        """Transform all geometries in the study are to a new coordinate reference system.

            Parameters
            ----------
            crs : dict or str
                Output projection parameters as string or in dictionary form.
            epsg : int
                EPSG code specifying output projection.
            inplace : bool, optional, default: False
                Whether to return a new GeoDataFrame or do the transformation in
                place.
            """
        if inplace:
            self.tracts = self.tracts
            self.counties = self.counties
            self.states = self.states
        else:
            self.tracts = self.tracts.copy()
            self.counties = self.counties.copy()
            self.states = self.states.copy()

        self.tracts = self.tracts.to_crs(crs=crs, epsg=epsg)
        self.states = self.states.to_crs(crs=crs, epsg=epsg)
        self.counties = self.counties.to_crs(crs=crs, epsg=epsg)
        if not inplace:
            return self


# Utilities


def _adjust_inflation(df, columns, base_year):
    """
    Adjust currency data for inflation. Currently, this function generates
    output in 2015 dollars, but this could be parameterized later

    Parameters
    ----------
    df : DataFrame
        Dataframe of historical data
    columns : list-like
        The columns of the dataframe with currency data
    base_year: int
        Base year the data were collected; e.g. to convert data from the 1990
        census to 2015 dollars, this value should be 1990

    Returns
    -------
    type
        DataFrame

    """
    # adjust for inflation
    # get inflation adjustment table from BLS
    inflation = pd.read_excel(
        "https://www.bls.gov/cpi/research-series/allitems.xlsx", skiprows=6)
    inflation.columns = inflation.columns.str.lower()
    inflation.columns = inflation.columns.str.strip(".")
    inflation = inflation.dropna(subset=["year"])

    inflator = {
        2015: inflation[inflation.year == 2015]["avg"].values[0],
        2010: inflation[inflation.year == 2010]["avg"].values[0],
        2000: inflation[inflation.year == 2000]["avg"].values[0],
        1990: inflation[inflation.year == 1990]["avg"].values[0],
        1980: inflation[inflation.year == 1980]["avg"].values[0],
        1970:
        63.9,  # https://www2.census.gov/programs-surveys/demo/tables/p60/249/CPI-U-RS-Index-2013.pdf
    }

    df = df.copy()
    df[columns].apply(lambda x: x * (inflator[2015] / inflator[base_year]))

    return df
