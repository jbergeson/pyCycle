import openmdao.api as om

import pycycle.api as pyc


class Propulsor(pyc.Cycle):

    def initialize(self):
        self.options.declare('design', types=bool, default=True)

    def setup(self):

        thermo_spec = pyc.species_data.janaf
        design = self.options['design']
        comp_mode = 'isentropic'

        self.pyc_add_element('fc', pyc.FlightConditions(thermo_data=thermo_spec,
                                                  elements=pyc.AIR_MIX, computation_mode=comp_mode))

        self.pyc_add_element('inlet', pyc.Inlet(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX, computation_mode=comp_mode))
        self.pyc_add_element('fan', pyc.Compressor(thermo_data=thermo_spec, elements=pyc.AIR_MIX,
                                                 design=design, map_data=pyc.FanMap, map_extrap=True, computation_mode=comp_mode))
        self.pyc_add_element('nozz', pyc.Nozzle(thermo_data=thermo_spec, elements=pyc.AIR_MIX, computation_mode=comp_mode))
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
    """
    print a report of all the relevant cycle properties
    """

    fs_names = ['fc.Fl_O', 'inlet.Fl_O', 'fan.Fl_O', 'nozz.Fl_O']
    fs_full_names = [f'{pt}.{fs}' for fs in fs_names]
    pyc.print_flow_station(prob, fs_full_names)

    pyc.print_compressor(prob, [f'{pt}.fan'])

    pyc.print_nozzle(prob, [f'{pt}.nozz'])


class MPpropulsor(pyc.MPCycle):

    def setup(self):

        design = self.pyc_add_pnt('design', Propulsor(design=True))
        self.pyc_add_cycle_param('pwr_target', 100.)

        # define the off-design conditions we want to run
        self.od_pts = ['off_design']
        self.od_MNs = [0.8,]
        self.od_alts = [10000,]
        self.od_Rlines = [2.2,]

        for i, pt in enumerate(self.od_pts):
            self.pyc_add_pnt(pt, Propulsor(design=False))

            self.set_input_defaults(pt+'.fc.MN', val=self.od_MNs[i])
            self.set_input_defaults(pt+'.fc.alt', val=self.od_alts, units='m') 
            self.set_input_defaults(pt+'.fan.map.RlineMap', val=self.od_Rlines[i])        

        self.pyc_use_default_des_od_conns()

        self.pyc_connect_des_od('nozz.Throat:stat:area', 'balance.rhs:W')
        


if __name__ == "__main__":
    import time

    import numpy as np

    prob = om.Problem()

    prob.model = mp_propulsor = MPpropulsor()


    prob.setup()

    #Define the design point
    prob.set_val('design.fc.alt', 10000, units='m')
    prob.set_val('design.fc.MN', 0.8)
    prob.set_val('design.inlet.MN', 0.6)
    prob.set_val('design.fan.PR', 1.2)
    prob.set_val('pwr_target', -3486.657, units='hp')
    prob.set_val('design.fan.eff', 0.96)

    # Set initial guesses for balances
    prob['design.balance.W'] = 200.
    
    for i, pt in enumerate(mp_propulsor.od_pts):
    
        # initial guesses
        prob['off_design.fan.PR'] = 1.2
        prob['off_design.balance.W'] = 406.790
        prob['off_design.balance.Nmech'] = 1. # normalized value

    st = time.time()

    prob.set_solver_print(level=-1)
    prob.set_solver_print(level=2, depth=2)
    prob.model.design.nonlinear_solver.options['atol'] = 1e-6
    prob.model.design.nonlinear_solver.options['rtol'] = 1e-6

    prob.model.off_design.nonlinear_solver.options['atol'] = 1e-6
    prob.model.off_design.nonlinear_solver.options['rtol'] = 1e-6

    prob.set_solver_print(level=2, depth=1)

    prob.run_model()
    run_time = time.time() - st

    for pt in ['design']+mp_propulsor.od_pts:
        print('\n', '#'*10, pt, '#'*10)
        viewer(prob, pt)

    print("Run time", run_time)

    print('Design benchmark values')
    print(prob['design.fc.Fl_O:stat:W'] - 406.79020585)
    print(prob['design.nozz.Fg'] - 12070.38107246)
    print(prob['design.fan.SMN'] - 36.64057531)
    print(prob['design.fan.SMW'] - 29.88606676)
    print('Design flight conditions properties')
    print(prob['design.fc.Fl_O:tot:T'] - 453.21871844)
    print(prob['design.fc.Fl_O:stat:T'] - 401.67024934)
    print(prob['design.fc.Fl_O:tot:P'] - 5.84626037)
    print(prob['design.fc.Fl_O:stat:P'] - 3.83425106)
    print('CEA fc static gamma:', 1.40110464)
    print('Design inlet properties')
    print(prob['design.inlet.Fl_O:tot:T'] - 453.21871844)
    print(prob['design.inlet.Fl_O:stat:T'] - 422.709085)
    print(prob['design.inlet.Fl_O:tot:P'] - 5.84626037)
    print(prob['design.inlet.Fl_O:stat:P'] - 4.58278074)
    print('CEA inlet static gamma:', 1.40101115)
    print('Design fan properties')
    print(prob['design.fan.Fl_O:tot:T'] - 478.49893265)
    print(prob['design.fan.Fl_O:stat:T'] - 455.6711894)
    print(prob['design.fan.Fl_O:tot:P'] - 7.01551245)
    print(prob['design.fan.Fl_O:stat:P'] - 5.91367416)
    print('CEA fan static gamma:', 1.40081197)

    print()

    print('Off design benchmark values')
    print(prob['off_design.fc.Fl_O:stat:W'] - 406.79020585)
    print(prob['off_design.nozz.Fg'] - 12070.38107246)
    print(prob['off_design.fan.SMN'] - 36.64057531)
    print(prob['off_design.fan.SMW'] - 29.88606676)
    print('Off design flight conditions properties')
    print(prob['off_design.fc.Fl_O:tot:T'] - 453.21871844)
    print(prob['off_design.fc.Fl_O:stat:T'] - 401.67024934)
    print(prob['off_design.fc.Fl_O:tot:P'] - 5.84626037)
    print(prob['off_design.fc.Fl_O:stat:P'] - 3.83425106)
    print('CEA fc static gamma:', 1.40110464)
    print('Off design inlet properties')
    print(prob['off_design.inlet.Fl_O:tot:T'] - 453.21871844)
    print(prob['off_design.inlet.Fl_O:stat:T'] - 422.709085)
    print(prob['off_design.inlet.Fl_O:tot:P'] - 5.84626037)
    print(prob['off_design.inlet.Fl_O:stat:P'] - 4.58278074)
    print('CEA inlet static gamma:', 1.40101115)
    print('Off design fan properties')
    print(prob['off_design.fan.Fl_O:tot:T'] - 478.49893265)
    print(prob['off_design.fan.Fl_O:stat:T'] - 455.6711894)
    print(prob['off_design.fan.Fl_O:tot:P'] - 7.01551245)
    print(prob['off_design.fan.Fl_O:stat:P'] - 5.91367416)
    print('CEA fan static gamma:', 1.40081197)

