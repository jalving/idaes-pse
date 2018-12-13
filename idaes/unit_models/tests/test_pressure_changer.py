##############################################################################
# Institute for the Design of Advanced Energy Systems Process Systems
# Engineering Framework (IDAES PSE Framework) Copyright (c) 2018, by the
# software owners: The Regents of the University of California, through
# Lawrence Berkeley National Laboratory,  National Technology & Engineering
# Solutions of Sandia, LLC, Carnegie Mellon University, West Virginia
# University Research Corporation, et al. All rights reserved.
#
# Please see the files COPYRIGHT.txt and LICENSE.txt for full copyright and
# license information, respectively. Both files are also available online
# at the URL "https://github.com/IDAES/idaes".
##############################################################################
"""
Tests for Pressure Changer unit model.

Author: Andrew Lee, Emmanuel Ogbe
"""
import pytest
from pyomo.environ import ConcreteModel, SolverFactory, value, Var, Constraint
from idaes.core import FlowsheetBlock, declare_process_block_class, \
                        ControlVolume0D
from idaes.unit_models.pressure_changer import PressureChanger, PressureChangerData
from idaes.ui.report import degrees_of_freedom

# Import property package for testing
from idaes.property_models import iapws95_ph as pp

# -----------------------------------------------------------------------------
# General test classes
@declare_process_block_class("Flowsheet")
class _Flowsheet(FlowsheetBlock):
    def build(self):
        super(_Flowsheet, self).build()

if SolverFactory('ipopt').available():
    solver = SolverFactory('ipopt')
    solver.options = {'tol': 1e-6, 'bound_push': 1e-8}
else:
    solver = None


@pytest.fixture()
def build_presschanger():
    """
    Build a simple flowsheet model for build tests from.
    """
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.props = pp.Iapws95ParameterBlock()
    m.fs.pc = PressureChanger(default={"property_package": m.fs.props})
    return m

def test_build_pc():
    m = build_presschanger()
    assert hasattr(m.fs.pc, "inlet")
    assert hasattr(m.fs.pc, "outlet")
    assert len(m.fs.pc.inlet[0].vars) == 3
    assert len(m.fs.pc.outlet[0].vars) == 3

def test_set_geometry_include_holdup_true():
    m=build_presschanger()
    m.fs.pc.config.has_holdup = True
    super(PressureChangerData, m.fs.pc).build()

def test_make_performance():
    m=build_presschanger()

    assert hasattr(m.fs.pc, "work_mechanical")
    assert m.fs.pc.work_mechanical == m.fs.pc.control_volume.work
    assert hasattr(m.fs.pc, "deltaP")
    assert hasattr(m.fs.pc, "ratioP")
    assert hasattr(m.fs.pc, "ratioP_calculation")


def test_make_isothermal():
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.props = pp.Iapws95ParameterBlock()

    m.fs.pc = PressureChanger(default={"property_package": m.fs.props,
                            "thermodynamic_assumption":'isothermal'})

    assert hasattr(m.fs.pc, "isothermal")

def test_make_pump():
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.props = pp.Iapws95ParameterBlock()

    m.fs.pc = PressureChanger(default={"property_package": m.fs.props,
                            "thermodynamic_assumption":'pump'})

    assert hasattr(m.fs.pc, "work_fluid")
    assert hasattr(m.fs.pc, "efficiency_pump")
    assert hasattr(m.fs.pc, "fluid_work_calculation")
    assert hasattr(m.fs.pc, "actual_work")

def test_make_isentropic():
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.props = pp.Iapws95ParameterBlock()

    m.fs.pc = PressureChanger(default={"property_package": m.fs.props,
                            "thermodynamic_assumption":'isentropic'})

    assert hasattr(m.fs.pc, "efficiency_isentropic")
    assert hasattr(m.fs.pc, "work_isentropic")
    assert hasattr(m.fs.pc, "isentropic_pressure")
    assert hasattr(m.fs.pc, "isentropic_material")
    assert hasattr(m.fs.pc, "isentropic")
    assert hasattr(m.fs.pc, "isentropic_energy_balance")
    assert hasattr(m.fs.pc, "actual_work")


