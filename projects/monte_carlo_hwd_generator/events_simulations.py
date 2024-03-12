# -*- coding: utf-8 -*-
"""
Created on Mon Oct 23 15:20:46 2023

@author: z5158936
"""

import time
import os
import sys
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from matplotlib import cm
from sklearn import linear_model
from scipy.stats import norm

from typing import Optional, List, Dict, Any, Union

from tm_solarshift.constants import (
    DIR_DATA,
    PROFILES_TYPES,
)

import tm_solarshift.trnsys as trnsys
import tm_solarshift.profiles as profiles
from tm_solarshift.general import GeneralSetup
from tm_solarshift.devices import conversion_factor

PROFILES_TYPES = profiles.PROFILES_TYPES
PROFILES_COLUMNS = profiles.PROFILES_COLUMNS
WEATHER_TYPES = [
    'day_constant', 
    'meteonorm_random', 
    'meteonorm_month', 
    'meteonorm_date'
    ]
DIR_RESULTS = "results/event_simulations"

#-------------------------
def loading_timeseries(
    general_setup = GeneralSetup(),
    HWD_generator_method: str = 'events',
    HWDP_dist: int = 0,
    weather_type: str = 'day_constant'
    ) -> pd.DataFrame:

    #Getting the required data from GeneralSetup
    location = general_setup.location
    profile_control = general_setup.profile_control
    random_control = general_setup.random_control

    # creating and loading timeseries
    timeseries = profiles.new_profile(general_setup)
    
    #Hot water draw daily distribution
    HWD_daily_dist = profiles.HWD_daily_distribution(
        general_setup, 
        timeseries
    )
    if HWD_generator_method == 'events':
        event_probs = profiles.events_file(
            file_name = os.path.join(
                DIR_DATA["samples"], "HWD_events.xlsx",
                ),
            sheet_name="Custom"
            )
    else:
        event_probs = None
    timeseries = profiles.HWDP_generator(
            timeseries,
            method = HWD_generator_method,
            HWD_daily_dist = HWD_daily_dist,
            HWD_hourly_dist = HWDP_dist,
            event_probs = event_probs,
        )
    
    #Weather
    weather_subsets = {
        'meteonorm_random': ('all', None),
        'meteonorm_season': ('season', 'summer'),
        'meteonorm_month' : ('month', 1),
        'meteonorm_date' : ('date', pd.Timestamp("2022/02/07")),
        'day_constant': (None, None)
    }
    (subset_random, subset_value) = weather_subsets[weather_type]
    
    if weather_type == 'day_constant':
        timeseries = profiles.load_weather_day_constant_random(
            timeseries,
        )
    else:
        file_weather = os.path.join(
            DIR_DATA["weather"],
            "meteonorm_processed",
            f"meteonorm_{location}.csv",
        )
        timeseries = profiles.load_weather_from_file(
            timeseries,
            file_weather,
            columns = PROFILES_TYPES['weather'],
            subset_random = subset_random,
            subset_value = subset_value,
        )
    
    #Electric
    timeseries = profiles.load_PV_generation(timeseries)
    timeseries = profiles.load_elec_consumption(timeseries)
    
    #Control Load
    timeseries = profiles.load_control_load(
        timeseries, 
        profile_control = profile_control, 
        random_ON = random_control
    )
    return timeseries

#-------------------------
def run_or_load_simulation(
        general_setup: GeneralSetup,
        timeseries: pd.DataFrame,
        runsim: bool = True,
        savefile: bool = True
        ):
    
    HWDP_dist = general_setup.profile_HWD

    if runsim:
        out_data = trnsys.run_trnsys_simulation(
            general_setup, timeseries, verbose=True
        )
        df = trnsys.postprocessing_events_simulation(
            general_setup, timeseries, out_data,
        )
    else:
        df = pd.read_csv(
            os.path.join(
                DIR_RESULTS, 
                f"0-Results_HWDP_dist_{HWDP_dist}.csv"
                ),
            index_col=0,
        )
        out_data = pd.read_csv(
            os.path.join(
                DIR_RESULTS, 
                f"0-Results_HWDP_dist_{HWDP_dist}_detailed.csv",
                ),
            index_col=0,
        )
        df.index = [pd.to_datetime(i).date() for i in df.index]
        out_data.index = pd.to_datetime(out_data.index)
    
    #Saving the results if needed
    if not os.path.exists(DIR_RESULTS):
        os.mkdir(DIR_RESULTS)
    if savefile:
        df.to_csv(
            os.path.join(
                DIR_RESULTS,
                f"0-Results_HWDP_dist_{HWDP_dist}.csv",
                )
            )
        out_data.to_csv(
            os.path.join(
                DIR_RESULTS,
                f"0-Results_HWDP_dist_{HWDP_dist}_detailed.csv",
                )
            )

    return (out_data, df)

