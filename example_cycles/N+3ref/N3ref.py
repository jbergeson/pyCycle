import sys
import numpy as np

import openmdao.api as om

import pycycle.api as pyc

from small_core_eff_balance import SmallCoreEffBalance

from N3_Fan_map import FanMap
from N3_LPC_map import LPCMap
from N3_HPC_map import HPCMap
from N3_HPT_map import HPTMap
from N3_LPT_map import LPTMap


class N3(pyc.Cycle):

    def initialize(self):
        self.options.declare('design', default=True,
                              desc='Switch between on-design and off-design calculation.')
        self.options.declare('cooling', default=False,
                              desc='If True, calculate cooling flow values.')

    def setup(self):

        thermo_spec = pyc.species_data.janaf
        design = self.options['design']
        cooling = self.options['cooling']

        self.pyc_add_element('fc', pyc.FlightConditions(thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('inlet', pyc.Inlet(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('fan', pyc.Compressor(map_data=FanMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX, map_extrap=True,
                                                 bleed_names=[]),
                           promotes_inputs=[('Nmech','Fan_Nmech')])
        self.pyc_add_element('splitter', pyc.Splitter(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('duct2', pyc.Duct(design=design, expMN=2.0, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('lpc', pyc.Compressor(map_data=LPCMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX, map_extrap=True),
                            promotes_inputs=[('Nmech','LP_Nmech')])
        self.pyc_add_element('bld25', pyc.BleedOut(design=design, bleed_names=['sbv']))
        self.pyc_add_element('duct25', pyc.Duct(design=design, expMN=2.0, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('hpc', pyc.Compressor(map_data=HPCMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX, map_extrap=True,
                                        bleed_names=['bld_inlet','bld_exit','cust']),
                           promotes_inputs=[('Nmech','HP_Nmech')])
        self.pyc_add_element('bld3', pyc.BleedOut(design=design, bleed_names=['bld_inlet','bld_exit']))
        self.pyc_add_element('burner', pyc.Combustor(design=design,thermo_data=thermo_spec,
                                        inflow_elements=pyc.AIR_MIX,
                                        air_fuel_elements=pyc.AIR_FUEL_MIX,
                                        fuel_type='Jet-A(g)'))
        self.pyc_add_element('hpt', pyc.Turbine(map_data=HPTMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX, map_extrap=True,
                                              bleed_names=['bld_inlet','bld_exit']),
                           promotes_inputs=[('Nmech','HP_Nmech')])
        self.pyc_add_element('duct45', pyc.Duct(design=design, expMN=2.0, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))
        self.pyc_add_element('lpt', pyc.Turbine(map_data=LPTMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX, map_extrap=True,
                                              bleed_names=['bld_inlet','bld_exit']),
                           promotes_inputs=[('Nmech','LP_Nmech')])
        self.pyc_add_element('duct5', pyc.Duct(design=design, expMN=2.0, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))
        self.pyc_add_element('core_nozz', pyc.Nozzle(nozzType='CV', lossCoef='Cv', thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))

        self.pyc_add_element('byp_bld', pyc.BleedOut(design=design, bleed_names=['bypBld']))
        self.pyc_add_element('duct17', pyc.Duct(design=design, expMN=2.0, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('byp_nozz', pyc.Nozzle(nozzType='CV', lossCoef='Cv', thermo_data=thermo_spec, elements=pyc.AIR_MIX))

        self.pyc_add_element('fan_shaft', pyc.Shaft(num_ports=2), promotes_inputs=[('Nmech','Fan_Nmech')])
        self.pyc_add_element('gearbox', pyc.Gearbox(design=design), promotes_inputs=[('N_in','LP_Nmech'), ('N_out','Fan_Nmech')])
        self.pyc_add_element('lp_shaft', pyc.Shaft(num_ports=3), promotes_inputs=[('Nmech','LP_Nmech')])
        self.pyc_add_element('hp_shaft', pyc.Shaft(num_ports=2), promotes_inputs=[('Nmech','HP_Nmech')])
        self.pyc_add_element('perf', pyc.Performance(num_nozzles=2, num_burners=1))

        self.connect('inlet.Fl_O:tot:P', 'perf.Pt2')
        self.connect('hpc.Fl_O:tot:P', 'perf.Pt3')
        self.connect('burner.Wfuel', 'perf.Wfuel_0')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('core_nozz.Fg', 'perf.Fg_0')
        self.connect('byp_nozz.Fg', 'perf.Fg_1')

        self.connect('fan.trq', 'fan_shaft.trq_0')
        self.connect('gearbox.trq_out', 'fan_shaft.trq_1')
        self.connect('gearbox.trq_in', 'lp_shaft.trq_0')
        self.connect('lpc.trq', 'lp_shaft.trq_1')
        self.connect('lpt.trq', 'lp_shaft.trq_2')
        self.connect('hpc.trq', 'hp_shaft.trq_0')
        self.connect('hpt.trq', 'hp_shaft.trq_1')
        self.connect('fc.Fl_O:stat:P', 'core_nozz.Ps_exhaust')
        self.connect('fc.Fl_O:stat:P', 'byp_nozz.Ps_exhaust')

        self.add_subsystem('ext_ratio', om.ExecComp('ER = core_V_ideal * core_Cv / ( byp_V_ideal *  byp_Cv )',
                        core_V_ideal={'value':1000.0, 'units':'ft/s'},
                        core_Cv={'value':0.98, 'units':None},
                        byp_V_ideal={'value':1000.0, 'units':'ft/s'},
                        byp_Cv={'value':0.98, 'units':None},
                        ER={'value':1.4, 'units':None}))

        self.connect('core_nozz.ideal_flow.V', 'ext_ratio.core_V_ideal')
        self.connect('byp_nozz.ideal_flow.V', 'ext_ratio.byp_V_ideal')


        main_order = ['fc', 'inlet', 'fan', 'splitter', 'duct2', 'lpc', 'bld25', 'duct25', 'hpc', 'bld3', 'burner', 'hpt', 'duct45',
                            'lpt', 'duct5', 'core_nozz', 'byp_bld', 'duct17', 'byp_nozz', 'gearbox', 'fan_shaft', 'lp_shaft', 'hp_shaft',
                            'perf', 'ext_ratio']



        balance = self.add_subsystem('balance', om.BalanceComp())
        if design:

            balance.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017)
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')

            balance.add_balance('lpt_PR', val=10.937, lower=1.001, upper=20, eq_units='hp', rhs_val=0., res_ref=1e4)
            self.connect('balance.lpt_PR', 'lpt.PR')
            self.connect('lp_shaft.pwr_net', 'balance.lhs:lpt_PR')

            balance.add_balance('hpt_PR', val=4.185, lower=1.001, upper=8, eq_units='hp', rhs_val=0., res_ref=1e4)
            self.connect('balance.hpt_PR', 'hpt.PR')
            self.connect('hp_shaft.pwr_net', 'balance.lhs:hpt_PR')

            balance.add_balance('gb_trq', val=23928.0, units='ft*lbf', eq_units='hp', rhs_val=0.0)
            self.connect('balance.gb_trq', 'gearbox.trq_base')
            self.connect('fan_shaft.pwr_net', 'balance.lhs:gb_trq')

            balance.add_balance('hpc_PR', val=14.0, units=None, eq_units=None)
            self.connect('balance.hpc_PR', ['hpc.PR', 'opr_calc.HPCPR'])
            # self.connect('perf.OPR', 'balance.lhs:hpc_PR')
            self.connect('opr_calc.OPR_simple', 'balance.lhs:hpc_PR')

            balance.add_balance('fan_eff', val=0.9689, units=None, eq_units=None)
            self.connect('balance.fan_eff', 'fan.eff')
            self.connect('fan.eff_poly', 'balance.lhs:fan_eff')

            balance.add_balance('lpc_eff', val=0.8895, units=None, eq_units=None)
            self.connect('balance.lpc_eff', 'lpc.eff')
            self.connect('lpc.eff_poly', 'balance.lhs:lpc_eff')

            # balance.add_balance('hpc_eff', val=0.8470, units=None, eq_units=None)
            # self.connect('balance.hpc_eff', 'hpc.eff')
            # self.connect('hpc.eff_poly', 'balance.lhs:hpc_eff')

            balance.add_balance('hpt_eff', val=0.9226, units=None, eq_units=None)
            self.connect('balance.hpt_eff', 'hpt.eff')
            self.connect('hpt.eff_poly', 'balance.lhs:hpt_eff')

            balance.add_balance('lpt_eff', val=0.9401, units=None, eq_units=None)
            self.connect('balance.lpt_eff', 'lpt.eff')
            self.connect('lpt.eff_poly', 'balance.lhs:lpt_eff')

            self.add_subsystem('hpc_CS',
                    om.ExecComp('CS = Win *(pow(Tout/518.67,0.5)/(Pout/14.696))',
                            Win= {'value': 10.0, 'units':'lbm/s'},
                            Tout={'value': 14.696, 'units':'degR'},
                            Pout={'value': 518.67, 'units':'psi'},
                            CS={'value': 10.0, 'units':'lbm/s'}))
            self.connect('duct25.Fl_O:stat:W', 'hpc_CS.Win')
            self.connect('hpc.Fl_O:tot:T', 'hpc_CS.Tout')
            self.connect('hpc.Fl_O:tot:P', 'hpc_CS.Pout')
            self.add_subsystem('hpc_EtaBalance', SmallCoreEffBalance(eng_type = 'large', tech_level = 0))
            self.connect('hpc_CS.CS','hpc_EtaBalance.CS')
            self.connect('hpc.eff_poly', 'hpc_EtaBalance.eta_p')
            self.connect('hpc_EtaBalance.eta_a', 'hpc.eff')

            self.add_subsystem('fan_dia', om.ExecComp('FanDia = 2.0*(area/(pi*(1.0-hub_tip**2.0)))**0.5',
                            area={'value':7000.0, 'units':'inch**2'},
                            hub_tip={'value':0.3125, 'units':None},
                            FanDia={'value':100.0, 'units':'inch'}))
            self.connect('inlet.Fl_O:stat:area', 'fan_dia.area')

            self.add_subsystem('opr_calc', om.ExecComp('OPR_simple = FPR*LPCPR*HPCPR',
                            FPR={'value':1.3, 'units':None},
                            LPCPR={'value':3.0, 'units':None},
                            HPCPR={'value':14.0, 'units':None},
                            OPR_simple={'value':55.0, 'units':None}))


            # order_add = ['hpc_CS', 'fan_dia', 'opr_calc']
            order_add = ['hpc_CS', 'hpc_EtaBalance', 'fan_dia', 'opr_calc']

        else:

            balance.add_balance('FAR', val=0.017, lower=1e-4, eq_units='lbf')
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('perf.Fn', 'balance.lhs:FAR')
            # self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')

            balance.add_balance('W', units='lbm/s', lower=10., upper=2500., eq_units='inch**2')
            self.connect('balance.W', 'fc.W')
            self.connect('core_nozz.Throat:stat:area', 'balance.lhs:W')

            balance.add_balance('BPR', lower=15., upper=40.)
            self.connect('balance.BPR', 'splitter.BPR')
            self.connect('fan.map.RlineMap', 'balance.lhs:BPR')

            balance.add_balance('fan_Nmech', val=2000.0, units='rpm', lower=500., eq_units='hp', rhs_val=0., res_ref=1e2)
            self.connect('balance.fan_Nmech', 'Fan_Nmech')
            self.connect('fan_shaft.pwr_net', 'balance.lhs:fan_Nmech')

            balance.add_balance('lp_Nmech', val=6000.0, units='rpm', lower=500., eq_units='hp', rhs_val=0., res_ref=1e2)
            self.connect('balance.lp_Nmech', 'LP_Nmech')
            self.connect('lp_shaft.pwr_net', 'balance.lhs:lp_Nmech')

            balance.add_balance('hp_Nmech', val=20000.0, units='rpm', lower=500., eq_units='hp', rhs_val=0., res_ref=1e2)
            self.connect('balance.hp_Nmech', 'HP_Nmech')
            self.connect('hp_shaft.pwr_net', 'balance.lhs:hp_Nmech')

            order_add = []

        if cooling:
            self.add_subsystem('hpt_cooling', pyc.TurbineCooling(n_stages=2, thermo_data=pyc.species_data.janaf, T_metal=2460.))
            self.add_subsystem('hpt_chargable', pyc.CombineCooling(n_ins=3))

            self.pyc_connect_flow('bld3.bld_inlet', 'hpt_cooling.Fl_cool', connect_stat=False)
            self.pyc_connect_flow('burner.Fl_O', 'hpt_cooling.Fl_turb_I')
            self.pyc_connect_flow('hpt.Fl_O', 'hpt_cooling.Fl_turb_O')

            self.connect('hpt_cooling.row_1.W_cool', 'hpt_chargable.W_1')
            self.connect('hpt_cooling.row_2.W_cool', 'hpt_chargable.W_2')
            self.connect('hpt_cooling.row_3.W_cool', 'hpt_chargable.W_3')
            self.connect('hpt.power', 'hpt_cooling.turb_pwr')

            balance.add_balance('hpt_nochrg_cool_frac', val=0.063660111, lower=0.02, upper=.15, eq_units='lbm/s')
            self.connect('balance.hpt_nochrg_cool_frac', 'bld3.bld_inlet:frac_W')
            self.connect('bld3.bld_inlet:stat:W', 'balance.lhs:hpt_nochrg_cool_frac')
            self.connect('hpt_cooling.row_0.W_cool', 'balance.rhs:hpt_nochrg_cool_frac')

            balance.add_balance('hpt_chrg_cool_frac', val=0.07037185, lower=0.02, upper=.15, eq_units='lbm/s')
            self.connect('balance.hpt_chrg_cool_frac', 'bld3.bld_exit:frac_W')
            self.connect('bld3.bld_exit:stat:W', 'balance.lhs:hpt_chrg_cool_frac')
            self.connect('hpt_chargable.W_cool', 'balance.rhs:hpt_chrg_cool_frac')



            order_add = ['hpt_cooling', 'hpt_chargable']



        self.set_order(main_order + order_add + ['balance'])

        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I')
        self.pyc_connect_flow('inlet.Fl_O', 'fan.Fl_I')
        self.pyc_connect_flow('fan.Fl_O', 'splitter.Fl_I')
        self.pyc_connect_flow('splitter.Fl_O1', 'duct2.Fl_I')
        self.pyc_connect_flow('duct2.Fl_O', 'lpc.Fl_I')
        self.pyc_connect_flow('lpc.Fl_O', 'bld25.Fl_I')
        self.pyc_connect_flow('bld25.Fl_O', 'duct25.Fl_I')
        self.pyc_connect_flow('duct25.Fl_O', 'hpc.Fl_I')
        self.pyc_connect_flow('hpc.Fl_O', 'bld3.Fl_I')
        self.pyc_connect_flow('bld3.Fl_O', 'burner.Fl_I')
        self.pyc_connect_flow('burner.Fl_O', 'hpt.Fl_I')
        self.pyc_connect_flow('hpt.Fl_O', 'duct45.Fl_I')
        self.pyc_connect_flow('duct45.Fl_O', 'lpt.Fl_I')
        self.pyc_connect_flow('lpt.Fl_O', 'duct5.Fl_I')
        self.pyc_connect_flow('duct5.Fl_O','core_nozz.Fl_I')
        self.pyc_connect_flow('splitter.Fl_O2', 'byp_bld.Fl_I')
        self.pyc_connect_flow('byp_bld.Fl_O', 'duct17.Fl_I')
        self.pyc_connect_flow('duct17.Fl_O', 'byp_nozz.Fl_I')

        self.pyc_connect_flow('hpc.bld_inlet', 'lpt.bld_inlet', connect_stat=False)
        self.pyc_connect_flow('hpc.bld_exit', 'lpt.bld_exit', connect_stat=False)
        self.pyc_connect_flow('bld3.bld_inlet', 'hpt.bld_inlet', connect_stat=False)
        self.pyc_connect_flow('bld3.bld_exit', 'hpt.bld_exit', connect_stat=False)

        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-4
        newton.options['rtol'] = 1e-4
        newton.options['iprint'] = 2
        newton.options['maxiter'] = 10
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 10
        newton.options['reraise_child_analysiserror'] = False
        # newton.linesearch = om.BoundsEnforceLS()
        newton.linesearch = om.ArmijoGoldsteinLS()
        # newton.linesearch.options['maxiter'] = 2
        newton.linesearch.options['bound_enforcement'] = 'scalar'
        newton.linesearch.options['iprint'] = -1
        # if design:
        #     newton.linesearch.options['print_bound_enforce'] = True

        # newton.options['debug_print'] = True

        self.linear_solver = om.DirectSolver(assemble_jac=True)

def viewer(prob, pt, file=sys.stdout):
    """
    print a report of all the relevant cycle properties
    """

    # if pt == 'DESIGN':
    #     MN = prob['DESIGN.fc.Fl_O:stat:MN']
    #     LPT_PR = prob['DESIGN.balance.lpt_PR']
    #     HPT_PR = prob['DESIGN.balance.hpt_PR']
    #     FAR = prob['DESIGN.balance.FAR']
    # else:
    #     MN = prob[pt+'.fc.Fl_O:stat:MN']
    #     LPT_PR = prob[pt+'.lpt.PR']
    #     HPT_PR = prob[pt+'.hpt.PR']
    #     FAR = prob[pt+'.balance.FAR']

    print(file=file, flush=True)
    print(file=file, flush=True)
    print(file=file, flush=True)
    print("----------------------------------------------------------------------------", file=file, flush=True)
    print("                              POINT:", pt, file=file, flush=True)
    print("----------------------------------------------------------------------------", file=file, flush=True)
    print("                       PERFORMANCE CHARACTERISTICS", file=file, flush=True)
    print("    Mach      Alt       W      Fn      Fg    Fram     OPR     TSFC      BPR ", file=file, flush=True)
    print(" %7.5f  %7.1f %7.3f %7.1f %7.1f %7.1f %7.3f  %7.5f  %7.3f" %(prob[pt+'.fc.Fl_O:stat:MN'], prob[pt+'.fc.alt'],prob[pt+'.inlet.Fl_O:stat:W'],prob[pt+'.perf.Fn'],prob[pt+'.perf.Fg'],prob[pt+'.inlet.F_ram'],prob[pt+'.perf.OPR'],prob[pt+'.perf.TSFC'], prob[pt+'.splitter.BPR']), file=file, flush=True)

    fs_names = ['fc.Fl_O','inlet.Fl_O','fan.Fl_O','splitter.Fl_O1','duct2.Fl_O',
                'lpc.Fl_O','bld25.Fl_O','duct25.Fl_O','hpc.Fl_O','bld3.Fl_O',
                'burner.Fl_O','hpt.Fl_O','duct45.Fl_O','lpt.Fl_O','duct5.Fl_O',
                'core_nozz.Fl_O','splitter.Fl_O2','byp_bld.Fl_O','duct17.Fl_O',
                'byp_nozz.Fl_O']
    fs_full_names = [f'{pt}.{fs}' for fs in fs_names]
    pyc.print_flow_station(prob, fs_full_names, file=file)

    comp_names = ['fan', 'lpc', 'hpc']
    comp_full_names = [f'{pt}.{c}' for c in comp_names]
    pyc.print_compressor(prob, comp_full_names, file=file)

    pyc.print_burner(prob, [f'{pt}.burner'])

    turb_names = ['hpt', 'lpt']
    turb_full_names = [f'{pt}.{t}' for t in turb_names]
    pyc.print_turbine(prob, turb_full_names, file=file)

    noz_names = ['core_nozz', 'byp_nozz']
    noz_full_names = [f'{pt}.{n}' for n in noz_names]
    pyc.print_nozzle(prob, noz_full_names, file=file)

    shaft_names = ['hp_shaft', 'lp_shaft', 'fan_shaft']
    shaft_full_names = [f'{pt}.{s}' for s in shaft_names]
    pyc.print_shaft(prob, shaft_full_names, file=file)

    bleed_names = ['hpc', 'bld3','bld3','bld25']
    bleed_full_names = [f'{pt}.{b}' for b in bleed_names]
    pyc.print_bleed(prob, bleed_full_names, file=file)




class MPN3(pyc.MPCycle):

    def setup(self):

        des_vars = self.add_subsystem('des_vars', om.IndepVarComp(), promotes=["*"])

        des_vars.add_output('inlet:ram_recovery', 0.9980),
        des_vars.add_output('fan:PRdes', 1.300),
        des_vars.add_output('fan:effDes', 0.96888),
        des_vars.add_output('fan:effPoly', 0.97),
        des_vars.add_output('splitter:BPR', 23.94514401), 
        des_vars.add_output('duct2:dPqP', 0.0100),
        des_vars.add_output('lpc:PRdes', 3.000),
        des_vars.add_output('lpc:effDes', 0.889513),
        des_vars.add_output('lpc:effPoly', 0.905),
        des_vars.add_output('duct25:dPqP', 0.0150),
        des_vars.add_output('hpc:PRdes', 14.103),
        des_vars.add_output('OPR', 53.6332)
        des_vars.add_output('hpc:effDes', 0.847001),
        des_vars.add_output('hpc:effPoly', 0.89),
        des_vars.add_output('hpt:effDes', 0.922649),
        des_vars.add_output('hpt:effPoly', 0.91),
        des_vars.add_output('duct45:dPqP', 0.0050),
        des_vars.add_output('lpt:effDes', 0.940104),
        des_vars.add_output('lpt:effPoly', 0.92),
        des_vars.add_output('duct5:dPqP', 0.0100),
        des_vars.add_output('duct17:dPqP', 0.0150),
        des_vars.add_output('fan_shaft:Nmech', 2184.5, units='rpm'),
        des_vars.add_output('lp_shaft:Nmech', 6772.0, units='rpm'),
        des_vars.add_output('hp_shaft:Nmech', 20871.0, units='rpm'),

        des_vars.add_output('bld3:bld_inlet:frac_W', 0.063660111), #different than NPSS due to Wref
        des_vars.add_output('bld3:bld_exit:frac_W', 0.07037185), #different than NPSS due to Wref

        des_vars.add_output('inlet:MN_out', 0.625),
        des_vars.add_output('fan:MN_out', 0.45)
        des_vars.add_output('splitter:MN_out1', 0.45)
        des_vars.add_output('splitter:MN_out2', 0.45)
        des_vars.add_output('duct2:MN_out', 0.45),
        des_vars.add_output('lpc:MN_out', 0.45),
        des_vars.add_output('bld25:MN_out', 0.45),
        des_vars.add_output('duct25:MN_out', 0.45),
        des_vars.add_output('hpc:MN_out', 0.30),
        des_vars.add_output('bld3:MN_out', 0.30)
        des_vars.add_output('burner:MN_out', 0.10),
        des_vars.add_output('hpt:MN_out', 0.30),
        des_vars.add_output('duct45:MN_out', 0.45),
        des_vars.add_output('lpt:MN_out', 0.35),
        des_vars.add_output('duct5:MN_out', 0.25),
        des_vars.add_output('bypBld:MN_out', 0.45),
        des_vars.add_output('duct17:MN_out', 0.45),

        # POINT 1: Top-of-climb (TOC)
        des_vars.add_output('TOC:alt', 35000., units='ft'),
        des_vars.add_output('TOC:MN', 0.8),
        des_vars.add_output('TOC:T4max', 3150.0, units='degR'),
        # des_vars.add_output('FAR', 0.02833)
        des_vars.add_output('TOC:Fn_des', 6073.4, units='lbf'),
        des_vars.add_output('TOC:ram_recovery', 0.9980),
        des_vars.add_output('TR', 0.926470588)
        # des_vars.add_output('TOC:W', 820.44097898, units='lbm/s')

        # POINT 2: Rolling Takeoff (RTO)
        des_vars.add_output('RTO:MN', 0.25),
        des_vars.add_output('RTO:alt', 0.0, units='ft'),
        des_vars.add_output('RTO:Fn_target', 22800.0, units='lbf'), #8950.0
        des_vars.add_output('RTO:dTs', 27.0, units='degR')
        des_vars.add_output('RTO:Ath', 5532.3, units='inch**2')
        des_vars.add_output('RTO:RlineMap', 1.75)
        des_vars.add_output('RTO:T4max', 3400.0, units='degR')
        des_vars.add_output('RTO:W', 1916.13, units='lbm/s')
        des_vars.add_output('RTO:ram_recovery', 0.9970),
        des_vars.add_output('RTO:duct2:dPqP', 0.0073)
        des_vars.add_output('RTO:duct25:dPqP', 0.0138)
        des_vars.add_output('RTO:duct45:dPqP', 0.0051)
        des_vars.add_output('RTO:duct5:dPqP', 0.0058)
        des_vars.add_output('RTO:duct17:dPqP', 0.0132)

        # POINT 3: Sea-Level Static (SLS)
        des_vars.add_output('SLS:MN', 0.000001),
        des_vars.add_output('SLS:alt', 0.0, units='ft'),
        des_vars.add_output('SLS:Fn_target', 28620.84, units='lbf'), 
        des_vars.add_output('SLS:dTs', 27.0, units='degR')
        des_vars.add_output('SLS:Ath', 6315.6, units='inch**2')
        des_vars.add_output('SLS:RlineMap', 1.75)
        des_vars.add_output('SLS:ram_recovery', 0.9950),
        des_vars.add_output('SLS:duct2:dPqP', 0.0058)
        des_vars.add_output('SLS:duct25:dPqP', 0.0126)
        des_vars.add_output('SLS:duct45:dPqP', 0.0052)
        des_vars.add_output('SLS:duct5:dPqP', 0.0043)
        des_vars.add_output('SLS:duct17:dPqP', 0.0123)

        # POINT 4: Cruise (CRZ)
        des_vars.add_output('CRZ:MN', 0.8),
        des_vars.add_output('CRZ:alt', 35000.0, units='ft'),
        des_vars.add_output('CRZ:Fn_target', 5510.72833567, units='lbf'), 
        des_vars.add_output('CRZ:dTs', 0.0, units='degR')
        des_vars.add_output('CRZ:Ath', 4747.1, units='inch**2')
        des_vars.add_output('CRZ:RlineMap', 1.9397)
        des_vars.add_output('CRZ:ram_recovery', 0.9980),
        des_vars.add_output('CRZ:duct2:dPqP', 0.0092)
        des_vars.add_output('CRZ:duct25:dPqP', 0.0138)
        des_vars.add_output('CRZ:duct45:dPqP', 0.0050)
        des_vars.add_output('CRZ:duct5:dPqP', 0.0097)
        des_vars.add_output('CRZ:duct17:dPqP', 0.0148)
        des_vars.add_output('CRZ:VjetRatio', 1.41038)

        # TOC POINT (DESIGN)
        self.pyc_add_pnt('TOC', N3())
        self.connect('TOC:alt', 'TOC.fc.alt')
        self.connect('TOC:MN', 'TOC.fc.MN')

        self.connect('TOC:ram_recovery', 'TOC.inlet.ram_recovery')
        self.connect('fan:PRdes', 'TOC.fan.PR')
        self.connect('fan:effPoly', 'TOC.balance.rhs:fan_eff')
        self.connect('duct2:dPqP', 'TOC.duct2.dPqP')
        self.connect('lpc:PRdes', 'TOC.lpc.PR')
        self.connect('lpc:effPoly', 'TOC.balance.rhs:lpc_eff')
        self.connect('duct25:dPqP', 'TOC.duct25.dPqP')
        self.connect('OPR', 'TOC.balance.rhs:hpc_PR')
        self.connect('hpt:effPoly', 'TOC.balance.rhs:hpt_eff')
        self.connect('duct45:dPqP', 'TOC.duct45.dPqP')
        self.connect('lpt:effPoly', 'TOC.balance.rhs:lpt_eff')
        self.connect('duct5:dPqP', 'TOC.duct5.dPqP')
        self.connect('duct17:dPqP', 'TOC.duct17.dPqP')
        self.connect('fan_shaft:Nmech', 'TOC.Fan_Nmech')
        self.connect('lp_shaft:Nmech', 'TOC.LP_Nmech')
        self.connect('hp_shaft:Nmech', 'TOC.HP_Nmech')

        self.connect('inlet:MN_out', 'TOC.inlet.MN')
        self.connect('fan:MN_out', 'TOC.fan.MN')
        self.connect('splitter:MN_out1', 'TOC.splitter.MN1')
        self.connect('splitter:MN_out2', 'TOC.splitter.MN2')
        self.connect('duct2:MN_out', 'TOC.duct2.MN')
        self.connect('lpc:MN_out', 'TOC.lpc.MN')
        self.connect('bld25:MN_out', 'TOC.bld25.MN')
        self.connect('duct25:MN_out', 'TOC.duct25.MN')
        self.connect('hpc:MN_out', 'TOC.hpc.MN')
        self.connect('bld3:MN_out', 'TOC.bld3.MN')
        self.connect('burner:MN_out', 'TOC.burner.MN')
        self.connect('hpt:MN_out', 'TOC.hpt.MN')
        self.connect('duct45:MN_out', 'TOC.duct45.MN')
        self.connect('lpt:MN_out', 'TOC.lpt.MN')
        self.connect('duct5:MN_out', 'TOC.duct5.MN')
        self.connect('bypBld:MN_out', 'TOC.byp_bld.MN')
        self.connect('duct17:MN_out', 'TOC.duct17.MN')

        # OTHER POINTS (OFF-DESIGN)
        pts = ['RTO','SLS','CRZ']

        self.connect('RTO:Fn_target', 'RTO.balance.rhs:FAR')

        self.pyc_add_pnt('RTO', N3(design=False, cooling=True))
        self.pyc_add_pnt('SLS', N3(design=False))
        self.pyc_add_pnt('CRZ', N3(design=False))


        for pt in pts:

            self.connect(pt+':alt', pt+'.fc.alt')
            self.connect(pt+':MN', pt+'.fc.MN')
            self.connect(pt+':dTs', pt+'.fc.dTs')
            self.connect(pt+':RlineMap',pt+'.balance.rhs:BPR')
            self.connect(pt+':ram_recovery', pt+'.inlet.ram_recovery')

        self.pyc_add_cycle_param('burner.dPqP', 0.0400),
        self.pyc_add_cycle_param('core_nozz.Cv', 0.9999),
        self.pyc_add_cycle_param('byp_nozz.Cv', 0.9975),
        self.pyc_add_cycle_param('lp_shaft.fracLoss', 0.01)
        self.pyc_add_cycle_param('hp_shaft.HPX', 350.0, units='hp'),
        self.pyc_add_cycle_param('bld25.sbv:frac_W', 0.0),
        self.pyc_add_cycle_param('hpc.bld_inlet:frac_W', 0.0),
        self.pyc_add_cycle_param('hpc.bld_inlet:frac_P', 0.1465),
        self.pyc_add_cycle_param('hpc.bld_inlet:frac_work', 0.5),
        self.pyc_add_cycle_param('hpc.bld_exit:frac_W', 0.02),
        self.pyc_add_cycle_param('hpc.bld_exit:frac_P', 0.1465),
        self.pyc_add_cycle_param('hpc.bld_exit:frac_work', 0.5),
        self.pyc_add_cycle_param('hpc.cust:frac_W', 0.0),
        self.pyc_add_cycle_param('hpc.cust:frac_P', 0.1465),
        self.pyc_add_cycle_param('hpc.cust:frac_work', 0.35),
        self.pyc_add_cycle_param('hpt.bld_inlet:frac_P', 1.0),
        self.pyc_add_cycle_param('hpt.bld_exit:frac_P', 0.0),
        self.pyc_add_cycle_param('lpt.bld_inlet:frac_P', 1.0),
        self.pyc_add_cycle_param('lpt.bld_exit:frac_P', 0.0),
        self.pyc_add_cycle_param('byp_bld.bypBld:frac_W', 0.0),

        self.pyc_connect_des_od('fan.s_PR', 'fan.s_PR')
        self.pyc_connect_des_od('fan.s_Wc', 'fan.s_Wc')
        self.pyc_connect_des_od('fan.s_eff', 'fan.s_eff')
        self.pyc_connect_des_od('fan.s_Nc', 'fan.s_Nc')
        self.pyc_connect_des_od('lpc.s_PR', 'lpc.s_PR')
        self.pyc_connect_des_od('lpc.s_Wc', 'lpc.s_Wc')
        self.pyc_connect_des_od('lpc.s_eff', 'lpc.s_eff')
        self.pyc_connect_des_od('lpc.s_Nc', 'lpc.s_Nc')
        self.pyc_connect_des_od('hpc.s_PR', 'hpc.s_PR')
        self.pyc_connect_des_od('hpc.s_Wc', 'hpc.s_Wc')
        self.pyc_connect_des_od('hpc.s_eff', 'hpc.s_eff')
        self.pyc_connect_des_od('hpc.s_Nc', 'hpc.s_Nc')
        self.pyc_connect_des_od('hpt.s_PR', 'hpt.s_PR')
        self.pyc_connect_des_od('hpt.s_Wp', 'hpt.s_Wp')
        self.pyc_connect_des_od('hpt.s_eff', 'hpt.s_eff')
        self.pyc_connect_des_od('hpt.s_Np', 'hpt.s_Np')
        self.pyc_connect_des_od('lpt.s_PR', 'lpt.s_PR')
        self.pyc_connect_des_od('lpt.s_Wp', 'lpt.s_Wp')
        self.pyc_connect_des_od('lpt.s_eff', 'lpt.s_eff')
        self.pyc_connect_des_od('lpt.s_Np', 'lpt.s_Np')

        self.pyc_connect_des_od('gearbox.gear_ratio', 'gearbox.gear_ratio')
        self.pyc_connect_des_od('core_nozz.Throat:stat:area','balance.rhs:W')

        self.pyc_connect_des_od('inlet.Fl_O:stat:area', 'inlet.area')
        self.pyc_connect_des_od('fan.Fl_O:stat:area', 'fan.area')
        self.pyc_connect_des_od('splitter.Fl_O1:stat:area', 'splitter.area1')
        self.pyc_connect_des_od('splitter.Fl_O2:stat:area', 'splitter.area2')
        self.pyc_connect_des_od('duct2.Fl_O:stat:area', 'duct2.area')
        self.pyc_connect_des_od('lpc.Fl_O:stat:area', 'lpc.area')
        self.pyc_connect_des_od('bld25.Fl_O:stat:area', 'bld25.area')
        self.pyc_connect_des_od('duct25.Fl_O:stat:area', 'duct25.area')
        self.pyc_connect_des_od('hpc.Fl_O:stat:area', 'hpc.area')
        self.pyc_connect_des_od('bld3.Fl_O:stat:area', 'bld3.area')
        self.pyc_connect_des_od('burner.Fl_O:stat:area', 'burner.area')
        self.pyc_connect_des_od('hpt.Fl_O:stat:area', 'hpt.area')
        self.pyc_connect_des_od('duct45.Fl_O:stat:area', 'duct45.area')
        self.pyc_connect_des_od('lpt.Fl_O:stat:area', 'lpt.area')
        self.pyc_connect_des_od('duct5.Fl_O:stat:area', 'duct5.area')
        self.pyc_connect_des_od('byp_bld.Fl_O:stat:area', 'byp_bld.area')
        self.pyc_connect_des_od('duct17.Fl_O:stat:area', 'duct17.area')

        self.pyc_connect_des_od('duct2.s_dPqP', 'duct2.s_dPqP')
        self.pyc_connect_des_od('duct25.s_dPqP', 'duct25.s_dPqP')
        self.pyc_connect_des_od('duct45.s_dPqP', 'duct45.s_dPqP')
        self.pyc_connect_des_od('duct5.s_dPqP', 'duct5.s_dPqP')
        self.pyc_connect_des_od('duct17.s_dPqP', 'duct17.s_dPqP')


        self.connect('RTO.balance.hpt_chrg_cool_frac', 'TOC.bld3.bld_exit:frac_W')
        self.connect('RTO.balance.hpt_nochrg_cool_frac', 'TOC.bld3.bld_inlet:frac_W')

        self.connect('RTO.balance.hpt_chrg_cool_frac', 'SLS.bld3.bld_exit:frac_W')
        self.connect('RTO.balance.hpt_nochrg_cool_frac', 'SLS.bld3.bld_inlet:frac_W')

        self.connect('RTO.balance.hpt_chrg_cool_frac', 'CRZ.bld3.bld_exit:frac_W')
        self.connect('RTO.balance.hpt_nochrg_cool_frac', 'CRZ.bld3.bld_inlet:frac_W')

        # self.connect('splitter:BPR', 'TOC.splitter.BPR')
        # self.connect('TOC:W', 'TOC.fc.W')
        # self.connect('CRZ:Fn_target', 'CRZ.balance.rhs:FAR')
        # self.connect('SLS:Fn_target', 'SLS.balance.rhs:FAR')

        self.add_subsystem('T4_ratio',
                             om.ExecComp('TOC_T4 = RTO_T4*TR',
                                         RTO_T4={'value': 3400.0, 'units':'degR'},
                                         TOC_T4={'value': 3150.0, 'units':'degR'},
                                         TR={'value': 0.926470588, 'units': None}))
        self.connect('RTO:T4max','T4_ratio.RTO_T4')
        self.connect('T4_ratio.TOC_T4', 'TOC.balance.rhs:FAR')
        self.connect('TR', 'T4_ratio.TR')
        # self.set_order(['des_vars', 'T4_ratio', 'TOC', 'RTO', 'SLS', 'CRZ'])

        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-6
        newton.options['rtol'] = 1e-6
        newton.options['iprint'] = 2
        newton.options['maxiter'] = 20
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 10
        newton.options['err_on_non_converge'] = True
        newton.options['reraise_child_analysiserror'] = False
        newton.linesearch =  om.BoundsEnforceLS()
        newton.linesearch.options['bound_enforcement'] = 'scalar'
        newton.linesearch.options['iprint'] = -1

        self.linear_solver = om.DirectSolver(assemble_jac=True)


if __name__ == "__main__":

    import time

    prob = om.Problem()

    prob.model = MPN3()

    prob.model.connect('splitter:BPR', 'TOC.splitter.BPR')
    # prob.model.connect('TOC:W', 'TOC.fc.W')
    prob.model.connect('CRZ:Fn_target', 'CRZ.balance.rhs:FAR')
    prob.model.connect('SLS:Fn_target', 'SLS.balance.rhs:FAR')

    # setup the optimization
    prob.driver = om.ScipyOptimizeDriver()
    prob.driver.options['optimizer'] = 'SLSQP'
    prob.driver.options['debug_print'] = ['desvars', 'nl_cons', 'objs']
    prob.driver.opt_settings={'Major step limit': 0.05}

    prob.model.add_design_var('fan:PRdes', lower=1.20, upper=1.4)
    prob.model.add_design_var('lpc:PRdes', lower=2.0, upper=4.0)
    prob.model.add_design_var('OPR', lower=40.0, upper=70.0, ref0=40.0, ref=70.0)
    prob.model.add_design_var('RTO:T4max', lower=3000.0, upper=3600.0, ref0=3000.0, ref=3600.0)
    prob.model.add_design_var('CRZ:VjetRatio', lower=1.35, upper=1.45, ref0=1.35, ref=1.45)
    prob.model.add_design_var('TR', lower=0.5, upper=0.95, ref0=0.5, ref=0.95)

    prob.model.add_objective('TOC.perf.TSFC')

    # to add the constraint to the model
    prob.model.add_constraint('TOC.fan_dia.FanDia', upper=100.0, ref=100.0)

    prob.setup(check=False)
    prob.set_val('TOC.fc.W', 820.44097898, units='lbm/s')
    prob['RTO.hpt_cooling.x_factor'] = 0.9

    # initial guesses
    prob['TOC.balance.FAR'] = 0.02650
    prob['TOC.balance.lpt_PR'] = 10.937
    prob['TOC.balance.hpt_PR'] = 4.185
    prob['TOC.fc.balance.Pt'] = 5.272
    prob['TOC.fc.balance.Tt'] = 444.41

    pts = ['RTO','SLS','CRZ']

    for pt in pts:

        if pt == 'RTO':
            prob[pt+'.balance.FAR'] = 0.02832
            prob[pt+'.balance.W'] = 1916.13
            prob[pt+'.balance.BPR'] = 25.5620
            prob[pt+'.balance.fan_Nmech'] = 2132.6
            prob[pt+'.balance.lp_Nmech'] = 6611.2
            prob[pt+'.balance.hp_Nmech'] = 22288.2
            prob[pt+'.fc.balance.Pt'] = 15.349
            prob[pt+'.fc.balance.Tt'] = 552.49
            prob[pt+'.hpt.PR'] = 4.210
            prob[pt+'.lpt.PR'] = 8.161
            prob[pt+'.fan.map.RlineMap'] = 1.7500
            prob[pt+'.lpc.map.RlineMap'] = 2.0052
            prob[pt+'.hpc.map.RlineMap'] = 2.0589
            prob[pt+'.gearbox.trq_base'] = 52509.1

        if pt == 'SLS':
            prob[pt+'.balance.FAR'] = 0.02541
            prob[pt+'.balance.W'] = 2000. #1734.44
            prob[pt+'.balance.BPR'] = 27.3467
            prob[pt+'.balance.fan_Nmech'] = 1953.1
            prob[pt+'.balance.lp_Nmech'] = 6054.5
            prob[pt+'.balance.hp_Nmech'] = 21594.0
            prob[pt+'.fc.balance.Pt'] = 14.696
            prob[pt+'.fc.balance.Tt'] = 545.67
            prob[pt+'.hpt.PR'] = 4.245
            prob[pt+'.lpt.PR'] = 7.001
            prob[pt+'.fan.map.RlineMap'] = 1.7500
            prob[pt+'.lpc.map.RlineMap'] = 1.8632
            prob[pt+'.hpc.map.RlineMap'] = 2.0281
            prob[pt+'.gearbox.trq_base'] = 41779.4

        if pt == 'CRZ':
            prob[pt+'.balance.FAR'] = 0.02510
            prob[pt+'.balance.W'] = 802.79
            prob[pt+'.balance.BPR'] = 24.3233
            prob[pt+'.balance.fan_Nmech'] = 2118.7
            prob[pt+'.balance.lp_Nmech'] = 6567.9
            prob[pt+'.balance.hp_Nmech'] = 20574.1
            prob[pt+'.fc.balance.Pt'] = 5.272
            prob[pt+'.fc.balance.Tt'] = 444.41
            prob[pt+'.hpt.PR'] = 4.197
            prob[pt+'.lpt.PR'] = 10.803
            prob[pt+'.fan.map.RlineMap'] = 1.9397
            prob[pt+'.lpc.map.RlineMap'] = 2.1075
            prob[pt+'.hpc.map.RlineMap'] = 1.9746
            prob[pt+'.gearbox.trq_base'] = 22369.7



    st = time.time()

    prob.set_solver_print(level=-1)
    prob.set_solver_print(level=2, depth=1)
    prob.run_model()

    for pt in ['TOC']+pts:
        viewer(prob, pt)

    print("time", time.time() - st)


    print('TOC')
    print(prob['TOC.inlet.Fl_O:stat:W'] - 820.44097898)#
    print(prob['TOC.inlet.Fl_O:tot:P'] - 5.26210728)#
    print(prob['TOC.hpc.Fl_O:tot:P'] - 275.21039426)#
    print(prob['TOC.burner.Wfuel'] - 0.74668441)#
    print(prob['TOC.inlet.F_ram'] - 19854.88340967)#
    print(prob['TOC.core_nozz.Fg'] - 1547.13847348)#
    print(prob['TOC.byp_nozz.Fg'] - 24430.7872167)#
    print(prob['TOC.perf.TSFC'] - 0.43900789)#
    print(prob['TOC.perf.OPR'] - 52.30041498)#
    print(prob['TOC.balance.FAR'] - 0.02669913)#
    print(prob['TOC.hpc.Fl_O:tot:T'] - 1517.98001185)#
    print('............................')
    print('RTO')
    print(prob['RTO.inlet.Fl_O:stat:W'] - 1915.22687254)#
    print(prob['RTO.inlet.Fl_O:tot:P'] - 15.3028198)#
    print(prob['RTO.hpc.Fl_O:tot:P'] - 623.4047562)#
    print(prob['RTO.burner.Wfuel'] - 1.73500397)#
    print(prob['RTO.inlet.F_ram'] - 17040.51023484)#
    print(prob['RTO.core_nozz.Fg'] - 2208.78618847)#
    print(prob['RTO.byp_nozz.Fg'] - 37631.72404627)#
    print(prob['RTO.perf.TSFC'] - 0.273948)#
    print(prob['RTO.perf.OPR'] - 40.73790087)#
    print(prob['RTO.balance.FAR'] - 0.02853677)#
    print(prob['RTO.balance.fan_Nmech'] - 2133.2082055)#
    print(prob['RTO.balance.lp_Nmech'] - 6612.99426306)#
    print(prob['RTO.balance.hp_Nmech'] - 22294.4214065)#
    print(prob['RTO.hpc.Fl_O:tot:T'] - 1707.8424979)#
    print('............................')
    print('SLS')
    print(prob['SLS.inlet.Fl_O:stat:W'] - 1733.66974646)#
    print(prob['SLS.inlet.Fl_O:tot:P'] - 14.62242048)#
    print(prob['SLS.hpc.Fl_O:tot:P'] - 509.33522171)#
    print(prob['SLS.burner.Wfuel'] - 1.3201035)#
    print(prob['SLS.inlet.F_ram'] - 0.06170051)#
    print(prob['SLS.core_nozz.Fg'] - 1526.45701492)#
    print(prob['SLS.byp_nozz.Fg'] - 27094.44468547)#
    print(prob['SLS.perf.TSFC'] - 0.16604588)#
    print(prob['SLS.perf.OPR'] - 34.8324836)#
    print(prob['SLS.balance.FAR'] - 0.02559136)#
    print(prob['SLS.balance.fan_Nmech'] - 1953.67749381)#
    print(prob['SLS.balance.lp_Nmech'] - 6056.44494761)#
    print(prob['SLS.balance.hp_Nmech'] - 21599.4239832)#
    print(prob['SLS.hpc.Fl_O:tot:T'] - 1615.20710655)#
    print('............................')
    print('CRZ')
    print(prob['CRZ.inlet.Fl_O:stat:W'] - 802.28669491)#
    print(prob['CRZ.inlet.Fl_O:tot:P'] - 5.26210728)#
    print(prob['CRZ.hpc.Fl_O:tot:P'] - 258.04394098)#
    print(prob['CRZ.burner.Wfuel'] - 0.67533764)#
    print(prob['CRZ.inlet.F_ram'] - 19415.54505032)#
    print(prob['CRZ.core_nozz.Fg'] - 1375.4427785)#
    print(prob['CRZ.byp_nozz.Fg'] - 23550.83060746)#
    print(prob['CRZ.perf.TSFC'] - 0.44117862)#
    print(prob['CRZ.perf.OPR'] - 49.03813765)#
    print(prob['CRZ.balance.FAR'] - 0.02528878)#
    print(prob['CRZ.balance.fan_Nmech'] - 2118.62554023)#
    print(prob['CRZ.balance.lp_Nmech'] - 6567.78766693)#
    print(prob['CRZ.balance.hp_Nmech'] - 20574.43651756)#
    print(prob['CRZ.hpc.Fl_O:tot:T'] - 1481.9756247)#

