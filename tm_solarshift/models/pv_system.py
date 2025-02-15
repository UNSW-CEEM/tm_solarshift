import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pvlib
from pvlib.pvarray import pvefficiency_adr

import tm_solarshift.utils.solar as solar
from tm_solarshift.constants import (DIRECTORY, DEFAULT, SIMULATIONS_IO)
from tm_solarshift.utils.units import ( Variable, conversion_factor as CF)

# default values
DIR_MAIN = DIRECTORY.DIR_MAIN
DEFAULT_TZ = DEFAULT.TZ
DEFAULT_LAT = DEFAULT.LAT
DEFAULT_LON = DEFAULT.LON
DEFAULT_TILT = DEFAULT.TILT
DEFAULT_ORIENT = DEFAULT.ORIENT
DEFAULT_G_STC = DEFAULT.G_STC
DEFAULT_PV_NOMPOW = DEFAULT.PV_NOMPOW
DEFAULT_ADR_PARAMS = DEFAULT.ADR_PARAMS

# columns (most are from pbliv)
COLS_TMY = [
    "temp_air", "GHI", "DNI", "DHI", "WS"
]
COLS_SOLPOS = [
    "apparent_zenith", "zenith",
    "apparent_elevation", "elevation",
    "azimuth", "equation_of_time"
]
COLS_INCIDENCE = [
    "cosine_aoi",
    "aoi"
]
COLS_IRRADIANCE_PLANE = [
    "poa_global", "poa_direct",
    "poa_diffuse", "poa_sky_diffuse",
    "poa_ground_diffuse"
]

#-------------------------
#PV System and auxiliary devices
class PVSystem():
    """PV System using ADR method

    Parameters:
        name (str): Name of the numerical model.
        cost (Variable): Cost of the Sistem.
        nom_power (Variable): Nominal power of the system. Default to Variable(5000, "W")
        adr_params (dict[str,float]): ADR model parameters.
        G_STC (Variable): Nominal standard irradiance. Default to Variable(1000, 'W/m2').
        lat (Variable): Latitude of the location.
        lon (Variable): Longitud of the location.
        tilt (Variable): Inclination angle.
        orient (Variable): Orientation angle.
        tz (Variable): Timezone.
        
    """
    def __init__(self):

        #description
        self.name = "PV system standard."
        self.model = "-"
        self.cost = Variable(np.nan, "AUD")

        #technical data
        self.nom_power = Variable(5000.0, "W")
        self.adr_params = {
            'k_a': 0.99924,
            'k_d': -5.49097,
            'tc_d': 0.01918,
            'k_rs': 0.06999,
            'k_rsh': 0.26144,
        }
        self.G_STC = Variable(1000.0, "W/m2")

        #location (change lat and lon with Location). Create them as properties.
        self.lat = Variable(-33.86, "deg")
        self.lon = Variable(151.22, "deg")
        self.tilt = Variable(abs(self.lat.get_value("deg")),"deg")
        self.orient = Variable(180.0,"deg")
        self.tz = 'Australia/Brisbane'

        #generation profile (only used for testing)
        self.profile_PV = 1
    
    def __eq__(self, other) : 
        return self.__dict__ == other.__dict__

    @property
    def coords(self) -> tuple[float,float]:
        return (self.lat, self.lon)
    
    def sim_generation(
            self,
            ts_wea: pd.DataFrame,
            unit: str = "kW",
            columns: list = SIMULATIONS_IO.OUTPUT_SIM_PV
    ) -> pd.DataFrame:
        """Simulate the PV generation given weather timeseries

        Args:
            ts_wea (pd.DataFrame): Weather timeseries. It requires "temp_amb", "WS" and "GHI".
            unit (str, optional): Unit to return the power generation. Defaults to "kW".
            columns (list, optional): Columns to return from the simulation. Defaults to SIMULATIONS_IO.OUTPUT_SIM_PV.

        Returns:
            pd.DataFrame: Dataframe with the resulted simulation.
        """
        
        latitude = self.lat.get_value("deg")
        longitude = self.lon.get_value("deg")
        tilt = self.tilt.get_value("deg")
        orient = self.orient.get_value("deg")
        nom_power = self.nom_power.get_value("W")
        tz = self.tz
        adr_params = self.adr_params
        G_STC = self.G_STC.get_value("W/m2")

        temp_amb = ts_wea["temp_amb"]
        WS = ts_wea["WS"]

        # Estimating: radiation in pv plane, pv temp, relative efficiency, and module power
        ts_aux = ts_wea.copy()
        ts_aux.index = ts_aux.index.tz_localize(tz)
        temp_amb = ts_aux["temp_amb"]
        WS = ts_aux["WS"]
        df_rad = solar.get_plane_irradiance(
            ts=ts_aux,
            latitude=latitude, longitude=longitude, tilt=tilt, orient=orient, tz=tz,
        )

        # results df
        df_pv = pd.DataFrame(index=ts_aux.index, columns=columns)
        df_pv["poa_global"] = df_rad["poa_global"]
        df_pv["temp_pv"] = pvlib.temperature.faiman( df_pv["poa_global"], temp_amb, WS )
        df_pv["eta_rel"] = pvefficiency_adr(
            df_pv['poa_global'], df_pv['temp_pv'], **adr_params
        )
        df_pv["pv_power"] = (
            nom_power * df_pv['eta_rel'] * (df_pv['poa_global'] / G_STC) * CF("W", unit)
        )
        df_pv = df_pv.tz_localize(None)
        return df_pv


#---------------
def sample_plots(
    df: pd.DataFrame,
    DEMO_DAY:str = '2022-02-07',
):
    plt.figure()
    pc = plt.scatter(df['poa_global'], df['eta_rel'], c=df['temp_pv'], cmap='jet')
    plt.colorbar(label='Temperature [C]', ax=plt.gca())
    pc.set_alpha(0.25)
    plt.grid(alpha=0.5)
    plt.ylim(0.48)
    plt.xlabel('Irradiance [W/m²]')
    plt.ylabel('Relative efficiency [-]')
    plt.show()

    plt.figure()

    pc = plt.scatter(df['poa_global'], df['pv_power'], c=df['temp_pv'], cmap='jet')
    plt.colorbar(label='Temperature [C]', ax=plt.gca())
    pc.set_alpha(0.25)
    plt.grid(alpha=0.5)
    plt.xlabel('Irradiance [W/m²]')
    plt.ylabel('Array power [W]')
    plt.show()

    plt.figure()
    plt.plot(df['pv_power'][DEMO_DAY])
    plt.xticks(rotation=30)
    plt.ylabel('Power [W]')
    plt.show()


def main():

    from tm_solarshift.general import Simulation
    sim = Simulation()
    ts = sim.create_ts()

    pv_system = PVSystem()
    df_pv = pv_system.sim_generation(ts)
    print(df_pv)
    sample_plots(df_pv)
    return


if __name__ == "__main__":
    main()
    pass