#-------------------------
def plot_histogram_end_of_day(
        values,
        xlim = (0,1),
        xlbl = None,
        ylbl = None,
        file_name = None,
        fldr_rslt = DIR_RESULTS,
        savefig = False,
):
    fs = 16
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.hist(values, bins=10, range=xlim, density=True)
    ax.set_xlabel(xlbl, fontsize=fs)
    ax.set_ylabel(ylbl, fontsize=fs)
    ax.tick_params(axis="both", which="major", labelsize=fs)
    ax.set_xlim(xlim)
    # ax.set_xticks(np.arange(0, 1.01, 0.1))
    ax.grid()
    if savefig:
        fig.savefig(
            os.path.join(fldr_rslt, file_name),
            bbox_inches="tight",
        )
    plt.show()
    return

#-------------------------
def plots_histogram_end_of_days(
        df: pd.DataFrame,
        include: List,
        case: Union[int, str],
        savefig: bool=False,
):
    for lbl in include:
        if lbl == "SOC_end":
            xlim = (0,1)
            xlbl = "State of Charge (-)"
            ylbl = "Frequency (-)"
            file_name = f"Case_{case}_hist_SOC.png"
        if lbl == "TempTh_end":
            xlim = (20,65)
            xlbl = "State of Charge (-)"
            ylbl = "Frequency (-)"
            file_name = f"Case_{case}_hist_TempTh.png"
        if lbl=="E_HWD_day":
            xlim = (0, 12)
            xlbl = "Daily Hot Water Draw (kWh)"
            ylbl = "Frequency (-)"
            file_name = f"Case_{case}_hist_HWD_Energy.png"
        if lbl=="m_HWD_day":
            xlim = (0, 400)
            xlbl = "Daily Hot Water Draw (L/day)"
            ylbl = "Frequency (-)"
            file_name = f"Case_{case}_hist_HWD_Flow.png"

        plot_histogram_end_of_day(
            df[lbl],
            xlim = xlim,
            xlbl = xlbl,
            ylbl = ylbl,
            file_name = file_name,
            savefig = savefig
            )
    return

#-------------------------
def additional_plots(
        df : pd.DataFrame,
        case: Union[int, str] = None,
        savefig: bool = False,
):

    #Plot of distribution function of daily HWD
    fs = 16
    HWD_day = df["m_HWD_day"].copy()
    HWD_day.sort_values(ascending=True, inplace=True)
    HWD_day = HWD_day.reset_index()
    if True:
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.plot(HWD_day.index, HWD_day["m_HWD_day"], lw=2.0)
        ax.set_xlabel("Days of simulation", fontsize=fs)
        ax.set_ylabel("Daily Hot Water Draw (L/day)", fontsize=fs)
        ax.tick_params(axis="both", which="major", labelsize=fs)
        # ax.set_xlim(0,12)
        ax.grid()
        if savefig:
            fig.savefig(
                os.path.join(DIR_RESULTS, f"Case_{case}_HWD_Flow_ascending.png"),
                bbox_inches="tight",
            )
        plt.show()

    # SOC as function of Daily HWD
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(df["m_HWD_day"], df["SOC_end"], c=df["Temp_Amb"], s=10)
    ax.set_xlabel("Daily HWD (L/day)", fontsize=fs)
    ax.set_ylabel("SOC (-)", fontsize=fs)
    ax.tick_params(axis="both", which="major", labelsize=fs)
    ax.grid()
    if savefig:
        fig.savefig(
            os.path.join(DIR_RESULTS, f"Case_{case}_HWD_SOC.png"),
            bbox_inches="tight",
        )
    plt.show()

    # SOC as function of Thermostat Temp
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.scatter(df["TempTh_end"], df["SOC_end"], c=df["m_HWD_day"], s=10)
    ax.set_xlabel("Thermostat temperature (C)", fontsize=fs)
    ax.set_ylabel("SOC (-)", fontsize=fs)
    ax.tick_params(axis="both", which="major", labelsize=fs)
    ax.grid()
    if savefig:
        fig.savefig(
            os.path.join(DIR_RESULTS, f"Case_{case}_TempTh_SOC.png"),
            bbox_inches="tight",
        )
    plt.show()
    return

