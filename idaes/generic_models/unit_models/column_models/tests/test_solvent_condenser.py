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
Tests for solvent condenser unit model.
Authors: Andrew Lee
"""

import pytest
from pyomo.environ import (ConcreteModel,
                           Constraint,
                           Param,
                           TerminationCondition,
                           SolverStatus,
                           units,
                           value)
from pyomo.util.check_units import (assert_units_consistent,
                                    assert_units_equivalent)

from idaes.core import FlowsheetBlock
from idaes.generic_models.properties.core.generic.generic_property import (
        GenericParameterBlock)
from idaes.core.util.model_statistics import (degrees_of_freedom,
                                              number_variables,
                                              number_total_constraints,
                                              number_unused_variables)
from idaes.core.util.testing import initialization_tester
from idaes.core.util import get_solver, scaling as iscale

from idaes.generic_models.unit_models.column_models.solvent_condenser import (
    SolventCondenser)
from idaes.power_generation.carbon_capture.mea_solvent_system.properties.MEA_solvent \
    import configuration as aqueous_mea
from idaes.power_generation.carbon_capture.mea_solvent_system.properties.MEA_vapor \
    import wet_co2


# -----------------------------------------------------------------------------
# Get default solver for testing
solver = get_solver()


# -----------------------------------------------------------------------------
class TestStripperVaporFlow(object):
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()
        m.fs = FlowsheetBlock(default={"dynamic": False})

        m.fs.liquid_properties = GenericParameterBlock(default=aqueous_mea)
        m.fs.vapor_properties = GenericParameterBlock(default=wet_co2)

        m.fs.unit = SolventCondenser(default={
            "liquid_property_package": m.fs.liquid_properties,
            "vapor_property_package": m.fs.vapor_properties})

        m.fs.unit.inlet.flow_mol[0].fix(1.1117)
        m.fs.unit.inlet.temperature[0].fix(339.33)
        m.fs.unit.inlet.pressure[0].fix(184360)
        m.fs.unit.inlet.mole_frac_comp[0, "CO2"].fix(0.8817)
        m.fs.unit.inlet.mole_frac_comp[0, "H2O"].fix(0.1183)

        m.fs.unit.reflux.flow_mol[0].fix(0.1083)

        return m

    @pytest.mark.build
    @pytest.mark.unit
    def test_build(self, model):

        assert hasattr(model.fs.unit, "inlet")
        assert len(model.fs.unit.inlet.vars) == 4
        assert hasattr(model.fs.unit.inlet, "flow_mol")
        assert hasattr(model.fs.unit.inlet, "mole_frac_comp")
        assert hasattr(model.fs.unit.inlet, "temperature")
        assert hasattr(model.fs.unit.inlet, "pressure")

        assert hasattr(model.fs.unit, "reflux")
        assert len(model.fs.unit.reflux.vars) == 4
        assert hasattr(model.fs.unit.reflux, "flow_mol")
        assert hasattr(model.fs.unit.reflux, "mole_frac_comp")
        assert hasattr(model.fs.unit.reflux, "temperature")
        assert hasattr(model.fs.unit.reflux, "pressure")

        assert hasattr(model.fs.unit, "vapor_outlet")
        assert len(model.fs.unit.vapor_outlet.vars) == 4
        assert hasattr(model.fs.unit.vapor_outlet, "flow_mol")
        assert hasattr(model.fs.unit.vapor_outlet, "mole_frac_comp")
        assert hasattr(model.fs.unit.vapor_outlet, "temperature")
        assert hasattr(model.fs.unit.vapor_outlet, "pressure")

        assert isinstance(model.fs.unit.unit_material_balance, Constraint)
        assert isinstance(model.fs.unit.unit_enthalpy_balance, Constraint)
        assert isinstance(model.fs.unit.unit_temperature_equality, Constraint)
        assert isinstance(model.fs.unit.unit_pressure_balance, Constraint)
        assert isinstance(model.fs.unit.zero_flow_param, Param)

        assert number_variables(model.fs.unit) == 55
        assert number_total_constraints(model.fs.unit) == 49
        assert number_unused_variables(model.fs.unit) == 0

    @pytest.mark.component
    def test_units(self, model):
        assert_units_consistent(model)
        assert_units_equivalent(model.fs.unit.heat_duty[0], units.W)

    @pytest.mark.unit
    def test_dof(self, model):
        assert degrees_of_freedom(model) == 0

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_initialize(self, model):
        initialization_tester(model)

    # @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solve(self, model):
        results = solver.solve(model)

        # Check for optimal solution
        assert results.solver.termination_condition == \
            TerminationCondition.optimal
        assert results.solver.status == SolverStatus.ok

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        assert (pytest.approx(0.1083, rel=1e-5) ==
                value(model.fs.unit.reflux.flow_mol[0]))
        assert (pytest.approx(0, abs=1e-3) ==
                value(model.fs.unit.reflux.mole_frac_comp[0, 'CO2']))
        assert (pytest.approx(0, abs=1e-3) ==
                value(model.fs.unit.reflux.mole_frac_comp[0, 'MEA']))
        assert (pytest.approx(1, rel=1e-3) ==
                value(model.fs.unit.reflux.mole_frac_comp[0, 'H2O']))
        assert (pytest.approx(184360, rel=1e-5) ==
                value(model.fs.unit.reflux.pressure[0]))
        assert (pytest.approx(303.244, rel=1e-5) ==
                value(model.fs.unit.reflux.temperature[0]))

        assert (pytest.approx(1.0034, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.flow_mol[0]))
        assert (pytest.approx(0.976758, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.mole_frac_comp[0, 'CO2']))
        assert (pytest.approx(0.0232416, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.mole_frac_comp[0, 'H2O']))
        assert (pytest.approx(184360, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.pressure[0]))
        assert (pytest.approx(303.244, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.temperature[0]))

        assert (pytest.approx(-6264.72, rel=1e-5) ==
                value(model.fs.unit.heat_duty[0]))

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_conservation(self, model):
        assert abs(value(model.fs.unit.inlet.flow_mol[0] -
                         model.fs.unit.reflux.flow_mol[0] -
                         model.fs.unit.vapor_outlet.flow_mol[0])) <= 1e-6

        assert (abs(value(model.fs.unit.inlet.flow_mol[0] *
                          model.fs.unit.inlet.mole_frac_comp[0, "CO2"] -
                          model.fs.unit.reflux.flow_mol[0] *
                          model.fs.unit.reflux.mole_frac_comp[0, "CO2"] -
                          model.fs.unit.vapor_outlet.flow_mol[0] *
                          model.fs.unit.vapor_outlet.mole_frac_comp[0, "CO2"]))
                <= 1e-6)
        assert (abs(value(model.fs.unit.inlet.flow_mol[0] *
                          model.fs.unit.inlet.mole_frac_comp[0, "H2O"] -
                          model.fs.unit.reflux.flow_mol[0] *
                          model.fs.unit.reflux.mole_frac_comp[0, "H2O"] -
                          model.fs.unit.vapor_outlet.flow_mol[0] *
                          model.fs.unit.vapor_outlet.mole_frac_comp[0, "H2O"]))
                <= 1e-6)
        assert (abs(value(model.fs.unit.reflux.flow_mol[0] *
                          model.fs.unit.reflux.mole_frac_comp[0, "MEA"]))
                <= 1e-6)

        assert abs(value(
            model.fs.unit.vapor_phase.properties_in[0]._enthalpy_flow_term[
                "Vap"] -
            model.fs.unit.vapor_phase.properties_out[0]._enthalpy_flow_term[
                "Vap"] -
            model.fs.unit.liquid_phase[0]._enthalpy_flow_term["Liq"] +
            model.fs.unit.heat_duty[0])) <= 1e-6


# -----------------------------------------------------------------------------
class TestStripperHeatDuty(object):
    @pytest.fixture(scope="class")
    def model(self):
        m = ConcreteModel()
        m.fs = FlowsheetBlock(default={"dynamic": False})

        m.fs.liquid_properties = GenericParameterBlock(default=aqueous_mea)
        m.fs.vapor_properties = GenericParameterBlock(default=wet_co2)

        m.fs.unit = SolventCondenser(default={
            "liquid_property_package": m.fs.liquid_properties,
            "vapor_property_package": m.fs.vapor_properties})

        m.fs.unit.inlet.flow_mol[0].fix(1.1117)
        m.fs.unit.inlet.temperature[0].fix(339.33)
        m.fs.unit.inlet.pressure[0].fix(184360)
        m.fs.unit.inlet.mole_frac_comp[0, "CO2"].fix(0.8817)
        m.fs.unit.inlet.mole_frac_comp[0, "H2O"].fix(0.1183)

        m.fs.unit.heat_duty.fix(-6264)

        return m

    @pytest.mark.build
    @pytest.mark.unit
    def test_build(self, model):

        assert hasattr(model.fs.unit, "inlet")
        assert len(model.fs.unit.inlet.vars) == 4
        assert hasattr(model.fs.unit.inlet, "flow_mol")
        assert hasattr(model.fs.unit.inlet, "mole_frac_comp")
        assert hasattr(model.fs.unit.inlet, "temperature")
        assert hasattr(model.fs.unit.inlet, "pressure")

        assert hasattr(model.fs.unit, "reflux")
        assert len(model.fs.unit.reflux.vars) == 4
        assert hasattr(model.fs.unit.reflux, "flow_mol")
        assert hasattr(model.fs.unit.reflux, "mole_frac_comp")
        assert hasattr(model.fs.unit.reflux, "temperature")
        assert hasattr(model.fs.unit.reflux, "pressure")

        assert hasattr(model.fs.unit, "vapor_outlet")
        assert len(model.fs.unit.vapor_outlet.vars) == 4
        assert hasattr(model.fs.unit.vapor_outlet, "flow_mol")
        assert hasattr(model.fs.unit.vapor_outlet, "mole_frac_comp")
        assert hasattr(model.fs.unit.vapor_outlet, "temperature")
        assert hasattr(model.fs.unit.vapor_outlet, "pressure")

        assert isinstance(model.fs.unit.unit_material_balance, Constraint)
        assert isinstance(model.fs.unit.unit_enthalpy_balance, Constraint)
        assert isinstance(model.fs.unit.unit_temperature_equality, Constraint)
        assert isinstance(model.fs.unit.unit_pressure_balance, Constraint)
        assert isinstance(model.fs.unit.zero_flow_param, Param)

        assert number_variables(model.fs.unit) == 55
        assert number_total_constraints(model.fs.unit) == 49
        assert number_unused_variables(model.fs.unit) == 0

    @pytest.mark.component
    def test_units(self, model):
        assert_units_consistent(model)
        assert_units_equivalent(model.fs.unit.heat_duty[0], units.W)

    @pytest.mark.unit
    def test_dof(self, model):
        assert degrees_of_freedom(model) == 0

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_initialize(self, model):
        initialization_tester(model)

    # @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solve(self, model):
        results = solver.solve(model)

        # Check for optimal solution
        assert results.solver.termination_condition == \
            TerminationCondition.optimal
        assert results.solver.status == SolverStatus.ok

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_solution(self, model):
        assert (pytest.approx(0.108291, rel=1e-5) ==
                value(model.fs.unit.reflux.flow_mol[0]))
        assert (pytest.approx(0, abs=1e-3) ==
                value(model.fs.unit.reflux.mole_frac_comp[0, 'CO2']))
        assert (pytest.approx(0, abs=1e-3) ==
                value(model.fs.unit.reflux.mole_frac_comp[0, 'MEA']))
        assert (pytest.approx(1, rel=1e-3) ==
                value(model.fs.unit.reflux.mole_frac_comp[0, 'H2O']))
        assert (pytest.approx(184360, rel=1e-5) ==
                value(model.fs.unit.reflux.pressure[0]))
        assert (pytest.approx(303.250, rel=1e-5) ==
                value(model.fs.unit.reflux.temperature[0]))

        assert (pytest.approx(1.0034, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.flow_mol[0]))
        assert (pytest.approx(0.976758, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.mole_frac_comp[0, 'CO2']))
        assert (pytest.approx(0.0232505, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.mole_frac_comp[0, 'H2O']))
        assert (pytest.approx(184360, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.pressure[0]))
        assert (pytest.approx(303.250, rel=1e-5) ==
                value(model.fs.unit.vapor_outlet.temperature[0]))

        assert (pytest.approx(-6264, rel=1e-5) ==
                value(model.fs.unit.heat_duty[0]))

    @pytest.mark.solver
    @pytest.mark.skipif(solver is None, reason="Solver not available")
    @pytest.mark.component
    def test_conservation(self, model):
        assert abs(value(model.fs.unit.inlet.flow_mol[0] -
                         model.fs.unit.reflux.flow_mol[0] -
                         model.fs.unit.vapor_outlet.flow_mol[0])) <= 1e-6

        assert (abs(value(model.fs.unit.inlet.flow_mol[0] *
                          model.fs.unit.inlet.mole_frac_comp[0, "CO2"] -
                          model.fs.unit.reflux.flow_mol[0] *
                          model.fs.unit.reflux.mole_frac_comp[0, "CO2"] -
                          model.fs.unit.vapor_outlet.flow_mol[0] *
                          model.fs.unit.vapor_outlet.mole_frac_comp[0, "CO2"]))
                <= 1e-6)
        assert (abs(value(model.fs.unit.inlet.flow_mol[0] *
                          model.fs.unit.inlet.mole_frac_comp[0, "H2O"] -
                          model.fs.unit.reflux.flow_mol[0] *
                          model.fs.unit.reflux.mole_frac_comp[0, "H2O"] -
                          model.fs.unit.vapor_outlet.flow_mol[0] *
                          model.fs.unit.vapor_outlet.mole_frac_comp[0, "H2O"]))
                <= 1e-6)
        assert (abs(value(model.fs.unit.reflux.flow_mol[0] *
                          model.fs.unit.reflux.mole_frac_comp[0, "MEA"]))
                <= 1e-6)

        assert abs(value(
            model.fs.unit.vapor_phase.properties_in[0]._enthalpy_flow_term[
                "Vap"] -
            model.fs.unit.vapor_phase.properties_out[0]._enthalpy_flow_term[
                "Vap"] -
            model.fs.unit.liquid_phase[0]._enthalpy_flow_term["Liq"] +
            model.fs.unit.heat_duty[0])) <= 1e-6

    @pytest.mark.component
    def test_scaling(self, model):
        iscale.set_scaling_factor(
            model.fs.unit.vapor_phase.properties_out[0].fug_phase_comp[
                "Vap", "CO2"], 1e-5)
        iscale.set_scaling_factor(
            model.fs.unit.vapor_phase.properties_out[0].fug_phase_comp[
                "Vap", "H2O"], 1e-3)

        iscale.calculate_scaling_factors(model.fs.unit)

        assert iscale.get_constraint_transform_applied_scaling_factor(
            model.fs.unit.unit_material_balance[0, "CO2"]) == 1
        assert iscale.get_constraint_transform_applied_scaling_factor(
            model.fs.unit.unit_material_balance[0, "H2O"]) == 1
        assert iscale.get_constraint_transform_applied_scaling_factor(
            model.fs.unit.unit_material_balance[0, "MEA"]) == 1e8

        assert iscale.get_constraint_transform_applied_scaling_factor(
            model.fs.unit.unit_phase_equilibrium[0, "CO2"]) == 1e-5
        assert iscale.get_constraint_transform_applied_scaling_factor(
            model.fs.unit.unit_phase_equilibrium[0, "H2O"]) == 1e-3

        assert iscale.get_constraint_transform_applied_scaling_factor(
            model.fs.unit.unit_temperature_equality[0]) == 1e-2

        assert iscale.get_constraint_transform_applied_scaling_factor(
            model.fs.unit.unit_enthalpy_balance[0]) == 1

        assert iscale.get_constraint_transform_applied_scaling_factor(
            model.fs.unit.unit_pressure_balance[0]) == 1e-5
