import sys

import openmdao.api as om

import pycycle.api as pyc

class Turboshaft(pyc.Cycle):

    def initialize(self):
        self.options.declare('design', default=True,
                              desc='Switch between on-design and off-design calculation.')

    def setup(self):

        thermo_spec = pyc.species_data.janaf
        design = self.options['design']

        # Add engine elements
        self.pyc_add_element('fc', pyc.FlightConditions(thermo_data=thermo_spec,
                                    elements=pyc.AIR_MIX))
        self.pyc_add_element('inlet', pyc.Inlet(design=design, thermo_data=thermo_spec,
                                    elements=pyc.AIR_MIX))
        self.pyc_add_element('comp', pyc.Compressor(map_data=pyc.AXI5, design=design,
                                    thermo_data=thermo_spec, elements=pyc.AIR_MIX, map_extrap=True),
                                    promotes_inputs=[('Nmech', 'HP_Nmech')])
        self.pyc_add_element('burner', pyc.Combustor(design=design,thermo_data=thermo_spec,
                                    inflow_elements=pyc.AIR_MIX,
                                    air_fuel_elements=pyc.AIR_FUEL_MIX,
                                    fuel_type='JP-7'))
        self.pyc_add_element('turb', pyc.Turbine(map_data=pyc.LPT2269, design=design,
                                    thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX, map_extrap=True),
                                    promotes_inputs=[('Nmech', 'HP_Nmech')])
        self.pyc_add_element('pt', pyc.Turbine(map_data=pyc.LPT2269, design=design,
                                    thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX, map_extrap=True),
                                    promotes_inputs=[('Nmech', 'LP_Nmech')])
        self.pyc_add_element('nozz', pyc.Nozzle(nozzType='CV', lossCoef='Cv',
                                    thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))
        self.pyc_add_element('HP_shaft', pyc.Shaft(num_ports=2),promotes_inputs=[('Nmech', 'HP_Nmech')])
        self.pyc_add_element('LP_shaft', pyc.Shaft(num_ports=1),promotes_inputs=[('Nmech', 'LP_Nmech')])
        self.pyc_add_element('perf', pyc.Performance(num_nozzles=1, num_burners=1))

        # Connect flow stations
        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I', connect_w=False)
        self.pyc_connect_flow('inlet.Fl_O', 'comp.Fl_I')
        self.pyc_connect_flow('comp.Fl_O', 'burner.Fl_I')
        self.pyc_connect_flow('burner.Fl_O', 'turb.Fl_I')
        self.pyc_connect_flow('turb.Fl_O', 'pt.Fl_I')
        self.pyc_connect_flow('pt.Fl_O', 'nozz.Fl_I')

        # Connect turbomachinery elements to shaft
        self.connect('comp.trq', 'HP_shaft.trq_0')
        self.connect('turb.trq', 'HP_shaft.trq_1')
        self.connect('pt.trq', 'LP_shaft.trq_0')

        # Connnect nozzle exhaust to freestream static conditions
        self.connect('fc.Fl_O:stat:P', 'nozz.Ps_exhaust')

        # Connect outputs to pefromance element
        self.connect('inlet.Fl_O:tot:P', 'perf.Pt2')
        self.connect('comp.Fl_O:tot:P', 'perf.Pt3')
        self.connect('burner.Wfuel', 'perf.Wfuel_0')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('nozz.Fg', 'perf.Fg_0')
        self.connect('LP_shaft.pwr_net', 'perf.power')

        # Add balances for design and off-design
        balance = self.add_subsystem('balance', om.BalanceComp())
        if design:

            balance.add_balance('W', val=27.0, units='lbm/s', eq_units=None, rhs_name='nozz_PR_target')
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('nozz.PR', 'balance.lhs:W')

            balance.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017, rhs_name='T4_target')
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')

            balance.add_balance('turb_PR', val=3.0, lower=1.001, upper=8, eq_units='hp', rhs_val=0.)
            self.connect('balance.turb_PR', 'turb.PR')
            self.connect('HP_shaft.pwr_net', 'balance.lhs:turb_PR')

            balance.add_balance('pt_PR', val=3.0, lower=1.001, upper=8, eq_units='hp', rhs_name='pwr_target')
            self.connect('balance.pt_PR', 'pt.PR')
            self.connect('LP_shaft.pwr_net', 'balance.lhs:pt_PR')

        else:

            balance.add_balance('FAR', eq_units='hp', lower=1e-4, val=.3, rhs_name='pwr_target')
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('LP_shaft.pwr_net', 'balance.lhs:FAR')

            balance.add_balance('HP_Nmech', val=1.5, units='rpm', lower=500., eq_units='hp', rhs_val=0.)
            self.connect('balance.HP_Nmech', 'HP_Nmech')
            self.connect('HP_shaft.pwr_net', 'balance.lhs:HP_Nmech')

            balance.add_balance('W', val=27.0, units='lbm/s', eq_units='inch**2')
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('nozz.Throat:stat:area', 'balance.lhs:W')

        # Setup solver to converge engine
        self.set_order(['balance', 'fc', 'inlet', 'comp', 'burner', 'turb', 'pt', 'nozz', 'HP_shaft', 'LP_shaft', 'perf'])

        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-6
        newton.options['rtol'] = 1e-6
        newton.options['iprint'] = 2
        newton.options['maxiter'] = 15
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 100
        newton.options['reraise_child_analysiserror'] = False

        # newton.linesearch = om.BoundsEnforceLS()
        newton.linesearch = om.ArmijoGoldsteinLS()
        # newton.linesearch.options['c'] = .0001
        newton.linesearch.options['bound_enforcement'] = 'scalar'
        newton.linesearch.options['iprint'] = -1

        self.linear_solver = om.DirectSolver(assemble_jac=True)

