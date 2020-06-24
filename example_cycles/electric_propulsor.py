import openmdao.api as om

import pycycle.api as pyc


class Propulsor(pyc.Cycle):

    def initialize(self):
        self.options.declare('design', types=bool, default=True)

    def setup(self):

        thermo_spec = pyc.species_data.janaf
        design = self.options['design']

        self.pyc_add_element('fc', pyc.FlightConditions(thermo_data=thermo_spec,
                                                  elements=pyc.AIR_MIX))

        self.pyc_add_element('inlet', pyc.Inlet(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('fan', pyc.Compressor(thermo_data=thermo_spec, elements=pyc.AIR_MIX,
                                                 design=design, map_data=pyc.FanMap, map_extrap=True))
        self.pyc_add_element('nozz', pyc.Nozzle(thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('perf', pyc.Performance(num_nozzles=1, num_burners=0))


        balance = om.BalanceComp()
        if design:
            self.add_subsystem('shaft', om.IndepVarComp('Nmech', 1., units='rpm'))
            self.connect('shaft.Nmech', 'fan.Nmech')

            balance.add_balance('W', units='lbm/s', eq_units='hp', val=50., lower=1., upper=500.)
            self.add_subsystem('balance', balance,
                               promotes_inputs=[('rhs:W', 'pwr_target')])
            self.connect('fan.power', 'balance.lhs:W')



        else:
            # vary mass flow till the nozzle area matches the design values
            balance.add_balance('W', units='lbm/s', eq_units='inch**2', val=50, lower=1., upper=500.)
            self.connect('nozz.Throat:stat:area', 'balance.lhs:W')

            balance.add_balance('Nmech', val=1., units='rpm', lower=0.1, upper=2.0, eq_units='hp')
            self.connect('balance.Nmech', 'fan.Nmech')
            self.connect('fan.power', 'balance.lhs:Nmech')

            # self.add_subsystem('shaft', om.IndepVarComp('Nmech', 1., units='rpm'))
            # self.connect('shaft.Nmech', 'fan.Nmech')

            self.add_subsystem('balance', balance,
                               promotes_inputs=[('rhs:Nmech', 'pwr_target')])

        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I')
        self.pyc_connect_flow('inlet.Fl_O', 'fan.Fl_I')
        self.pyc_connect_flow('fan.Fl_O', 'nozz.Fl_I')


        self.connect('fc.Fl_O:stat:P', 'nozz.Ps_exhaust')
        self.connect('inlet.Fl_O:tot:P', 'perf.Pt2')
        self.connect('fan.Fl_O:tot:P', 'perf.Pt3')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('nozz.Fg', 'perf.Fg_0')

        self.connect('balance.W', 'fc.W')

        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-12
        newton.options['rtol'] = 1e-12
        newton.options['iprint'] = 2
        newton.options['maxiter'] = 10
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 10
        newton.options['reraise_child_analysiserror'] = False
        #
        # newton.linesearch = om.ArmijoGoldsteinLS()
        # newton.linesearch.options['maxiter'] = 3
        newton.linesearch = om.BoundsEnforceLS()
        newton.linesearch.options['bound_enforcement'] = 'scalar'
        # newton.linesearch.options['print_bound_enforce'] = True
        # newton.linesearch.options['iprint'] = -1
        #
        self.linear_solver = om.DirectSolver(assemble_jac=True)


def viewer(prob, pt):


    fs_names = ['fc.Fl_O', 'inlet.Fl_O', 'fan.Fl_O', 'nozz.Fl_O']
    fs_full_names = [f'{pt}.{fs}' for fs in fs_names]
    pyc.print_flow_station(prob, fs_full_names)

    pyc.print_compressor(prob, [f'{pt}.fan'])

    pyc.print_nozzle(prob, [f'{pt}.nozz'])


if __name__ == "__main__":
    import time

    import numpy as np

    prob = om.Problem()

    prob.model = pyc.MPCycle()

    design = prob.model.pyc_add_pnt('design', Propulsor(design=True))
    od = prob.model.pyc_add_pnt('off_design', Propulsor(design=False))

    prob.model.pyc_add_cycle_param('pwr_target', 100.)
    prob.model.pyc_use_default_des_od_conns()

    prob.model.pyc_connect_des_od('nozz.Throat:stat:area', 'balance.rhs:W')

    prob.set_solver_print(level=-1)
    prob.set_solver_print(level=2, depth=2)
    # prob.set_solver_print(level=2)

    prob.setup(check=False)
    prob.final_setup()

    prob.set_val('design.fc.alt', 10000, units='m')
    prob['design.fc.MN'] = 0.8
    prob['design.inlet.MN'] = 0.6#
    prob['design.fan.PR'] = 1.2#
    prob['pwr_target'] = -3486.657 # -2600
    prob['design.fan.eff'] = 0.96#

    prob.set_val('off_design.fc.alt', 12000, units='m') #10000
    prob['off_design.fc.MN'] = 0.8#


    design.nonlinear_solver.options['atol'] = 1e-6
    design.nonlinear_solver.options['rtol'] = 1e-6

    od.nonlinear_solver.options['atol'] = 1e-6
    od.nonlinear_solver.options['rtol'] = 1e-6
    # od.nonlinear_solver.options['maxiter'] = 0

    ########################
    # initial guesses
    ########################
    
    prob['design.balance.W'] = 200.

    prob['off_design.balance.W'] = 406.790
    prob['off_design.balance.Nmech'] = 1. # normalized value
    prob['off_design.fan.PR'] = 1.2
    prob['off_design.fan.map.RlineMap'] = 2.2

    st = time.time()
    prob.run_model()
    run_time = time.time() - st

    print("design")

    viewer(prob, 'design')

    print("######"*10)
    print("######"*10)
    print("######"*10)

    viewer(prob, 'off_design')

    print("Run time", run_time)
