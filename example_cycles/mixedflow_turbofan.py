import sys
import numpy as np

import openmdao.api as om

import pycycle.api as pyc


class MixedFlowTurbofan(pyc.Cycle):

    def initialize(self):
        self.options.declare('design', default=True,
            desc='Switch between on-design and off-design calculation.')

    def setup(self):
        thermo_spec = pyc.species_data.janaf
        design = self.options['design']

        self.pyc_add_element('fc', pyc.FlightConditions(thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        # Inlet Components
        self.pyc_add_element('inlet', pyc.Inlet(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('inlet_duct', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        # Fan Components - Split here for CFD integration Add a CFDStart Compomponent
        self.pyc_add_element('fan', pyc.Compressor(map_data=pyc.AXI5, design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX,
                                             map_extrap=True),promotes_inputs=[('Nmech','LP_Nmech')])
        self.pyc_add_element('splitter', pyc.Splitter(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        # Core Stream components
        self.pyc_add_element('splitter_core_duct', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('lpc', pyc.Compressor(map_data=pyc.LPCMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX,map_extrap=True),
                                             promotes_inputs=[('Nmech','LP_Nmech')])
        self.pyc_add_element('lpc_duct', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        self.pyc_add_element('hpc', pyc.Compressor(map_data=pyc.HPCMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX,
                                        bleed_names=['cool1'],map_extrap=True),promotes_inputs=[('Nmech','HP_Nmech')])
        self.pyc_add_element('bld3', pyc.BleedOut(design=design, bleed_names=['cool3']))
        self.pyc_add_element('burner', pyc.Combustor(design=design,thermo_data=thermo_spec,
                                                inflow_elements=pyc.AIR_MIX,
                                                air_fuel_elements=pyc.AIR_FUEL_MIX,
                                                fuel_type='Jet-A(g)'))
        self.pyc_add_element('hpt', pyc.Turbine(map_data=pyc.HPTMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX,
                                          bleed_names=['cool3'],map_extrap=True),promotes_inputs=[('Nmech','HP_Nmech')])
        self.pyc_add_element('hpt_duct', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))
        self.pyc_add_element('lpt', pyc.Turbine(map_data=pyc.LPTMap, design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX,
                                        bleed_names=['cool1'],map_extrap=True), promotes_inputs=[('Nmech','LP_Nmech')])
        self.pyc_add_element('lpt_duct', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))
        # Bypass Components
        self.pyc_add_element('bypass_duct', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_MIX))
        # Mixer component
        self.pyc_add_element('mixer', pyc.Mixer(design=design, designed_stream=1, Fl_I1_elements=pyc.AIR_FUEL_MIX, Fl_I2_elements=pyc.AIR_MIX))
        self.pyc_add_element('mixer_duct', pyc.Duct(design=design, thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))
        # Afterburner Components
        self.pyc_add_element('afterburner', pyc.Combustor(design=design,thermo_data=thermo_spec,
                                                inflow_elements=pyc.AIR_FUEL_MIX,
                                                air_fuel_elements=pyc.AIR_FUEL_MIX,
                                                fuel_type='Jet-A(g)'))
        # End CFD HERE
        # Nozzle
        self.pyc_add_element('mixed_nozz', pyc.Nozzle(nozzType='CD', lossCoef='Cfg', thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX))

        # Mechanical components
        self.pyc_add_element('lp_shaft', pyc.Shaft(num_ports=3),promotes_inputs=[('Nmech','LP_Nmech')])
        self.pyc_add_element('hp_shaft', pyc.Shaft(num_ports=2),promotes_inputs=[('Nmech','HP_Nmech')])

        # Aggregating component
        self.pyc_add_element('perf', pyc.Performance(num_nozzles=1, num_burners=2))

        # Connnect flow path
        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I')
        self.pyc_connect_flow('inlet.Fl_O', 'inlet_duct.Fl_I')
        self.pyc_connect_flow('inlet_duct.Fl_O', 'fan.Fl_I')
        self.pyc_connect_flow('fan.Fl_O', 'splitter.Fl_I')
        # Core connections
        self.pyc_connect_flow('splitter.Fl_O1', 'splitter_core_duct.Fl_I')
        self.pyc_connect_flow('splitter_core_duct.Fl_O', 'lpc.Fl_I')
        self.pyc_connect_flow('lpc.Fl_O', 'lpc_duct.Fl_I')
        self.pyc_connect_flow('lpc_duct.Fl_O', 'hpc.Fl_I')
        self.pyc_connect_flow('hpc.Fl_O', 'bld3.Fl_I')
        self.pyc_connect_flow('bld3.Fl_O', 'burner.Fl_I')
        self.pyc_connect_flow('burner.Fl_O', 'hpt.Fl_I')
        self.pyc_connect_flow('hpt.Fl_O', 'hpt_duct.Fl_I')
        self.pyc_connect_flow('hpt_duct.Fl_O', 'lpt.Fl_I')
        self.pyc_connect_flow('lpt.Fl_O', 'lpt_duct.Fl_I')
        self.pyc_connect_flow('lpt_duct.Fl_O','mixer.Fl_I1')
        # Bypass Connections
        self.pyc_connect_flow('splitter.Fl_O2', 'bypass_duct.Fl_I')
        self.pyc_connect_flow('bypass_duct.Fl_O', 'mixer.Fl_I2')

        #Mixer Connections
        self.pyc_connect_flow('mixer.Fl_O', 'mixer_duct.Fl_I')
        # After Burner
        self.pyc_connect_flow('mixer_duct.Fl_O','afterburner.Fl_I')

        # Nozzle
        self.pyc_connect_flow('afterburner.Fl_O','mixed_nozz.Fl_I')

        # Connect cooling flows
        self.pyc_connect_flow('hpc.cool1', 'lpt.cool1', connect_stat=False)
        self.pyc_connect_flow('bld3.cool3', 'hpt.cool3', connect_stat=False)

        # Make additional model connections
        self.connect('inlet.Fl_O:tot:P', 'perf.Pt2')
        self.connect('hpc.Fl_O:tot:P', 'perf.Pt3')
        self.connect('burner.Wfuel', 'perf.Wfuel_0')
        self.connect('afterburner.Wfuel', 'perf.Wfuel_1')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('mixed_nozz.Fg', 'perf.Fg_0')

        self.connect('fan.trq', 'lp_shaft.trq_0')
        self.connect('lpc.trq', 'lp_shaft.trq_1')
        self.connect('lpt.trq', 'lp_shaft.trq_2')
        self.connect('hpc.trq', 'hp_shaft.trq_0')
        self.connect('hpt.trq', 'hp_shaft.trq_1')
        self.connect('fc.Fl_O:stat:P', 'mixed_nozz.Ps_exhaust')

        # Add balence components to close the implicit components
        balance = self.add_subsystem('balance', om.BalanceComp())
        if design:
            balance.add_balance('W', lower=1e-3, upper=200., units='lbm/s', eq_units='lbf')
            self.connect('balance.W', 'fc.W')
            self.connect('perf.Fn', 'balance.lhs:W')
            # self.add_subsystem('wDV',IndepVarComp('wDes',100,units='lbm/s'))
            # self.connect('wDV.wDes','fc.W')

            balance.add_balance('BPR', eq_units=None, lower=0.25, val=5.0)
            self.connect('balance.BPR', 'splitter.BPR')
            self.connect('mixer.ER', 'balance.lhs:BPR')

            balance.add_balance('FAR_core', eq_units='degR', lower=1e-4, val=.017)
            self.connect('balance.FAR_core', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR_core')

            balance.add_balance('FAR_ab', eq_units='degR', lower=1e-4, val=.017)
            self.connect('balance.FAR_ab', 'afterburner.Fl_I:FAR')
            self.connect('afterburner.Fl_O:tot:T', 'balance.lhs:FAR_ab')

            balance.add_balance('lpt_PR', val=1.5, lower=1.001, upper=8, eq_units='hp', use_mult=True, mult_val=-1)
            self.connect('balance.lpt_PR', 'lpt.PR')
            self.connect('lp_shaft.pwr_in', 'balance.lhs:lpt_PR')
            self.connect('lp_shaft.pwr_out', 'balance.rhs:lpt_PR')

            balance.add_balance('hpt_PR', val=1.5, lower=1.001, upper=8, eq_units='hp', use_mult=True, mult_val=-1)
            self.connect('balance.hpt_PR', 'hpt.PR')
            self.connect('hp_shaft.pwr_in', 'balance.lhs:hpt_PR')
            self.connect('hp_shaft.pwr_out', 'balance.rhs:hpt_PR')
        else:

            balance.add_balance('W', lower=1e-3, upper=200., units='lbm/s', eq_units='inch**2')
            self.connect('balance.W', 'fc.W')
            self.connect('mixed_nozz.Throat:stat:area', 'balance.lhs:W')

            balance.add_balance('BPR', lower=0.25, upper=5.0, eq_units='psi')
            self.connect('balance.BPR', 'splitter.BPR')
            self.connect('mixer.Fl_I1_calc:stat:P', 'balance.lhs:BPR')
            self.connect('bypass_duct.Fl_O:stat:P', 'balance.rhs:BPR')

            balance.add_balance('FAR_core', eq_units='degR', lower=1e-4, upper=.06, val=.017)
            self.connect('balance.FAR_core', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR_core')

            balance.add_balance('FAR_ab', eq_units='degR', lower=1e-4, upper=.06, val=.017)
            self.connect('balance.FAR_ab', 'afterburner.Fl_I:FAR')
            self.connect('afterburner.Fl_O:tot:T', 'balance.lhs:FAR_ab')

            balance.add_balance('LP_Nmech', val=1., units='rpm', lower=500., eq_units='hp', use_mult=True, mult_val=-1)
            self.connect('balance.LP_Nmech', 'LP_Nmech')
            self.connect('lp_shaft.pwr_in', 'balance.lhs:LP_Nmech')
            self.connect('lp_shaft.pwr_out', 'balance.rhs:LP_Nmech')

            balance.add_balance('HP_Nmech', val=1., units='rpm', lower=500., eq_units='hp', use_mult=True, mult_val=-1)
            self.connect('balance.HP_Nmech', 'HP_Nmech')
            self.connect('hp_shaft.pwr_in', 'balance.lhs:HP_Nmech')
            self.connect('hp_shaft.pwr_out', 'balance.rhs:HP_Nmech')

        # Off design
        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-6
        newton.options['rtol'] = 1e-10
        newton.options['iprint'] = 2
        newton.options['maxiter'] = 10
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 100
        newton.options['reraise_child_analysiserror'] = False
        newton.linesearch = om.BoundsEnforceLS()
        newton.linesearch.options['bound_enforcement'] = 'scalar'
        newton.linesearch.options['iprint'] = -1


        self.linear_solver = om.DirectSolver(assemble_jac=True)


def print_perf(prob,ptName):
    ''' print out the performancs values'''
    print('BPR',prob[ptName+'.balance.BPR'])
    print('W',prob[ptName+'.balance.W'])
    #print('W',prob[ptName+'.wDV.wDes'])
    print('Fnet uninst.',prob[ptName+'.perf.Fn'])

def page_viewer(point):
    flow_stations = ['fc.Fl_O', 'inlet.Fl_O', 'inlet_duct.Fl_O', 'fan.Fl_O', 'bypass_duct.Fl_O',
                     'splitter.Fl_O2', 'splitter.Fl_O1', 'splitter_core_duct.Fl_O',
                     'lpc.Fl_O', 'lpc_duct.Fl_O', 'hpc.Fl_O', 'bld3.Fl_O', 'burner.Fl_O',
                     'hpt.Fl_O', 'hpt_duct.Fl_O', 'lpt_duct.Fl_O',
                     'mixer.Fl_O', 'mixer_duct.Fl_O', 'afterburner.Fl_O', 'mixed_nozz.Fl_O']

    compressors = ['fan', 'hpc', 'lpc']
    burners = ['burner', 'afterburner']
    turbines = ['hpt', 'lpt']
    shafts = ['hp_shaft', 'lp_shaft']

    print('*'*80)
    print('* ' + ' '*10 + point)
    print('*'*80)
    print_perf(prob, point)

    pyc.print_flow_station(prob,[point+ "."+fl for fl in flow_stations])
    pyc.print_compressor(prob,[point+ "." + c for c in compressors])
    # print_splitter(prob,[point+ ".splitter" ])
    pyc.print_burner(prob,[point+ "." + b for b in burners])
    pyc.print_turbine(prob,[point+ "." + turb for turb in turbines])
    pyc.print_mixer(prob, [point+'.mixer'])
    pyc.print_nozzle(prob, [point + '.mixed_nozz'])
    pyc.print_shaft(prob, [point+ "." + s for s in shafts])
    pyc.print_bleed(prob, [point+'.hpc', point+'.bld3'])

if __name__ == "__main__":
    import time
    from openmdao.api import Problem

    prob = Problem()

    prob.model = pyc.MPCycle()

    #####################
    # DESIGN CASE
    #####################

    prob.model.pyc_add_pnt('DESIGN', MixedFlowTurbofan(design=True))
    prob.model.pyc_add_cycle_param('balance.rhs:FAR_ab', 3400 ,units='degR')
    prob.model.pyc_add_cycle_param('hp_shaft.HPX', 0.0, units='hp')
    prob.model.pyc_add_cycle_param('inlet.ram_recovery', 0.9990)
    prob.model.pyc_add_cycle_param('inlet_duct.dPqP', 0.0107)
    prob.model.pyc_add_cycle_param('splitter_core_duct.dPqP', 0.0048)
    prob.model.pyc_add_cycle_param('lpc_duct.dPqP', 0.0101)
    prob.model.pyc_add_cycle_param('burner.dPqP', 0.0540)
    prob.model.pyc_add_cycle_param('hpt_duct.dPqP', 0.0051)
    prob.model.pyc_add_cycle_param('lpt_duct.dPqP', 0.0107)
    prob.model.pyc_add_cycle_param('bypass_duct.dPqP', 0.0107)
    prob.model.pyc_add_cycle_param('mixer_duct.dPqP', 0.0107)
    prob.model.pyc_add_cycle_param('afterburner.dPqP', 0.0540)
    prob.model.pyc_add_cycle_param('mixed_nozz.Cfg', 0.9933)
    prob.model.pyc_add_cycle_param('hpc.cool1:frac_W', 0.050708)
    prob.model.pyc_add_cycle_param('hpc.cool1:frac_P', 0.5)
    prob.model.pyc_add_cycle_param('hpc.cool1:frac_work', 0.5)
    prob.model.pyc_add_cycle_param('bld3.cool3:frac_W', 0.067214)
    prob.model.pyc_add_cycle_param('hpt.cool3:frac_P', 1.0)
    prob.model.pyc_add_cycle_param('lpt.cool1:frac_P', 1.0)

    ####################
    # OFF DESIGN CASES
    ####################
    od_pts = ['OD0',]

    od_alts = [35000,]
    od_MNs = [0.8, ]

    for i,pt in enumerate(od_pts):
        prob.model.pyc_add_pnt(pt, MixedFlowTurbofan(design=False))

    # map scalars
    prob.model.pyc_connect_des_od('fan.s_PR', 'fan.s_PR')
    prob.model.pyc_connect_des_od('fan.s_Wc', 'fan.s_Wc')
    prob.model.pyc_connect_des_od('fan.s_eff', 'fan.s_eff')
    prob.model.pyc_connect_des_od('fan.s_Nc', 'fan.s_Nc')
    prob.model.pyc_connect_des_od('lpc.s_PR', 'lpc.s_PR')
    prob.model.pyc_connect_des_od('lpc.s_Wc', 'lpc.s_Wc')
    prob.model.pyc_connect_des_od('lpc.s_eff', 'lpc.s_eff')
    prob.model.pyc_connect_des_od('lpc.s_Nc', 'lpc.s_Nc')
    prob.model.pyc_connect_des_od('hpc.s_PR', 'hpc.s_PR')
    prob.model.pyc_connect_des_od('hpc.s_Wc', 'hpc.s_Wc')
    prob.model.pyc_connect_des_od('hpc.s_eff', 'hpc.s_eff')
    prob.model.pyc_connect_des_od('hpc.s_Nc', 'hpc.s_Nc')
    prob.model.pyc_connect_des_od('hpt.s_PR', 'hpt.s_PR')
    prob.model.pyc_connect_des_od('hpt.s_Wp', 'hpt.s_Wp')
    prob.model.pyc_connect_des_od('hpt.s_eff', 'hpt.s_eff')
    prob.model.pyc_connect_des_od('hpt.s_Np', 'hpt.s_Np')
    prob.model.pyc_connect_des_od('lpt.s_PR', 'lpt.s_PR')
    prob.model.pyc_connect_des_od('lpt.s_Wp', 'lpt.s_Wp')
    prob.model.pyc_connect_des_od('lpt.s_eff', 'lpt.s_eff')
    prob.model.pyc_connect_des_od('lpt.s_Np', 'lpt.s_Np')

    # flow areas
    prob.model.pyc_connect_des_od('mixed_nozz.Throat:stat:area', 'balance.rhs:W')

    prob.model.pyc_connect_des_od('inlet.Fl_O:stat:area', 'inlet.area')
    prob.model.pyc_connect_des_od('fan.Fl_O:stat:area', 'fan.area')
    prob.model.pyc_connect_des_od('splitter.Fl_O1:stat:area', 'splitter.area1')
    prob.model.pyc_connect_des_od('splitter.Fl_O2:stat:area', 'splitter.area2')
    prob.model.pyc_connect_des_od('splitter_core_duct.Fl_O:stat:area', 'splitter_core_duct.area')
    prob.model.pyc_connect_des_od('lpc.Fl_O:stat:area', 'lpc.area')
    prob.model.pyc_connect_des_od('lpc_duct.Fl_O:stat:area', 'lpc_duct.area')
    prob.model.pyc_connect_des_od('hpc.Fl_O:stat:area', 'hpc.area')
    prob.model.pyc_connect_des_od('bld3.Fl_O:stat:area', 'bld3.area')
    prob.model.pyc_connect_des_od('burner.Fl_O:stat:area', 'burner.area')
    prob.model.pyc_connect_des_od('hpt.Fl_O:stat:area', 'hpt.area')
    prob.model.pyc_connect_des_od('hpt_duct.Fl_O:stat:area', 'hpt_duct.area')
    prob.model.pyc_connect_des_od('lpt.Fl_O:stat:area', 'lpt.area')
    prob.model.pyc_connect_des_od('lpt_duct.Fl_O:stat:area', 'lpt_duct.area')
    prob.model.pyc_connect_des_od('bypass_duct.Fl_O:stat:area', 'bypass_duct.area')
    prob.model.pyc_connect_des_od('mixer.Fl_O:stat:area', 'mixer.area')
    prob.model.pyc_connect_des_od('mixer.Fl_I1_calc:stat:area', 'mixer.Fl_I1_stat_calc.area')
    prob.model.pyc_connect_des_od('mixer_duct.Fl_O:stat:area', 'mixer_duct.area')
    prob.model.pyc_connect_des_od('afterburner.Fl_O:stat:area', 'afterburner.area')


    # setup problem
    prob.setup(check=False)#True)

    prob.set_val('DESIGN.fc.alt', 35000., units='ft') #DV
    prob.set_val('DESIGN.fc.MN', 0.8) #DV
    prob.set_val('DESIGN.balance.rhs:W', 5500.0, units='lbf')
    prob.set_val('DESIGN.balance.rhs:FAR_core', 3200, units='degR')

    prob.set_val('DESIGN.balance.rhs:BPR', 1.05 ,units=None) # defined as 1 over 2

    prob.set_val('DESIGN.inlet.MN', 0.751)

    prob.set_val('DESIGN.inlet_duct.MN', 0.4463)

    prob.set_val('DESIGN.fan.PR', 3.3) #ADV
    prob.set_val('DESIGN.fan.eff', 0.8948)
    prob.set_val('DESIGN.fan.MN', 0.4578)

    prob.set_val('DESIGN.splitter.MN1', 0.3104)
    prob.set_val('DESIGN.splitter.MN2', 0.4518)
    prob.set_val('DESIGN.splitter_core_duct.MN', 0.3121)

    prob.set_val('DESIGN.lpc.PR', 1.935)
    prob.set_val('DESIGN.lpc.eff', 0.9243)
    prob.set_val('DESIGN.lpc.MN', 0.3059)

    prob.set_val('DESIGN.lpc_duct.MN', 0.3563)

    prob.set_val('DESIGN.hpc.PR', 4.9)
    prob.set_val('DESIGN.hpc.eff', 0.8707)
    prob.set_val('DESIGN.hpc.MN', 0.2442)

    prob.set_val('DESIGN.bld3.MN', 0.3000)

    prob.set_val('DESIGN.burner.MN', 0.1025)

    prob.set_val('DESIGN.hpt.eff', 0.8888)
    prob.set_val('DESIGN.hpt.MN', 0.3650)

    prob.set_val('DESIGN.hpt_duct.MN', 0.3063)

    prob.set_val('DESIGN.lpt.eff', 0.8996)
    prob.set_val('DESIGN.lpt.MN', 0.4127)

    prob.set_val('DESIGN.lpt_duct.MN', 0.4463)

    prob.set_val('DESIGN.bypass_duct.MN', 0.4463)

    prob.set_val('DESIGN.mixer_duct.MN', 0.4463)

    prob.set_val('DESIGN.afterburner.MN', 0.1025)

    prob.set_val('DESIGN.LP_Nmech', 4666.1, units='rpm')
    prob.set_val('DESIGN.HP_Nmech', 14705.7, units='rpm')

    # initial guesses
    prob['DESIGN.balance.FAR_core'] = 0.025
    prob['DESIGN.balance.FAR_ab'] = 0.025
    prob['DESIGN.balance.BPR'] = 1.0
    prob['DESIGN.balance.W'] = 100.
    prob['DESIGN.balance.lpt_PR'] = 3.5
    prob['DESIGN.balance.hpt_PR'] = 2.5
    prob['DESIGN.fc.balance.Pt'] = 5.2
    prob['DESIGN.fc.balance.Tt'] = 440.0
    prob['DESIGN.mixer.balance.P_tot']= 15

    for i,pt in enumerate(od_pts):
        prob.set_val(pt+'.balance.rhs:FAR_core', 3100, units='degR')
        prob.set_val(pt+'.fc.alt', od_alts[i], units='ft')
        prob.set_val(pt+'.fc.MN', od_MNs[i])

        prob[pt+'.balance.FAR_core'] = 0.025
        prob[pt+'.balance.FAR_ab'] = 0.025
        prob[pt+'.balance.BPR'] = 2.5
        prob[pt+'.balance.W'] = 50.
        prob[pt+'.balance.HP_Nmech'] = 14000
        prob[pt+'.balance.LP_Nmech'] = 4000
        prob[pt+'.fc.balance.Pt'] = 5.2
        prob[pt+'.fc.balance.Tt'] = 440.0
        prob[pt+'.mixer.balance.P_tot']= 15
        prob[pt+'.hpt.PR'] = 2.0
        prob[pt+'.lpt.PR'] = 4.0
        prob[pt+'.fan.map.RlineMap'] = 2.0
        prob[pt+'.lpc.map.RlineMap'] = 2.0
        prob[pt+'.hpc.map.RlineMap'] = 2.0

    st = time.time()

    prob.set_solver_print(level=-1)
    prob.set_solver_print(level=2, depth=1)

    prob.run_model()
    page_viewer('DESIGN')

    for T in [3200, 3100, 3000]:
        prob['balance.rhs:FAR_ab'] = T

        prob.run_model()

        page_viewer('OD0')

    print()
    print("time", time.time() - st)

