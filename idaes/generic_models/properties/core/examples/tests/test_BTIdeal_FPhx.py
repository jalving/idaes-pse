#################################################################################
# The Institute for the Design of Advanced Energy Systems Integrated Platform
# Framework (IDAES IP) was produced under the DOE Institute for the
# Design of Advanced Energy Systems (IDAES), and is copyright (c) 2018-2021
# by the software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia University
# Research Corporation, et al.  All rights reserved.
#
# Please see the files COPYRIGHT.md and LICENSE.md for full copyright and
# license information.
#################################################################################
"""
Author: Andrew Lee
"""
import pytest
from pyomo.environ import (ConcreteModel,
                           Set,
                           SolverStatus,
                           TerminationCondition,
                           value,
                           Var,
                           units as pyunits)
from pyomo.util.check_units import assert_units_consistent
from pyomo.common.unittest import assertStructuredAlmostEqual

from idaes.core import Component
from idaes.core.util.model_statistics import (degrees_of_freedom,
                                              fixed_variables_set,
                                              activated_constraints_set)
from idaes.core.util import get_solver

from idaes.core import LiquidPhase, VaporPhase

from idaes.generic_models.properties.core.generic.generic_property import (
        GenericParameterBlock)

from idaes.generic_models.properties.core.state_definitions import FPhx
from idaes.generic_models.properties.core.eos.ideal import Ideal
from idaes.generic_models.properties.core.phase_equil import SmoothVLE
from idaes.generic_models.properties.core.phase_equil.bubble_dew import (
        IdealBubbleDew)
from idaes.generic_models.properties.core.phase_equil.forms import fugacity

import idaes.generic_models.properties.core.pure.Perrys as Perrys
import idaes.generic_models.properties.core.pure.RPP4 as RPP4


# -----------------------------------------------------------------------------
# Get default solver for testing
solver = get_solver()

def _as_quantity(x):
    unit = pyunits.get_units(x)
    if unit is None:
        unit = pyunits.dimensionless
    return value(x) * unit._get_pint_unit()

config_dict = {
    "components": {
        'benzene': {
            "type": Component,
            "dens_mol_liq_comp": Perrys,
            "enth_mol_liq_comp": Perrys,
            "enth_mol_ig_comp": RPP4,
            "pressure_sat_comp": RPP4,
            "phase_equilibrium_form": {("Vap", "Liq"): fugacity},
            "parameter_data": {
                "mw": 78.1136E-3,  # [1]
                "pressure_crit": 48.9e5,  # [1]
                "temperature_crit": 562.2,  # [1]
                "dens_mol_liq_comp_coeff": {'1': 1.0162,  # [2] pg. 2-98
                                            '2': 0.2655,
                                            '3': 562.16,
                                            '4': 0.28212},
                "cp_mol_ig_comp_coeff": {'A': -3.392E1,  # [1]
                                         'B': 4.739E-1,
                                         'C': -3.017E-4,
                                         'D': 7.130E-8},
                "cp_mol_liq_comp_coeff": {'1': 1.29E2,  # [2]
                                          '2': -1.7E-1,
                                          '3': 6.48E-4,
                                          '4': 0,
                                          '5': 0},
                "enth_mol_form_liq_comp_ref": 49.0e3,  # [3]
                "enth_mol_form_vap_comp_ref": 82.9e3,  # [3]
                "pressure_sat_comp_coeff": {'A': -6.98273,  # [1]
                                            'B': 1.33213,
                                            'C': -2.62863,
                                            'D': -3.33399}}},
        'toluene': {
            "type": Component,
            "dens_mol_liq_comp": Perrys,
            "enth_mol_liq_comp": Perrys,
            "enth_mol_ig_comp": RPP4,
            "pressure_sat_comp": RPP4,
            "phase_equilibrium_form": {("Vap", "Liq"): fugacity},
            "parameter_data": {
                "mw": 92.1405E-3,  # [1]
                "pressure_crit": 41e5,  # [1]
                "temperature_crit": 591.8,  # [1]
                "dens_mol_liq_comp_coeff": {'1': 0.8488,  # [2] pg. 2-98
                                            '2': 0.26655,
                                            '3': 591.8,
                                            '4': 0.2878},
                "cp_mol_ig_comp_coeff": {'A': -2.435E1,
                                         'B': 5.125E-1,
                                         'C': -2.765E-4,
                                         'D': 4.911E-8},
                "cp_mol_liq_comp_coeff": {'1': 1.40E2,  # [2]
                                          '2': -1.52E-1,
                                          '3': 6.95E-4,
                                          '4': 0,
                                          '5': 0},
                "enth_mol_form_liq_comp_ref": 12.0e3,  # [3]
                "enth_mol_form_vap_comp_ref": 50.1e3,  # [3]
                "pressure_sat_comp_coeff": {'A': -7.28607,  # [1]
                                            'B': 1.38091,
                                            'C': -2.83433,
                                            'D': -2.79168}}}},
    "phases":  {'Liq': {"type": LiquidPhase,
                        "equation_of_state": Ideal},
                'Vap': {"type": VaporPhase,
                        "equation_of_state": Ideal}},
    "base_units": {"time": pyunits.s,
                   "length": pyunits.m,
                   "mass": pyunits.kg,
                   "amount": pyunits.mol,
                   "temperature": pyunits.K},
    "state_definition": FPhx,
    "state_bounds": {"flow_mol": (0, 100, 1000, pyunits.mol/pyunits.s),
                     "enth_mol": (1e4, 5e4, 2e5, pyunits.J/pyunits.mol),
                     "temperature": (273.15, 300, 450, pyunits.K),
                     "pressure": (5e4, 1e5, 1e6, pyunits.Pa)},
    "pressure_ref": 1e5,
    "temperature_ref": 300,
    "phases_in_equilibrium": [("Vap", "Liq")],
    "phase_equilibrium_state": {("Vap", "Liq"): SmoothVLE},
    "bubble_dew_method": IdealBubbleDew}