#-------------------------
def plot_histogram_2D(
    general_setup: GeneralSetup,
    df : pd.DataFrame,
    out_data: pd.DataFrame,
    case: Union[int, str] = None,
    savefig: bool = False,
):
    
    STEP = general_setup.STEP
    DAYS = general_setup.DAYS
    
    # Probabilities of SOC through the day
    Nx = 24
    Ny = 20
    xmin = 0
    xmax = 24
    ymin = 0.0
    ymax = 1.0
    vmin = 0
    vmax = 0.25
    
    dx = (xmax-xmin)/Nx
    F_bin = (60*dx/STEP)*DAYS
    out_data['hour'] = out_data.index.hour + out_data.index.minute/60.
    SOC_2D, X, Y = np.histogram2d(
        out_data['hour'], out_data['SOC'],
        bins = [Nx,Ny], range = [[xmin, xmax],[ymin, ymax]], density=False
    )
    SOC_2D = SOC_2D/F_bin
    fig = plt.figure(figsize=(14, 8))
    fs = 16
    ax = fig.add_subplot(111)
    X, Y = np.meshgrid(X, Y)
    surf = ax.pcolormesh(
        X, Y, SOC_2D.transpose(),
        cmap=cm.YlOrRd, vmin=vmin, vmax=vmax
    )
    ax.set_xlabel('time (hr)',fontsize=fs)
    ax.set_ylabel('SOC (-)',fontsize=fs)
    cb = fig.colorbar(surf, shrink=0.5, aspect=4)
    cb.ax.tick_params(labelsize=fs-2)
    ax.tick_params(axis="both", which="major", labelsize=fs)
    if savefig:
        fig.savefig(
            os.path.join(DIR_RESULTS, f"Case_{case}_SOC_map.png"),
            bbox_inches="tight",
        )
    plt.grid()
    plt.show()
    plt.close(fig)
    return

