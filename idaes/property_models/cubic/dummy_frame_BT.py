#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Tue Jul 23 14:36:11 2019

@author: alee
"""

from idaes.core import FlowsheetBlock
from idaes.property_models.cubic import BT_PR_VLE, cubic_prop_pack_VLE

from pyomo.environ import ConcreteModel, SolverFactory


m = ConcreteModel()

m.fs = FlowsheetBlock(default={'dynamic': False})

m.fs.props = BT_PR_VLE.BTParameterBlock(
        default={'valid_phase': ('Vap', 'Liq')})

m.fs.state = m.fs.props.state_block_class(default={'parameters': m.fs.props})

m.fs.state.flow_mol.fix(100)
m.fs.state.mole_frac["benzene"].fix(0.5)
m.fs.state.temperature.fix(368)
m.fs.state.pressure.fix(101325)

m.fs.state.mole_frac["toluene"] = 0.5

print(cubic_prop_pack_VLE.cubic_roots_available())

m.fs.state.initialize()

# Create a solver
solver = SolverFactory('ipopt')
results = solver.solve(m, tee=True)

# Print results
print(results)

m.fs.state.flow_mol_phase.display()
m.fs.state.mole_frac_phase.display()

m.fs.state.temperature_dew.display()
m.fs.state.temperature_bubble.display()
m.fs.state._teq.display()
