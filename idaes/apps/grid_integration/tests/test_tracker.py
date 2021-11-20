import pytest
from collections import deque
import pandas as pd
import pyomo.environ as pyo
from idaes.apps.grid_integration.tracker import Tracker

# declare a testing model class
class TestingModel:

    pmin = 20.00
    pmax = 100.00
    marginal_cost = 30.00

    def __init__(self, horizon = 48):

        '''
        Initializes the class object by building the thermal generator model.

        Arguments:
            rts_gmlc_dataframe: the RTS-GMLC generator data in Pandas DataFrame
            horizon: the length of the planning horizon of the model.
            generator: a generator in RTS-GMLC

        Returns:
            None
        '''

        self.generator = 'test'
        self.horizon = horizon
        self.result_list = []

    def populate_model(self, b):

        '''
        This function builds the model for a thermal generator.

        Arguments:
            plan_horizon: the length of the planning horizon of the model.
            segment_number: number of segments used in the piecewise linear
            production model.

        Returns:
            b: the constructed block.
        '''

        ## define the sets
        b.HOUR = pyo.Set(initialize = range(self.horizon))

        ## define the parameters
        b.marginal_cost = pyo.Param(initialize = self.marginal_cost, mutable = False)

        # capacity of generators: upper bound (MW)
        b.Pmax = pyo.Param(initialize = self.pmax, mutable = False)

        # minimum power of generators: lower bound (MW)
        b.Pmin = pyo.Param(initialize = self.pmin, mutable = False)

        b.pre_P_T = pyo.Param(initialize = self.pmin, mutable = True)

        ## define the variables
        # power generated by thermal generator
        b.P_T = pyo.Var(b.HOUR, initialize = 0, bounds = (self.pmin, self.pmax))

        ## Expression
        def prod_cost_fun(b,h):
            return b.P_T[h] * b.marginal_cost
        b.prod_cost_approx = pyo.Expression(b.HOUR,rule = prod_cost_fun)

        # total cost
        def tot_cost_fun(b,h):
            return b.prod_cost_approx[h]
        b.tot_cost = pyo.Expression(b.HOUR,rule = tot_cost_fun)

        return

    @staticmethod
    def _update_power(b, implemented_power_output):
        '''
        This method updates the parameters in the ramping constraints based on
        the implemented power outputs.

        Arguments:
            b: the block that needs to be updated
            implemented_power_output: realized power outputs: []

         Returns:
             None
        '''

        b.pre_P_T = round(implemented_power_output[-1],2)

        return

    def update_model(self, b, implemented_power_output):

        '''
        This method updates the parameters in the model based on
        the implemented power outputs, shut down and start up events.

        Arguments:
            b: the block that needs to be updated
            implemented_power_output: realized power outputs: []

         Returns:
             None
        '''

        self._update_power(b, implemented_power_output)

        return

    @staticmethod
    def get_implemented_profile(b, last_implemented_time_step):

        '''
        This method gets the implemented variable profiles in the last optimization
        solve.

        Arguments:
            b: the block
            model_var: intended variable name in str
            last_implemented_time_step: time index for the last implemented time
                                        step

         Returns:
             profile: the intended profile, {unit: [...]}
        '''

        implemented_power_output = deque([pyo.value(b.P_T[t]) for t in range(last_implemented_time_step + 1)])

        return {'implemented_power_output': implemented_power_output}

    @staticmethod
    def get_last_delivered_power(b,last_implemented_time_step):

        '''
        Returns the last delivered power output.

        Arguments:
            None

        Returns:
            None
        '''

        return pyo.value(b.P_T[last_implemented_time_step])

    def record_results(self, b, date = None, hour = None, **kwargs):

        '''
        Record the operations stats for the model.

        Arguments:

            date: current simulation date
            hour: current simulation hour

        Returns:
            None

        '''

        df_list = []

        for t in b.HOUR:

            result_dict = {}
            result_dict['Generator'] = self.generator
            result_dict['Date'] = date
            result_dict['Hour'] = hour

            # simulation inputs
            result_dict['Horizon [hr]'] = int(t)

            # model vars
            result_dict['Thermal Power Generated [MW]'] = float(round(pyo.value(b.P_T[t]),2))

            result_dict['Production Cost [$]'] = float(round(pyo.value(b.prod_cost_approx[t]),2))
            result_dict['Total Cost [$]'] = float(round(pyo.value(b.tot_cost[t]),2))

            # calculate mileage
            if t == 0:
                result_dict['Mileage [MW]'] = float(round(abs(pyo.value(b.P_T[t] - b.pre_P_T)),2))
            else:
                result_dict['Mileage [MW]'] = float(round(abs(pyo.value(b.P_T[t] - b.P_T[t-1])),2))

            for key in kwargs:
                result_dict[key] = kwargs[key]

            result_df = pd.DataFrame.from_dict(result_dict,orient = 'index')
            df_list.append(result_df.T)

        # save the result to object property
        # wait to be written when simulation ends
        self.result_list.append(pd.concat(df_list))

        return

    def write_results(self, path):

        '''
        This methods writes the saved operation stats into an csv file.

        Arguments:
            path: the path to write the results.

        Return:
            None
        '''

        pd.concat(self.result_list).to_csv(path, index = False)

    @property
    def power_output(self):
        return 'P_T'

    @property
    def total_cost(self):
        return ('tot_cost',1)

    @property
    def default_bids(self):
        return {p: self.marginal_cost for p in [20.00, 40.00, 60.00, 80.00, 100.00]}

horizon = 4

@pytest.fixture
def tracker_object():

    n_tracking_hour = 1
    solver = pyo.SolverFactory('cbc')

    # create a tracker model
    tracking_model_object = TestingModel(horizon = horizon)
    tracker_object = Tracker(tracking_model_object = tracking_model_object,\
                             n_tracking_hour = n_tracking_hour, \
                             solver = solver)
    return tracker_object

@pytest.mark.component
def test_track_market_dispatch(tracker_object):

    market_dispatch = [30, 40 , 50, 70]
    tracker_object.track_market_dispatch(market_dispatch = market_dispatch, \
                                         date = "2021-07-26", \
                                         hour = '17:00')

    for t, dispatch in zip(range(horizon), market_dispatch):
        assert pytest.approx(pyo.value(tracker_object.power_output[t]),abs = 1e-3) == dispatch

    last_delivered_power = market_dispatch[0]
    assert pytest.approx(tracker_object.get_last_delivered_power(), abs = 1e-3) == last_delivered_power