def viewer(prob, pt, file=sys.stdout):
    """
    print a report of all the relevant cycle properties
    """

    print(file=file, flush=True)
    print(file=file, flush=True)
    print(file=file, flush=True)
    print("----------------------------------------------------------------------------", file=file, flush=True)
    print("                              POINT:", pt, file=file, flush=True)
    print("----------------------------------------------------------------------------", file=file, flush=True)
    print("                       PERFORMANCE CHARACTERISTICS", file=file, flush=True)
    print("    Mach      Alt       W      Fn      Fg    Fram     OPR     PSFC ")
    print(" %7.5f  %7.1f %7.3f %7.1f %7.1f %7.1f %7.3f  %7.5f" \
                %(prob[pt+'.fc.Fl_O:stat:MN'], prob[pt+'.fc.alt'],prob[pt+'.inlet.Fl_O:stat:W'], \
                prob[pt+'.perf.Fn'],prob[pt+'.perf.Fg'],prob[pt+'.inlet.F_ram'],prob[pt+'.perf.OPR'],prob[pt+'.perf.PSFC']))


    fs_names = ['fc.Fl_O','inlet.Fl_O','comp.Fl_O',
                'burner.Fl_O','turb.Fl_O','pt.Fl_O',
                'nozz.Fl_O']
    fs_full_names = [f'{pt}.{fs}' for fs in fs_names]
    pyc.print_flow_station(prob, fs_full_names, file=file)

    comp_names = ['comp']
    comp_full_names = [f'{pt}.{c}' for c in comp_names]
    pyc.print_compressor(prob, comp_full_names, file=file)

    pyc.print_burner(prob, [f'{pt}.burner'])

    turb_names = ['turb','pt']
    turb_full_names = [f'{pt}.{t}' for t in turb_names]
    pyc.print_turbine(prob, turb_full_names, file=file)

    noz_names = ['nozz']
    noz_full_names = [f'{pt}.{n}' for n in noz_names]
    pyc.print_nozzle(prob, noz_full_names, file=file)

    shaft_names = ['HP_shaft','LP_shaft']
    shaft_full_names = [f'{pt}.{s}' for s in shaft_names]
    pyc.print_shaft(prob, shaft_full_names, file=file)