#-------------------------
def plots_sample_simulations(
    general_setup: GeneralSetup,
    out_data : pd.DataFrame,
    df: pd.DataFrame,
    case: Union[int, str],
    savefig: bool = False,
    t_ini: float = 3
):
    DAYS = general_setup.DAYS

    # Plot with a sample of 10% of days

    #SOC
    df_sample = df.sample(max(DAYS // 10, 10))
    fig, ax = plt.subplots(figsize=(9, 6))
    fs=16
    for date in df_sample.index:
        df_day = out_data[out_data.index.date == date]
        time_day = df_day.index.hour + df_day.index.minute / 60.0
        ax.plot(time_day, df_day.SOC, lw=0.5)

    ax.set_xlabel("Time of the Day (hr)", fontsize=fs)
    ax.set_ylabel("SOC (-)", fontsize=fs)
    ax.tick_params(axis="both", which="major", labelsize=fs)
    ax.grid()
    ax.set_xlim(0, 24)
    ax.set_xticks(np.arange(0, 25, 4))
    if savefig:
        fig.savefig(
            os.path.join(DIR_RESULTS, f"Case_{case}_sample_SOC.png"),
            bbox_inches="tight",
        )
    plt.show()

    # Thermostat temperature
    fig, ax = plt.subplots(figsize=(9, 6))
    ax2 = ax.twinx()
    ax2.plot(time_day, df_day["C_Load"], c="blue", lw=2, label="C_Load")

    out_data_first = out_data[(out_data.C_Tmax < 1) & (out_data.index.hour >= t_ini)]
    out_data_first = out_data_first.groupby(out_data_first.index.date).first()
    out_data_first["C_Tmax_first"] = out_data_first["TIME"] - 24 * (
        pd.to_datetime(out_data_first.index).dayofyear - 1
    )
    out_data_first.index = pd.to_datetime(out_data_first.index)

    for date in df_sample.index:
        df_day = out_data[out_data.index.date == date]
        time_day = df_day.index.hour + df_day.index.minute / 60.0
        ax.plot(time_day, df_day.TempBottom, lw=0.5)
        aux2 = out_data_first[out_data_first.index.date == date]
        ax.scatter(
            aux2["C_Tmax_first"], aux2["TempBottom"],
            s=50, marker="*",
            label="C_Tmax" if (date == df_sample.index[0]) else None,
        )
    ax2.legend()
    ax.set_xlabel("Time of the Day (hr)", fontsize=fs)
    ax.set_ylabel("Thermostat Temperature (-)", fontsize=fs)
    ax.tick_params(axis="both", which="major", labelsize=fs)
    ax.grid()
    ax.set_xlim(0, 24)
    ax.set_xticks(np.arange(0, 25, 4))
    if savefig:
        fig.savefig(
            os.path.join(DIR_RESULTS, f"Case_{case}_sample_TempTh.png"),
            bbox_inches="tight",
        )
    plt.show()

#-------------------------
def regression_analysis_and_plots(
    general_setup: GeneralSetup,
    timeseries : pd.DataFrame,
    df : pd.DataFrame,
    case: Union[int, str] = None,
    savefig: bool = False,
):
    
    HWDP_dist = general_setup.profile_HWD
    
    # Histogram of generated HWDP
    HWDP_generated = timeseries.groupby(
        timeseries.index.hour
        )["m_HWD"].sum()
    HWDP_generated = HWDP_generated / HWDP_generated.sum()
    list_hours = np.arange(0, 23 + 1)
    if HWDP_dist is not None:
        HWD_file = os.path.join(
            DIR_DATA["HWDP"], f"HWDP_Generic_AU_{HWDP_dist}.csv"
        )
        HWDP_day = pd.read_csv(HWD_file)
        probs = HWDP_day.loc[list_hours, "HWDP"].values
        probs = probs / probs.sum()
        HWDP_template = probs
    
        from scipy.stats import linregress
        (slope, intercept, R2, p_value, std_err) = linregress(
            HWDP_template, 
            HWDP_generated,
            )
        RSME = ((HWDP_template - HWDP_generated) ** 2).mean() ** 0.5
    
        fig, ax = plt.subplots(figsize=(9, 6))
        fs = 16
        ax.scatter(HWDP_template, HWDP_generated, s=20)
        Ymax = HWDP_template.max()
        ax.plot([0, Ymax], [0, Ymax], c="k")
        ax.set_xlim(0, Ymax * 1.05)
        ax.set_ylim(0, Ymax * 1.05)
        ax.grid()
        ax.tick_params(axis="both", which="major", labelsize=fs)
        if savefig:
            fig.savefig(
                os.path.join(DIR_RESULTS, f"Case_{case}_HWDP_methods_comparison.png"),
                bbox_inches="tight",
            )
        plt.show()
    
        fig, ax = plt.subplots(figsize=(9, 6))
        ax.bar(HWDP_generated.index, HWDP_template,
                width=0.4, align="edge",)
        ax.bar(HWDP_generated.index, HWDP_generated,
                width=-0.4, align="edge",)
        ax.grid()
        ax.tick_params(axis="both", which="major", labelsize=fs)
        plt.show()

    #Regresion
    for lbl in ["SOC_end", "TempTh_end"]:
        cols = ["SOC_ini", "Temp_Amb", "Temp_Mains", "m_HWD_day"]
        df2 = df[cols + [lbl]].copy()
        df2.dropna(inplace=True)
        X = df2[cols]
        Y = df2[lbl]
        regr = linear_model.LinearRegression()
        regr.fit(X, Y)
        R2 = regr.score(X, Y)
        print(R2)
        if lbl == "SOC_end":
            R2_SOC = R2
        if lbl == "TempTh_end":
            R2_TempTh = R2

        Y_pred = regr.predict(X)

        show_plot = True
        if show_plot:
            fig, ax = plt.subplots(figsize=(9, 6))
            ax.scatter(Y, Y_pred, s=2)
            Ymax = Y.max()
            ax.plot([0, Ymax], [0, Ymax], c="k")

            ax.set_xlim(0, Ymax * 1.05)
            ax.set_ylim(0, Ymax * 1.05)
            ax.grid()
            ax.set_xlabel(f"Simulated {lbl}", fontsize=fs)
            ax.set_ylabel(f"Predicted {lbl}", fontsize=fs)
            # ax.set_title(f'CL={row.profile_control}. HWDP={row.profile_HWD}. Timestep={t}mins ahead',fontsize=fs)
            ax.tick_params(axis="both", which="major", labelsize=fs)
            plt.show()

    return [R2_SOC, R2_TempTh]
    
#-------------------------
def main():

    ## DEFINING CASES
    # Cases are:
    #    1: Only varying the initial time of event.
    #    2: Only varying the ambient and mains temperature.
    #    3: Only varying the duration and flow rate
    #    4: Including different number of events
    #    5: Varying everything
    #    6: Selecting days randomnly from Sydney weather file

    # Cases = [5,1,2,3,4]

    load_profiles = True
    runsim = True
    savefig = True
    savefile = True
    DAYS = 100
    t_ini = 3.0
    #Profile Control
    profile_control = 10
    random_control = False

    #Which HWDP will be used 
    HWDP_dists = [1, 2, 3, 4, 5, 6, None]
    HWDP_dist = 1

    # HWDG_method = 'standard'
    HWD_generator_method = 'events'
    HWD_daily_dist = 'sample'

    CASES = [0, 1, 2, 3]
    CASES = [1,]
    data = []
    for case in CASES:
        
        s_time = time.time()

        weather_type = WEATHER_TYPES[case]
        general_setup = GeneralSetup(
            STOP = int(24 * DAYS),
            STEP = 3,
            YEAR = 2022,
            profile_control = profile_control,
            profile_HWD = HWDP_dist,
            random_control = random_control,
            weather_source = "local_file",
            HWD_daily_dist = HWD_daily_dist,
        )
        timeseries = loading_timeseries(
            general_setup = general_setup,
            HWD_generator_method = HWD_generator_method,
            HWDP_dist = HWDP_dist,
            weather_type = weather_type
        )
        (out_data, df) = run_or_load_simulation(
            general_setup, timeseries, runsim = runsim, savefile=savefile
        )
        trnsys.detailed_plots(
                general_setup,
                out_data,
                fldr_results_detailed = DIR_RESULTS,
                case = 'simple_event',
                save_plots_detailed = False,
                tmax = 120.
                )
        time_simulation = time.time() - s_time
        print(f"Time spent in thermal simulation={time_simulation}")

        #Different plottings
        plots_histogram_end_of_days(
            df,
            ["SOC_end", "TempTh_end", "E_HWD_day", "m_HWD_day"],
            case, savefig
        )        
        additional_plots(df, case, savefig)
        plot_histogram_2D(
            general_setup, df, out_data, case, savefig
        )
        plots_sample_simulations(general_setup, out_data, df, case, savefig)
        R2_SOC, R2_TempTh = regression_analysis_and_plots(
            general_setup, timeseries, df, case, savefig
        )
        
        Risk_Shortage01 = len(df[df["SOC_end"] <= 0.1]) / len(df)
        print(f"Fraction with SOC<0.1 at the end of the day: {Risk_Shortage01*100}%")
        Risk_Shortage02 = len(df[df["SOC_end"] <= 0.2]) / len(df)
        print(f"Fraction with SOC<0.2 at the end of the day: {Risk_Shortage02*100}%")

        data_row = [HWDP_dist, Risk_Shortage01, Risk_Shortage02, R2_SOC, R2_TempTh]
        data.append(data_row)

    elapsed_time = time.time() - s_time
    print(DAYS, elapsed_time)
    columns = ["HWDP_dist", "Risk_Shortage01",
                    "Risk_Shortage02", "R2_SOC", "R2_TempTh",]
    df_data = pd.DataFrame(data, columns=columns,)
    print(df_data)


if __name__ == '__main__':
    main()