@pytest.mark.skipif(solver is None, reason="Solver not available")
def test_initialization_isothermal():
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.props = pp.Iapws95ParameterBlock()

    m.fs.pc = PressureChanger(default={"property_package": m.fs.props,
                            "thermodynamic_assumption":'isothermal'})
    init_state = {
        "flow_mol":100,
        "pressure":101325,
        "enth_mol":4000
    }
    m.fs.pc.initialize(state_args=init_state, outlvl=5)

    solver.solve(m)

    prop_in = m.fs.pc.control_volume.properties_in[0]
    prop_out = m.fs.pc.control_volume.properties_out[0]

    assert abs(value(prop_in.phase_frac["Liq"]) - 1) <= 1e-6
    assert abs(value(prop_out.phase_frac["Liq"]) - 1) <= 1e-6
    assert abs(value(prop_in.phase_frac["Vap"]) - 0) <= 1e-6
    assert abs(value(prop_out.phase_frac["Vap"]) - 0) <= 1e-6

    assert (pytest.approx(317.6523912867851, abs=1e-2) ==
            m.fs.pc.outlet[0].vars["flow_mol"].value)
    assert (pytest.approx(3999.9999999994984, abs=1e-2) ==
            m.fs.pc.outlet[0].vars["enth_mol"].value)
    assert (pytest.approx(99999.99999999822, abs=1e-2) ==
            m.fs.pc.outlet[0].vars["pressure"].value)

    m.fs.pc.deltaP.fix(-1e7)
    prop_in.enth_mol.fix()
    prop_in.flow_mol.fix()
    prop_in.pressure.fix()

    assert degrees_of_freedom(m) == 0


@pytest.mark.skipif(solver is None, reason="Solver not available")
def test_initialization_pump():
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.props = pp.Iapws95ParameterBlock()

    m.fs.pc = PressureChanger(default={"property_package": m.fs.props,
                            "thermodynamic_assumption":'pump'})
    

    init_state = {
        "flow_mol":3000,
        "pressure":101325,
        "enth_mol":4000
    }

    m.fs.pc.initialize(state_args=init_state, outlvl=5,
                        optarg={'tol': 1e-6})

    assert (pytest.approx(3751.94367345694, abs=1e-2) ==
            m.fs.pc.outlet[0].vars["flow_mol"].value)
    assert (pytest.approx(3460.28609772748, abs=1e-2) ==
            m.fs.pc.outlet[0].vars["enth_mol"].value)
    assert (pytest.approx(100000.01560129, abs=1e-2) ==
            m.fs.pc.outlet[0].vars["pressure"].value)

    solver.solve(m)

    m.fs.pc.inlet[:].flow_mol.fix(27.5e3)
    m.fs.pc.inlet[:].enth_mol.fix(1036.514775)
    m.fs.pc.inlet[:].pressure.fix(101325.0)
    m.fs.pc.deltaP.fix(-1e7)
    m.fs.pc.efficiency_pump.fix(0.9)

    assert degrees_of_freedom(m) == 0


@pytest.mark.skipif(solver is None, reason="Solver not available")
def test_initialization_isentropic():
    m = ConcreteModel()
    m.fs = FlowsheetBlock(default={"dynamic": False})
    m.fs.props = pp.Iapws95ParameterBlock()

    m.fs.pc = PressureChanger(default={"property_package": m.fs.props,
                            "thermodynamic_assumption":'isentropic'})

    init_state = {
        "flow_mol":27500,
        "pressure":1e5,
        "enth_mol":4000
    }
    m.fs.pc.initialize(state_args=init_state, outlvl=5,
                        optarg={'tol': 1e-6})


    assert (pytest.approx(27500.0, abs=1e-2) ==
            m.fs.pc.outlet[0].vars["flow_mol"].value)
    assert (pytest.approx(4000, abs=1e-2) ==
            m.fs.pc.outlet[0].vars["enth_mol"].value)
    assert (pytest.approx(1e5, abs=1e-2) ==
            m.fs.pc.outlet[0].vars["pressure"].value)


    m.fs.pc.deltaP.fix(-1e7)
    m.fs.pc.efficiency_isentropic.fix(0.83)

    assert degrees_of_freedom(m) == 0
    
    solver.solve(m)


#-------------------------------------------------------------------#
