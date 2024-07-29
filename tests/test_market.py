import pytest

from tm_solarshift.general import Simulation
from tm_solarshift.timeseries import market

#--------------------
@pytest.mark.parametrize("location, tariff_type", [
    ("Sydney", "flat"),
    ("Sydney", "CL"),
    ("Melbourne", "tou"),
    ("Brisbane", "flat"),
    ("Adelaide", "tou"),
])
def test_load_household_import_rate(location: str, tariff_type: str):
    sim = Simulation()
    sim.household.location = location
    sim.household.tariff_type = tariff_type
    ts_index = sim.time_params.idx
    ts_mkt = market.load_household_import_rate(
        ts_index,
        tariff_type = sim.household.tariff_type,
        dnsp = sim.household.DNSP,
        control_type= sim.household.control_type,
    )
    assert len(ts_mkt[ts_mkt["tariff"].isnull()]) == 0