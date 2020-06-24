import sys
import numpy as np

import openmdao.api as om

import pycycle.api as pyc

class Turboshaft(pyc.Cycle):

    def initialize(self):
        self.options.declare('design', default=True,
                              desc='Switch between on-design and off-design calculation.')
        self.options.declare('maxiter', default=10,
                              desc='Maximum number of Newton solver iterations.')

    def setup(self):

        thermo_spec = pyc.species_data.janaf
        design = self.options['design']
        maxiter = self.options['maxiter']

        self.pyc_add_element('fc', pyc.FlightConditions(thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('inlet', pyc.Inlet(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('duct1', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('lpc', pyc.Compressor(map_data=pyc.LPCMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX),
                           promotes_inputs=[('Nmech','IP_Nmech')])
        self.pyc_add_element('icduct', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('hpc_axi', pyc.Compressor(map_data=pyc.HPCMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX),
                           promotes_inputs=[('Nmech','HP_Nmech')])
        self.pyc_add_element('bld25', pyc.BleedOut(design=design, bleed_names=['cool1','cool2']))
        self.pyc_add_element('hpc_centri', pyc.Compressor(map_data=pyc.HPCMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX),
                           promotes_inputs=[('Nmech','HP_Nmech')])
        self.pyc_add_element('bld3', pyc.BleedOut(design=design, bleed_names=['cool3','cool4']))
        self.pyc_add_element('duct6', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('burner', pyc.Combustor(design=design,thermo_data=thermo_spec,
                                                   inflow_elements=pyc.AIR_MIX,
                                                   air_fuel_elements=pyc.AIR_FUEL_MIX,
                                                   fuel_type='Jet-A(g)'))
        self.pyc_add_element('hpt', pyc.Turbine(map_data=pyc.HPTMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX,
                                              bleed_names=['cool3','cool4']),
                           promotes_inputs=[('Nmech','HP_Nmech')])
        self.pyc_add_element('duct43', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))
        self.pyc_add_element('lpt', pyc.Turbine(map_data=pyc.LPTMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX,
                                              bleed_names=['cool1','cool2']),
                           promotes_inputs=[('Nmech','IP_Nmech')])
        self.pyc_add_element('itduct', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))
        self.pyc_add_element('pt', pyc.Turbine(map_data=pyc.LPTMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX),
                           promotes_inputs=[('Nmech','LP_Nmech')])
        self.pyc_add_element('duct12', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))
        self.pyc_add_element('nozzle', pyc.Nozzle(nozzType='CV', lossCoef='Cv', thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))

        self.pyc_add_element('lp_shaft', pyc.Shaft(num_ports=1),promotes_inputs=[('Nmech','LP_Nmech')])
        self.pyc_add_element('ip_shaft', pyc.Shaft(num_ports=2),promotes_inputs=[('Nmech','IP_Nmech')])
        self.pyc_add_element('hp_shaft', pyc.Shaft(num_ports=3),promotes_inputs=[('Nmech','HP_Nmech')])
        self.pyc_add_element('perf', pyc.Performance(num_nozzles=1, num_burners=1))

        self.connect('duct1.Fl_O:tot:P', 'perf.Pt2')
        self.connect('hpc_centri.Fl_O:tot:P', 'perf.Pt3')
        self.connect('burner.Wfuel', 'perf.Wfuel_0')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('nozzle.Fg', 'perf.Fg_0')
        self.connect('lp_shaft.pwr_in', 'perf.power')

        self.connect('pt.trq', 'lp_shaft.trq_0')
        self.connect('lpc.trq', 'ip_shaft.trq_0')
        self.connect('lpt.trq', 'ip_shaft.trq_1')
        self.connect('hpc_axi.trq', 'hp_shaft.trq_0')
        self.connect('hpc_centri.trq', 'hp_shaft.trq_1')
        self.connect('hpt.trq', 'hp_shaft.trq_2')
        self.connect('fc.Fl_O:stat:P', 'nozzle.Ps_exhaust')

        balance = self.add_subsystem('balance', om.BalanceComp())
        if design:

            balance.add_balance('W', units='lbm/s', eq_units=None)
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('nozzle.PR', 'balance.lhs:W')

            balance.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017)
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')

            balance.add_balance('lpt_PR', val=1.5, lower=1.001, upper=8, eq_units='hp', rhs_val=0.)
            self.connect('balance.lpt_PR', 'lpt.PR')
            self.connect('ip_shaft.pwr_net', 'balance.lhs:lpt_PR')

            balance.add_balance('hpt_PR', val=1.5, lower=1.001, upper=8, eq_units='hp', rhs_val=0.)
            self.connect('balance.hpt_PR', 'hpt.PR')
            self.connect('hp_shaft.pwr_net', 'balance.lhs:hpt_PR')

            balance.add_balance('pt_PR', val=1.5, lower=1.001, upper=8, eq_units='hp', rhs_val=0.)
            self.connect('balance.pt_PR', 'pt.PR')
            self.connect('lp_shaft.pwr_net', 'balance.lhs:pt_PR')


        else:
            balance.add_balance('FAR', eq_units='hp', lower=1e-4, val=.017)
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('lp_shaft.pwr_net', 'balance.lhs:FAR')

            balance.add_balance('W', units='lbm/s', eq_units='inch**2')
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('nozzle.Throat:stat:area', 'balance.lhs:W')

            balance.add_balance('IP_Nmech', val=12000.0, units='rpm', lower=1.001, eq_units='hp', rhs_val=0.)
            self.connect('balance.IP_Nmech', 'IP_Nmech')
            self.connect('ip_shaft.pwr_net', 'balance.lhs:IP_Nmech')

            balance.add_balance('HP_Nmech', val=14800.0, units='rpm', lower=1.001, eq_units='hp', rhs_val=0.)
            self.connect('balance.HP_Nmech', 'HP_Nmech')
            self.connect('hp_shaft.pwr_net', 'balance.lhs:HP_Nmech')

        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I', connect_w=False)
        self.pyc_connect_flow('inlet.Fl_O', 'duct1.Fl_I')
        self.pyc_connect_flow('duct1.Fl_O', 'lpc.Fl_I')
        self.pyc_connect_flow('lpc.Fl_O', 'icduct.Fl_I')
        self.pyc_connect_flow('icduct.Fl_O', 'hpc_axi.Fl_I')
        self.pyc_connect_flow('hpc_axi.Fl_O', 'bld25.Fl_I')
        self.pyc_connect_flow('bld25.Fl_O', 'hpc_centri.Fl_I')
        self.pyc_connect_flow('hpc_centri.Fl_O', 'bld3.Fl_I')
        self.pyc_connect_flow('bld3.Fl_O', 'duct6.Fl_I')
        self.pyc_connect_flow('duct6.Fl_O', 'burner.Fl_I')
        self.pyc_connect_flow('burner.Fl_O', 'hpt.Fl_I')
        self.pyc_connect_flow('hpt.Fl_O', 'duct43.Fl_I')
        self.pyc_connect_flow('duct43.Fl_O', 'lpt.Fl_I')
        self.pyc_connect_flow('lpt.Fl_O', 'itduct.Fl_I')
        self.pyc_connect_flow('itduct.Fl_O', 'pt.Fl_I')
        self.pyc_connect_flow('pt.Fl_O', 'duct12.Fl_I')
        self.pyc_connect_flow('duct12.Fl_O', 'nozzle.Fl_I')

        self.pyc_connect_flow('bld25.cool1', 'lpt.cool1', connect_stat=False)
        self.pyc_connect_flow('bld25.cool2', 'lpt.cool2', connect_stat=False)
        self.pyc_connect_flow('bld3.cool3', 'hpt.cool3', connect_stat=False)
        self.pyc_connect_flow('bld3.cool4', 'hpt.cool4', connect_stat=False)

        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-6
        newton.options['rtol'] = 1e-6
        newton.options['iprint'] = 2
        newton.options['maxiter'] = maxiter
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 100
        newton.options['reraise_child_analysiserror'] = False
        newton.linesearch = om.BoundsEnforceLS()
        newton.linesearch.options['bound_enforcement'] = 'scalar'
        newton.linesearch.options['iprint'] = -1

        self.linear_solver = om.DirectSolver()

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


    fs_names = ['fc.Fl_O','inlet.Fl_O','duct1.Fl_O','lpc.Fl_O',
                'icduct.Fl_O','hpc_axi.Fl_O','bld25.Fl_O',
                'hpc_centri.Fl_O','bld3.Fl_O','duct6.Fl_O',
                'burner.Fl_O','hpt.Fl_O','duct43.Fl_O','lpt.Fl_O',
                'itduct.Fl_O','pt.Fl_O','duct12.Fl_O','nozzle.Fl_O']
    fs_full_names = [f'{pt}.{fs}' for fs in fs_names]
    pyc.print_flow_station(prob, fs_full_names, file=file)

    comp_names = ['lpc','hpc_axi','hpc_centri']
    comp_full_names = [f'{pt}.{c}' for c in comp_names]
    pyc.print_compressor(prob, comp_full_names, file=file)

    pyc.print_burner(prob, [f'{pt}.burner'])

    turb_names = ['hpt','lpt','pt']
    turb_full_names = [f'{pt}.{t}' for t in turb_names]
    pyc.print_turbine(prob, turb_full_names, file=file)

    noz_names = ['nozzle']
    noz_full_names = [f'{pt}.{n}' for n in noz_names]
    pyc.print_nozzle(prob, noz_full_names, file=file)

    shaft_names = ['hp_shaft','ip_shaft','lp_shaft']
    shaft_full_names = [f'{pt}.{s}' for s in shaft_names]
    pyc.print_shaft(prob, shaft_full_names, file=file)

    bleed_names = ['bld25', 'bld3']
    bleed_full_names = [f'{pt}.{b}' for b in bleed_names]
    pyc.print_bleed(prob, bleed_full_names, file=file)


if __name__ == "__main__":

    import time
    from openmdao.api import Problem
    from openmdao.utils.units import convert_units as cu

    prob = om.Problem()

    prob.model = pyc.MPCycle()

    # DESIGN CASE
    prob.model.pyc_add_pnt('DESIGN', Turboshaft())
    prob.model.pyc_add_cycle_param('inlet.ram_recovery', 1.0)
    prob.model.pyc_add_cycle_param('duct1.dPqP', 0.0)
    prob.model.pyc_add_cycle_param('icduct.dPqP', 0.002)
    prob.model.pyc_add_cycle_param('bld25.cool1:frac_W', 0.024)
    prob.model.pyc_add_cycle_param('bld25.cool2:frac_W', 0.0146)
    prob.model.pyc_add_cycle_param('duct6.dPqP', 0.00)
    prob.model.pyc_add_cycle_param('burner.dPqP', 0.050)
    prob.model.pyc_add_cycle_param('bld3.cool3:frac_W', 0.1705)
    prob.model.pyc_add_cycle_param('bld3.cool4:frac_W', 0.1209)
    prob.model.pyc_add_cycle_param('duct43.dPqP', 0.0051)
    prob.model.pyc_add_cycle_param('itduct.dPqP', 0.00)
    prob.model.pyc_add_cycle_param('duct12.dPqP', 0.00)
    prob.model.pyc_add_cycle_param('nozzle.Cv', 0.99)
    prob.model.pyc_add_cycle_param('hpt.cool3:frac_P', 1.0)
    prob.model.pyc_add_cycle_param('hpt.cool4:frac_P', 0.0)
    prob.model.pyc_add_cycle_param('lpt.cool1:frac_P', 1.0)
    prob.model.pyc_add_cycle_param('lpt.cool2:frac_P', 0.0)

    # OFF DESIGN CASES
    pts = ['OD1'] 

    for pt in pts:
        ODpt = prob.model.pyc_add_pnt(pt, Turboshaft(design=False, maxiter=10))

    prob.model.pyc_connect_des_od('lpc.s_PR', 'lpc.s_PR')
    prob.model.pyc_connect_des_od('lpc.s_Wc', 'lpc.s_Wc')
    prob.model.pyc_connect_des_od('lpc.s_eff', 'lpc.s_eff')
    prob.model.pyc_connect_des_od('lpc.s_Nc', 'lpc.s_Nc')
    prob.model.pyc_connect_des_od('hpc_axi.s_PR', 'hpc_axi.s_PR')
    prob.model.pyc_connect_des_od('hpc_axi.s_Wc', 'hpc_axi.s_Wc')
    prob.model.pyc_connect_des_od('hpc_axi.s_eff', 'hpc_axi.s_eff')
    prob.model.pyc_connect_des_od('hpc_axi.s_Nc', 'hpc_axi.s_Nc')
    prob.model.pyc_connect_des_od('hpc_centri.s_PR', 'hpc_centri.s_PR')
    prob.model.pyc_connect_des_od('hpc_centri.s_Wc', 'hpc_centri.s_Wc')
    prob.model.pyc_connect_des_od('hpc_centri.s_eff', 'hpc_centri.s_eff')
    prob.model.pyc_connect_des_od('hpc_centri.s_Nc', 'hpc_centri.s_Nc')
    prob.model.pyc_connect_des_od('hpt.s_PR', 'hpt.s_PR')
    prob.model.pyc_connect_des_od('hpt.s_Wp', 'hpt.s_Wp')
    prob.model.pyc_connect_des_od('hpt.s_eff', 'hpt.s_eff')
    prob.model.pyc_connect_des_od('hpt.s_Np', 'hpt.s_Np')
    prob.model.pyc_connect_des_od('lpt.s_PR', 'lpt.s_PR')
    prob.model.pyc_connect_des_od('lpt.s_Wp', 'lpt.s_Wp')
    prob.model.pyc_connect_des_od('lpt.s_eff', 'lpt.s_eff')
    prob.model.pyc_connect_des_od('lpt.s_Np', 'lpt.s_Np')
    prob.model.pyc_connect_des_od('pt.s_PR', 'pt.s_PR')
    prob.model.pyc_connect_des_od('pt.s_Wp', 'pt.s_Wp')
    prob.model.pyc_connect_des_od('pt.s_eff', 'pt.s_eff')
    prob.model.pyc_connect_des_od('pt.s_Np', 'pt.s_Np')

    prob.model.pyc_connect_des_od('inlet.Fl_O:stat:area', 'inlet.area')
    prob.model.pyc_connect_des_od('duct1.Fl_O:stat:area', 'duct1.area')
    prob.model.pyc_connect_des_od('lpc.Fl_O:stat:area', 'lpc.area')
    prob.model.pyc_connect_des_od('icduct.Fl_O:stat:area', 'icduct.area')
    prob.model.pyc_connect_des_od('hpc_axi.Fl_O:stat:area', 'hpc_axi.area')
    prob.model.pyc_connect_des_od('bld25.Fl_O:stat:area', 'bld25.area')
    prob.model.pyc_connect_des_od('hpc_centri.Fl_O:stat:area', 'hpc_centri.area')
    prob.model.pyc_connect_des_od('bld3.Fl_O:stat:area', 'bld3.area')
    prob.model.pyc_connect_des_od('burner.Fl_O:stat:area', 'burner.area')
    prob.model.pyc_connect_des_od('hpt.Fl_O:stat:area', 'hpt.area')
    prob.model.pyc_connect_des_od('duct43.Fl_O:stat:area', 'duct43.area')
    prob.model.pyc_connect_des_od('lpt.Fl_O:stat:area', 'lpt.area')
    prob.model.pyc_connect_des_od('itduct.Fl_O:stat:area', 'itduct.area')
    prob.model.pyc_connect_des_od('pt.Fl_O:stat:area', 'pt.area')
    prob.model.pyc_connect_des_od('duct12.Fl_O:stat:area', 'duct12.area')
    prob.model.pyc_connect_des_od('nozzle.Throat:stat:area','balance.rhs:W')

    prob.setup()

    prob.set_val('DESIGN.fc.alt', 28000., units='ft'),
    prob.set_val('DESIGN.fc.MN', 0.5),
    prob.set_val('DESIGN.balance.rhs:FAR', 2740.0, units='degR'),
    prob.set_val('DESIGN.balance.rhs:W', 1.1)

    prob.set_val('DESIGN.inlet.MN', 0.4),
    prob.set_val('DESIGN.duct1.MN', 0.4),
    prob.set_val('DESIGN.lpc.PR', 5.000),
    prob.set_val('DESIGN.lpc.eff', 0.8900),

    prob.set_val('DESIGN.lpc.MN', 0.3),
    prob.set_val('DESIGN.icduct.MN', 0.3),
    prob.set_val('DESIGN.hpc_axi.PR', 3.0),
    prob.set_val('DESIGN.hpc_axi.eff', 0.8900),

    prob.set_val('DESIGN.hpc_axi.MN', 0.25),
    prob.set_val('DESIGN.bld25.MN', 0.3000),
    prob.set_val('DESIGN.hpc_centri.PR', 2.7),

    prob.set_val('DESIGN.hpc_centri.eff', 0.8800),
    prob.set_val('DESIGN.hpc_centri.MN', 0.20),
    prob.set_val('DESIGN.bld3.MN', 0.2000),

    prob.set_val('DESIGN.duct6.MN', 0.2000),
    prob.set_val('DESIGN.burner.MN', 0.15),
    prob.set_val('DESIGN.hpt.eff', 0.89),

    prob.set_val('DESIGN.hpt.MN', 0.30),
    prob.set_val('DESIGN.duct43.MN', 0.30),

    prob.set_val('DESIGN.lpt.eff', 0.9),
    prob.set_val('DESIGN.lpt.MN', 0.4),

    prob.set_val('DESIGN.itduct.MN', 0.4),
    prob.set_val('DESIGN.pt.eff', 0.85),
    prob.set_val('DESIGN.pt.MN', 0.4),
    prob.set_val('DESIGN.duct12.MN', 0.4),

    prob.set_val('DESIGN.LP_Nmech', 12750., units='rpm'),
    prob.set_val('DESIGN.lp_shaft.HPX', 1800.0, units='hp'),
    prob.set_val('DESIGN.IP_Nmech', 12000., units='rpm'),
    prob.set_val('DESIGN.HP_Nmech', 14800., units='rpm'),

    alts = [28000,]
    MNs = [.5,]

    for i, pt in enumerate(pts):

        prob.set_val(pt+'.balance.rhs:FAR', 1600.0, units='hp')
        prob.set_val(pt+'.LP_Nmech', 12750.0, units='rpm')
        prob.set_val(pt+'.fc.alt', alts[i], units='ft')
        prob.set_val(pt+'.fc.MN', MNs[i])

        # initial guesses
        prob[pt+'.balance.FAR'] = 0.02135
        prob[pt+'.balance.W'] = 10.775
        prob[pt+'.balance.HP_Nmech'] = 14800.000
        prob[pt+'.balance.IP_Nmech'] = 12000.000
        prob[pt+'.hpt.PR'] = 4.233
        prob[pt+'.lpt.PR'] = 1.979
        prob[pt+'.pt.PR'] = 4.919
        prob[pt+'.fc.balance.Pt'] = 5.666
        prob[pt+'.fc.balance.Tt'] = 440.0
        prob[pt+'.nozzle.PR'] = 1.1

    # initial guesses
    prob['DESIGN.balance.FAR'] = 0.02261
    prob['DESIGN.balance.W'] = 10.76
    prob['DESIGN.balance.hpt_PR'] = 4.233
    prob['DESIGN.balance.lpt_PR'] = 1.979
    prob['DESIGN.balance.pt_PR'] = 4.919
    prob['DESIGN.fc.balance.Pt'] = 5.666
    prob['DESIGN.fc.balance.Tt'] = 440.0

    st = time.time()


    prob.set_solver_print(level=-1)
    prob.set_solver_print(level=2, depth=1)
    prob.run_model()

    for pt in ['DESIGN']+pts:
        viewer(prob, pt)

    print()
    print("time", time.time() - st)