class TestParamBlock(object):
    @pytest.mark.unit
    def test_build(self):
        model = ConcreteModel()
        model.params = GenericParameterBlock(default=config_dict)

        assert isinstance(model.params.phase_list, Set)
        assert len(model.params.phase_list) == 2
        for i in model.params.phase_list:
            assert i in ["Liq", "Vap"]
        assert model.params.Liq.is_liquid_phase()
        assert model.params.Vap.is_vapor_phase()

        assert isinstance(model.params.component_list, Set)
        assert len(model.params.component_list) == 2
        for i in model.params.component_list:
            assert i in ['benzene',
                         'toluene']
            assert isinstance(model.params.get_component(i), Component)

        assert isinstance(model.params._phase_component_set, Set)
        assert len(model.params._phase_component_set) == 4
        for i in model.params._phase_component_set:
            assert i in [("Liq", "benzene"), ("Liq", "toluene"),
                         ("Vap", "benzene"), ("Vap", "toluene")]

        assert model.params.config.state_definition == FPhx

        assertStructuredAlmostEqual(
            model.params.config.state_bounds,
            { "flow_mol": (0, 100, 1000, pyunits.mol/pyunits.s),
              "enth_mol": (1e4, 5e4, 2e5, pyunits.J/pyunits.mol),
              "temperature": (273.15, 300, 450, pyunits.K),
              "pressure": (5e4, 1e5, 1e6, pyunits.Pa) },
            item_callback=_as_quantity,
        )

        assert model.params.config.phase_equilibrium_state == {
            ("Vap", "Liq"): SmoothVLE}

        assert isinstance(model.params.phase_equilibrium_idx, Set)
        assert len(model.params.phase_equilibrium_idx) == 2
        for i in model.params.phase_equilibrium_idx:
            assert i in ["PE1", "PE2"]

        assert model.params.phase_equilibrium_list == {
            "PE1": {"benzene": ("Vap", "Liq")},
            "PE2": {"toluene": ("Vap", "Liq")}}

        assert model.params.pressure_ref.value == 1e5
        assert model.params.temperature_ref.value == 300

        assert_units_consistent(model)