if __name__ == "__main__":

    import time

    prob = om.Problem()

    prob.model = pyc.MPCycle()

    # Create design instance of model
    prob.model.pyc_add_pnt('DESIGN', Turboshaft())
    prob.model.pyc_add_cycle_param('burner.dPqP', .03)
    prob.model.pyc_add_cycle_param('nozz.Cv', 0.99)

    # Connect off-design and required design inputs to model
    od_pts = ['OD1', 'OD2']
    od_MNs = [0.000001, 0.1]
    od_alts =[0.0, 0.0]
    od_pwrs =[3500.0, 3500.0]
    od_nmechs =[5000., 5000.]

    for pt in od_pts:
        prob.model.pyc_add_pnt(pt, Turboshaft(design=False))

    prob.model.pyc_connect_des_od('comp.s_PR', 'comp.s_PR')
    prob.model.pyc_connect_des_od('comp.s_Wc', 'comp.s_Wc')
    prob.model.pyc_connect_des_od('comp.s_eff', 'comp.s_eff')
    prob.model.pyc_connect_des_od('comp.s_Nc', 'comp.s_Nc')

    prob.model.pyc_connect_des_od('turb.s_PR', 'turb.s_PR')
    prob.model.pyc_connect_des_od('turb.s_Wp', 'turb.s_Wp')
    prob.model.pyc_connect_des_od('turb.s_eff', 'turb.s_eff')
    prob.model.pyc_connect_des_od('turb.s_Np', 'turb.s_Np')

    prob.model.pyc_connect_des_od('pt.s_PR', 'pt.s_PR')
    prob.model.pyc_connect_des_od('pt.s_Wp', 'pt.s_Wp')
    prob.model.pyc_connect_des_od('pt.s_eff', 'pt.s_eff')
    prob.model.pyc_connect_des_od('pt.s_Np', 'pt.s_Np')

    prob.model.pyc_connect_des_od('inlet.Fl_O:stat:area', 'inlet.area')
    prob.model.pyc_connect_des_od('comp.Fl_O:stat:area', 'comp.area')
    prob.model.pyc_connect_des_od('burner.Fl_O:stat:area', 'burner.area')
    prob.model.pyc_connect_des_od('turb.Fl_O:stat:area', 'turb.area')
    prob.model.pyc_connect_des_od('pt.Fl_O:stat:area', 'pt.area')

    prob.model.pyc_connect_des_od('nozz.Throat:stat:area', 'balance.rhs:W')


    prob.setup(check=False)



    # Connect design point inputs to model
    prob.set_val('DESIGN.fc.alt', 0.0, units='ft')
    prob.set_val('DESIGN.fc.MN', 0.000001)
    prob.set_val('DESIGN.balance.T4_target', 2370.0, units='degR')
    prob.set_val('DESIGN.balance.pwr_target', 4000.0, units='hp')
    prob.set_val('DESIGN.balance.nozz_PR_target', 1.2)

    prob.set_val('DESIGN.comp.PR', 13.5)
    prob.set_val('DESIGN.comp.eff', 0.83)
    prob.set_val('DESIGN.turb.eff', 0.86)
    prob.set_val('DESIGN.pt.eff', 0.9)
    prob.set_val('DESIGN.HP_Nmech', 8070.0, units='rpm')
    prob.set_val('DESIGN.LP_Nmech', 5000.0, units='rpm')

    prob.set_val('DESIGN.inlet.MN', 0.60)
    prob.set_val('DESIGN.comp.MN', 0.20)
    prob.set_val('DESIGN.burner.MN', 0.20)
    prob.set_val('DESIGN.turb.MN', 0.4)


    # Set initial guesses for balances
    prob['DESIGN.balance.FAR'] = 0.0175506829934
    prob['DESIGN.balance.W'] = 27.265
    prob['DESIGN.balance.turb_PR'] = 3.8768
    prob['DESIGN.balance.pt_PR'] = 2.
    prob['DESIGN.fc.balance.Pt'] = 14.69551131598148
    prob['DESIGN.fc.balance.Tt'] = 518.665288153

    for i,pt in enumerate(od_pts):

        prob.set_val(pt+'.fc.alt', od_alts[i], units='ft')
        prob.set_val(pt+'.fc.MN', od_MNs[i])
        prob.set_val(pt+'.LP_Nmech', od_nmechs[i], units='rpm')
        prob.set_val(pt+'.balance.pwr_target', od_pwrs[i], units='hp')

        prob[pt+'.balance.W'] = 27.265
        prob[pt+'.balance.FAR'] = 0.0175506829934
        prob[pt+'.balance.HP_Nmech'] = 8070.0
        prob[pt+'.fc.balance.Pt'] = 15.703
        prob[pt+'.fc.balance.Tt'] = 558.31
        prob[pt+'.turb.PR'] = 3.8768
        prob[pt+'.pt.PR'] = 2.8148

    st = time.time()

    prob.set_solver_print(level=-1)
    prob.set_solver_print(level=2, depth=1)
    prob.run_model()

    for pt in ['DESIGN']+od_pts:
        viewer(prob, pt)

    print()
    print("time", time.time() - st)