class TestStateBlock(object):
    @pytest.fixture(scope="class")
    def model(self):
        model = ConcreteModel()
        model.params = GenericParameterBlock(default=config_dict)

        model.props = model.params.state_block_class(
                [1],
                default={"parameters": model.params,
                         "defined_state": True})

        model.props[1].calculate_scaling_factors()

        # Fix state
        model.props[1].flow_mol.fix(1)
        model.props[1].enth_mol.fix(47297)
        model.props[1].pressure.fix(101325)
        model.props[1].mole_frac_comp["benzene"].fix(0.5)
        model.props[1].mole_frac_comp["toluene"].fix(0.5)

        return model

    @pytest.mark.unit
    def test_build(self, model):
        # Check state variable values and bounds
        assert isinstance(model.props[1].flow_mol, Var)
        assert value(model.props[1].flow_mol) == 1
        assert model.props[1].flow_mol.ub == 1000
        assert model.props[1].flow_mol.lb == 0

        assert isinstance(model.props[1].pressure, Var)
        assert value(model.props[1].pressure) == 101325
        assert model.props[1].pressure.ub == 1e6
        assert model.props[1].pressure.lb == 5e4

        assert isinstance(model.props[1].enth_mol, Var)
        assert value(model.props[1].enth_mol) == 47297
        assert model.props[1].enth_mol.ub == 2e5
        assert model.props[1].enth_mol.lb == 1e4

        assert isinstance(model.props[1].temperature, Var)
        assert value(model.props[1].temperature) == 300
        assert model.props[1].temperature.ub == 450
        assert model.props[1].temperature.lb == 273.15

        assert isinstance(model.props[1].mole_frac_comp, Var)
        assert len(model.props[1].mole_frac_comp) == 2
        for i in model.props[1].mole_frac_comp:
            assert value(model.props[1].mole_frac_comp[i]) == 0.5

        assert_units_consistent(model)

    @pytest.mark.unit
    def test_basic_scaling(self, model):
        assert len(model.props[1].scaling_factor) == 26

        assert model.props[1].scaling_factor[
            model.props[1]._mole_frac_tbub["Vap", "Liq", "benzene"]] == 1000
        assert model.props[1].scaling_factor[
            model.props[1]._mole_frac_tbub["Vap", "Liq", "toluene"]] == 1000
        assert model.props[1].scaling_factor[
            model.props[1]._mole_frac_tdew["Vap", "Liq", "benzene"]] == 1000
        assert model.props[1].scaling_factor[
            model.props[1]._mole_frac_tdew["Vap", "Liq", "toluene"]] == 1000
        assert model.props[1].scaling_factor[
            model.props[1]._t1_Vap_Liq] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1]._teq["Vap", "Liq"]] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].dens_mol_phase["Liq"]] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].dens_mol_phase["Vap"]] == 1e-2
        assert model.props[1].scaling_factor[model.props[1].enth_mol] == 1e-4
        assert model.props[1].scaling_factor[model.props[1].flow_mol] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].flow_mol_phase["Liq"]] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].flow_mol_phase["Vap"]] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].flow_mol_phase_comp["Liq", "benzene"]] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].flow_mol_phase_comp["Liq", "toluene"]] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].flow_mol_phase_comp["Vap", "benzene"]] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].flow_mol_phase_comp["Vap", "toluene"]] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].mole_frac_comp["benzene"]] == 1000
        assert model.props[1].scaling_factor[
            model.props[1].mole_frac_comp["toluene"]] == 1000
        assert model.props[1].scaling_factor[
            model.props[1].mole_frac_phase_comp["Liq", "benzene"]] == 1000
        assert model.props[1].scaling_factor[
            model.props[1].mole_frac_phase_comp["Liq", "toluene"]] == 1000
        assert model.props[1].scaling_factor[
            model.props[1].mole_frac_phase_comp["Vap", "benzene"]] == 1000
        assert model.props[1].scaling_factor[
            model.props[1].mole_frac_phase_comp["Vap", "toluene"]] == 1000
        assert model.props[1].scaling_factor[model.props[1].pressure] == 1e-5
        assert model.props[1].scaling_factor[
            model.props[1].temperature] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].temperature_bubble["Vap", "Liq"]] == 1e-2
        assert model.props[1].scaling_factor[
            model.props[1].temperature_dew["Vap", "Liq"]] == 1e-2

    @pytest.mark.unit
    def test_define_state_vars(self, model):
        sv = model.props[1].define_state_vars()

        assert len(sv) == 4
        for i in sv:
            assert i in ["flow_mol",
                         "enth_mol",
                         "pressure",
                         "mole_frac_comp"]

    @pytest.mark.unit
    def test_define_port_members(self, model):
        sv = model.props[1].define_state_vars()

        assert len(sv) == 4
        for i in sv:
            assert i in ["flow_mol",
                         "enth_mol",
                         "pressure",
                         "mole_frac_comp"]

    @pytest.mark.unit
    def test_define_display_vars(self, model):
        sv = model.props[1].define_display_vars()

        assert len(sv) == 4
        for i in sv:
            assert i in ["Total Molar Flowrate",
                         "Molar Enthalpy",
                         "Pressure",
                         "Total Mole Fraction"]

    @pytest.mark.unit
    def test_dof(self, model):
        assert degrees_of_freedom(model.props[1]) == 0

    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_initialize(self, model):
        orig_fixed_vars = fixed_variables_set(model)
        orig_act_consts = activated_constraints_set(model)

        model.props.initialize(optarg={'tol': 1e-6})

        assert degrees_of_freedom(model) == 0

        fin_fixed_vars = fixed_variables_set(model)
        fin_act_consts = activated_constraints_set(model)

        assert len(fin_act_consts) == len(orig_act_consts)
        assert len(fin_fixed_vars) == len(orig_fixed_vars)

        for c in fin_act_consts:
            assert c in orig_act_consts
        for v in fin_fixed_vars:
            assert v in orig_fixed_vars

    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solve(self, model):
        results = solver.solve(model)

        # Check for optimal solution
        assert results.solver.termination_condition == \
            TerminationCondition.optimal
        assert results.solver.status == SolverStatus.ok

    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        # Check phase equilibrium results
        assert model.props[1].mole_frac_phase_comp["Liq", "benzene"].value == \
            pytest.approx(0.4121, abs=1e-4)
        assert model.props[1].mole_frac_phase_comp["Vap", "benzene"].value == \
            pytest.approx(0.6339, abs=1e-4)
        assert model.props[1].phase_frac["Vap"].value == \
            pytest.approx(0.3961, abs=1e-4)

    @pytest.mark.ui
    @pytest.mark.unit
    def test_report(self, model):
        model.props[1].report()
