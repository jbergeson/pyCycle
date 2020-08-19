import sys

import openmdao.api as om

import pycycle.api as pyc

from pycycle.elements.combustor_isentropic import IsentropicCombustor
from pycycle.elements.turbine_isentropic import IsentropicTurbine
from pycycle.isentropic.AIR_FUEL_MIX_entropy_full import AIR_FUEL_MIX_entropy
from pycycle.isentropic.entropy_map_data import AIR_MIX_entropy


class Turbojet(pyc.Cycle):

    def initialize(self):
        self.options.declare('design', default=True,
                              desc='Switch between on-design and off-design calculation.')

    def setup(self):

        thermo_spec = pyc.species_data.janaf
        design = self.options['design']
        comp_mode = 'isentropic'
        S_data = AIR_FUEL_MIX_entropy
        T_base = 1297.91021 #degK
        h_base = 86.73820575 #cal/g
        Cp = 0.29460272 #cal/(g*degK)

        # Add engine elements
        self.pyc_add_element('fc', pyc.FlightConditions(thermo_data=thermo_spec,
                                    elements=pyc.AIR_MIX, computation_mode=comp_mode))
        self.pyc_add_element('inlet', pyc.Inlet(design=design, thermo_data=thermo_spec,
                                    elements=pyc.AIR_MIX, computation_mode=comp_mode))
        self.pyc_add_element('comp', pyc.Compressor(map_data=pyc.AXI5, design=design,
                                    thermo_data=thermo_spec, elements=pyc.AIR_MIX, computation_mode=comp_mode, gamma=1.36872902),
                                    promotes_inputs=['Nmech'])
        self.pyc_add_element('burner', IsentropicCombustor(design=design,thermo_data=thermo_spec,
                                    inflow_elements=pyc.AIR_MIX,
                                    air_fuel_elements=pyc.AIR_FUEL_MIX,
                                    fuel_type='JP-7', gamma=1.30235009, S_data=S_data, Cp=Cp, h_base=h_base, T_base=T_base))
        self.pyc_add_element('turb', IsentropicTurbine(map_data=pyc.LPT2269, design=design,
                                    thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX, gamma=1.32500477, S_data=S_data, Cp=Cp, h_base=h_base, T_base=T_base),
                                    promotes_inputs=['Nmech'])
        self.pyc_add_element('nozz', pyc.Nozzle(nozzType='CD', lossCoef='Cv',
                                    thermo_data=thermo_spec, elements=pyc.AIR_FUEL_MIX, computation_mode=comp_mode, S_data=S_data, Cp=Cp, h_base=h_base, T_base=T_base))
        self.pyc_add_element('shaft', pyc.Shaft(num_ports=2),promotes_inputs=['Nmech'])
        self.pyc_add_element('perf', pyc.Performance(num_nozzles=1, num_burners=1))

        # Connect flow stations
        self.pyc_connect_flow('fc.Fl_O', 'inlet.Fl_I', connect_w=False)
        self.pyc_connect_flow('inlet.Fl_O', 'comp.Fl_I')
        self.pyc_connect_flow('comp.Fl_O', 'burner.Fl_I')
        self.pyc_connect_flow('burner.Fl_O', 'turb.Fl_I')
        self.pyc_connect_flow('turb.Fl_O', 'nozz.Fl_I')

        # Make other non-flow connections
        # Connect turbomachinery elements to shaft
        self.connect('comp.trq', 'shaft.trq_0')
        self.connect('turb.trq', 'shaft.trq_1')

        # Connnect nozzle exhaust to freestream static conditions
        self.connect('fc.Fl_O:stat:P', 'nozz.Ps_exhaust')

        # Connect outputs to perfomance element
        self.connect('inlet.Fl_O:tot:P', 'perf.Pt2')
        self.connect('comp.Fl_O:tot:P', 'perf.Pt3')
        self.connect('burner.Wfuel', 'perf.Wfuel_0')
        self.connect('inlet.F_ram', 'perf.ram_drag')
        self.connect('nozz.Fg', 'perf.Fg_0')

        # Add balances for design and off-design
        balance = self.add_subsystem('balance', om.BalanceComp())
        if design:

            balance.add_balance('W', units='lbm/s', eq_units='lbf', rhs_name='Fn_target')
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('perf.Fn', 'balance.lhs:W')

            balance.add_balance('FAR', eq_units='degR', lower=1e-4, val=.017, rhs_name='T4_target')
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('burner.Fl_O:tot:T', 'balance.lhs:FAR')

            balance.add_balance('turb_PR', val=1.5, lower=1.001, upper=8, eq_units='hp', rhs_val=0.)
            self.connect('balance.turb_PR', 'turb.PR')
            self.connect('shaft.pwr_net', 'balance.lhs:turb_PR')

        else:

            balance.add_balance('FAR', eq_units='lbf', lower=1e-4, val=.3, rhs_name='Fn_target')
            self.connect('balance.FAR', 'burner.Fl_I:FAR')
            self.connect('perf.Fn', 'balance.lhs:FAR')

            balance.add_balance('Nmech', val=1.5, units='rpm', lower=500., eq_units='hp', rhs_val=0.)
            self.connect('balance.Nmech', 'Nmech')
            self.connect('shaft.pwr_net', 'balance.lhs:Nmech')

            balance.add_balance('W', val=168.0, units='lbm/s', eq_units='inch**2')
            self.connect('balance.W', 'inlet.Fl_I:stat:W')
            self.connect('nozz.Throat:stat:area', 'balance.lhs:W')

        # Setup solver to converge engine
        self.set_order(['fc', 'inlet', 'comp', 'burner', 'turb', 'nozz', 'shaft', 'perf', 'balance'])

        newton = self.nonlinear_solver = om.NewtonSolver()
        newton.options['atol'] = 1e-6
        newton.options['rtol'] = 1e-6
        newton.options['iprint'] = 2
        newton.options['maxiter'] = 15
        newton.options['solve_subsystems'] = True
        newton.options['max_sub_solves'] = 100
        newton.options['reraise_child_analysiserror'] = False
        
        self.linear_solver = om.DirectSolver(assemble_jac=True)

def viewer(prob, pt, file=sys.stdout):
    """
    print a report of all the relevant cycle properties
    """

    summary_data = (prob[pt+'.fc.Fl_O:stat:MN'], prob[pt+'.fc.alt'], prob[pt+'.inlet.Fl_O:stat:W'], 
                    prob[pt+'.perf.Fn'], prob[pt+'.perf.Fg'], prob[pt+'.inlet.F_ram'],
                    prob[pt+'.perf.OPR'], prob[pt+'.perf.TSFC'])

    print(file=file, flush=True)
    print(file=file, flush=True)
    print(file=file, flush=True)
    print("----------------------------------------------------------------------------", file=file, flush=True)
    print("                              POINT:", pt, file=file, flush=True)
    print("----------------------------------------------------------------------------", file=file, flush=True)
    print("                       PERFORMANCE CHARACTERISTICS", file=file, flush=True)
    print("    Mach      Alt       W      Fn      Fg    Fram     OPR     TSFC  ", file=file, flush=True)
    print(" %7.5f  %7.1f %7.3f %7.1f %7.1f %7.1f %7.3f  %7.5f" %summary_data, file=file, flush=True)


    fs_names = ['fc.Fl_O', 'inlet.Fl_O', 'comp.Fl_O', 'burner.Fl_O',
                'turb.Fl_O', 'nozz.Fl_O']
    fs_full_names = [f'{pt}.{fs}' for fs in fs_names]
    pyc.print_flow_station(prob, fs_full_names, file=file)

    comp_names = ['comp']
    comp_full_names = [f'{pt}.{c}' for c in comp_names]
    pyc.print_compressor(prob, comp_full_names, file=file)

    pyc.print_burner(prob, [f'{pt}.burner'])

    turb_names = ['turb']
    turb_full_names = [f'{pt}.{t}' for t in turb_names]
    pyc.print_turbine(prob, turb_full_names, file=file)

    noz_names = ['nozz']
    noz_full_names = [f'{pt}.{n}' for n in noz_names]
    pyc.print_nozzle(prob, noz_full_names, file=file)

    shaft_names = ['shaft']
    shaft_full_names = [f'{pt}.{s}' for s in shaft_names]
    pyc.print_shaft(prob, shaft_full_names, file=file)


class MPTurbojet(pyc.MPCycle):

    def setup(self):

        # Create design instance of model
        self.pyc_add_pnt('DESIGN', Turbojet())

        self.set_input_defaults('DESIGN.Nmech', 8070.0, units='rpm')
        self.set_input_defaults('DESIGN.inlet.MN', 0.60)
        self.set_input_defaults('DESIGN.comp.MN', 0.020)#.2
        self.set_input_defaults('DESIGN.burner.MN', 0.020)#.2
        self.set_input_defaults('DESIGN.turb.MN', 0.4)

        self.pyc_add_cycle_param('burner.dPqP', 0.03)
        self.pyc_add_cycle_param('nozz.Cv', 0.99)
        self.pyc_add_cycle_param('burner.fuel_MW', 28.390194936, units='g/mol') #for JP-7

        
        # define the off-design conditions we want to run
        self.od_pts = ['OD0', 'OD1']
        self.od_MNs = [0.000001, 0.2]
        self.od_alts = [0.0, 5000]
        self.od_Fns =[11000.0, 8000.0]

        for i,pt in enumerate(self.od_pts):
            self.pyc_add_pnt(pt, Turbojet(design=False))

            self.set_input_defaults(pt+'.fc.MN', val=self.od_MNs[i])
            self.set_input_defaults(pt+'.fc.alt', self.od_alts[i], units='ft')
            self.set_input_defaults(pt+'.balance.Fn_target', self.od_Fns[i], units='lbf')  

        self.pyc_connect_des_od('comp.s_PR', 'comp.s_PR')
        self.pyc_connect_des_od('comp.s_Wc', 'comp.s_Wc')
        self.pyc_connect_des_od('comp.s_eff', 'comp.s_eff')
        self.pyc_connect_des_od('comp.s_Nc', 'comp.s_Nc')

        self.pyc_connect_des_od('turb.s_PR', 'turb.s_PR')
        self.pyc_connect_des_od('turb.s_Wp', 'turb.s_Wp')
        self.pyc_connect_des_od('turb.s_eff', 'turb.s_eff')
        self.pyc_connect_des_od('turb.s_Np', 'turb.s_Np')

        self.pyc_connect_des_od('inlet.Fl_O:stat:area', 'inlet.area')
        self.pyc_connect_des_od('comp.Fl_O:stat:area', 'comp.area')
        self.pyc_connect_des_od('burner.Fl_O:stat:area', 'burner.area')
        self.pyc_connect_des_od('turb.Fl_O:stat:area', 'turb.area')

        self.pyc_connect_des_od('nozz.Throat:stat:area', 'balance.rhs:W')

if __name__ == "__main__":

    import time

    prob = om.Problem()

    prob.model = mp_turbojet = MPTurbojet()

    prob.setup(check=False)

    #Define the design point
    prob.set_val('DESIGN.fc.alt', 0, units='ft')
    prob.set_val('DESIGN.fc.MN', 0.000001)
    prob.set_val('DESIGN.balance.Fn_target', 11800.0, units='lbf')
    prob.set_val('DESIGN.balance.T4_target', 2370.0, units='degR') 
    prob.set_val('DESIGN.comp.PR', 13.5) 
    prob.set_val('DESIGN.comp.eff', 0.83)
    prob.set_val('DESIGN.turb.eff', 0.86)

    # Set initial guesses for balances
    prob['DESIGN.balance.FAR'] = 0.0175506829934
    prob['DESIGN.balance.W'] = 168.453135137
    prob['DESIGN.balance.turb_PR'] = 4.46138725662
    prob['DESIGN.fc.balance.Pt'] = 14.6955113159
    prob['DESIGN.fc.balance.Tt'] = 518.665288153

    for i,pt in enumerate(mp_turbojet.od_pts):

        # initial guesses
        prob[pt+'.balance.W'] = 166.073
        prob[pt+'.balance.FAR'] = 0.01680
        prob[pt+'.balance.Nmech'] = 8197.38
        prob[pt+'.fc.balance.Pt'] = 15.703
        prob[pt+'.fc.balance.Tt'] = 558.31
        prob[pt+'.turb.PR'] = 4.6690

    st = time.time()

    prob.set_solver_print(level=-1)
    prob.set_solver_print(level=2, depth=1)
    prob.run_model()

    for pt in ['DESIGN']+mp_turbojet.od_pts:
        viewer(prob, pt)

    print()
    print("time", time.time() - st)

    print('W:', prob['DESIGN.inlet.Fl_O:stat:W'][0] - 147.55302767907438)
    print('OPR:', prob['DESIGN.perf.OPR'][0] - 13.5)
    print('Main FAR:', prob['DESIGN.balance.FAR'][0] - 0.017550780065132325)
    print('HPT PR:', prob['DESIGN.balance.turb_PR'][0] - 3.876811007533011)
    print('Fg:', prob['DESIGN.perf.Fg'][0] - 11800.004972857632)
    print('TSFC:', prob['DESIGN.perf.TSFC'][0] - 0.7900690482114057)
    print('Tt3:', prob['DESIGN.comp.Fl_O:tot:T'][0] - 1190.1777648504044)
    print('W:', prob['OD0.inlet.Fl_O:stat:W'][0] - 142.69375084217026)
    print('OPR:', prob['OD0.perf.OPR'][0] - 12.840848747331666)
    print('Main FAR:', prob['OD0.balance.FAR'][0] - 0.016651018104669776)
    print('HP Nmech:', prob['OD0.balance.Nmech'][0] - 7936.36544281587)
    print('Fg:', prob['OD0.perf.Fg'][0] - 11000.004885187022)
    print('TSFC:', prob['OD0.perf.TSFC'][0] - 0.7775987704675483)
    print('Tt3:', prob['OD0.comp.Fl_O:tot:T'][0] - 1169.5125213466022)
    print()
    print('DESIGN.fc.Fl_O:tot:T', prob['DESIGN.fc.Fl_O:tot:T'] - 518.67)
    print('DESIGN.fc.Fl_O:tot:P', prob['DESIGN.fc.Fl_O:tot:P'] - 14.69589998)
    print('DESIGN.fc.Fl_O:stat:T', prob['DESIGN.fc.Fl_O:stat:T'] - 518.67)
    print('DESIGN.fc.Fl_O:stat:P', prob['DESIGN.fc.Fl_O:stat:P'] - 14.69589998)
    print()
    print('DESIGN.inlet.Fl_O:tot:T', prob['DESIGN.inlet.Fl_O:tot:T'] - 518.67)
    print('DESIGN.inlet.Fl_O:tot:P', prob['DESIGN.inlet.Fl_O:tot:P'] - 14.69589998)
    print('DESIGN.inlet.Fl_O:stat:T', prob['DESIGN.inlet.Fl_O:stat:T'] - 483.7955408)
    print('DESIGN.inlet.Fl_O:stat:P', prob['DESIGN.inlet.Fl_O:stat:P'] - 11.52060553)
    print()
    print('DESIGN.comp.Fl_O:tot:T', prob['DESIGN.comp.Fl_O:tot:T'] - 1190.17776485)
    print('DESIGN.comp.Fl_O:tot:P', prob['DESIGN.comp.Fl_O:tot:P'] - 198.39464979)
    print('DESIGN.comp.Fl_O:stat:T', prob['DESIGN.comp.Fl_O:stat:T'] - 1190.0900001)
    print('DESIGN.comp.Fl_O:stat:P', prob['DESIGN.comp.Fl_O:stat:P'] - 198.34034952)
    print()
    print('DESIGN.burner.Fl_O:tot:T', prob['DESIGN.burner.Fl_O:tot:T'] - 2370.)
    print('DESIGN.burner.Fl_O:tot:P', prob['DESIGN.burner.Fl_O:tot:P'] - 192.4428103)
    print('DESIGN.burner.Fl_O:stat:T', prob['DESIGN.burner.Fl_O:stat:T'] - 2369.85669074)
    print('DESIGN.burner.Fl_O:stat:P', prob['DESIGN.burner.Fl_O:stat:P'] - 192.39269275)
    print()
    print('DESIGN.turb.Fl_O:tot:T', prob['DESIGN.turb.Fl_O:tot:T'] - 1808.17420214)
    print('DESIGN.turb.Fl_O:tot:P', prob['DESIGN.turb.Fl_O:tot:P'] - 49.63946138)
    print('DESIGN.turb.Fl_O:stat:T', prob['DESIGN.turb.Fl_O:stat:T'] - 1762.45738007)
    print('DESIGN.turb.Fl_O:stat:P', prob['DESIGN.turb.Fl_O:stat:P'] - 44.70736449)
    print()
    print('OD0.fc.Fl_O:tot:T', prob['OD0.fc.Fl_O:tot:T'] - 518.67)
    print('OD0.fc.Fl_O:tot:P', prob['OD0.fc.Fl_O:tot:P'] - 14.69589998)
    print('OD0.fc.Fl_O:stat:T', prob['OD0.fc.Fl_O:stat:T'] - 518.67)
    print('OD0.fc.Fl_O:stat:P', prob['OD0.fc.Fl_O:stat:P'] - 14.69589998)
    print()
    print('OD0.inlet.Fl_O:tot:T', prob['OD0.inlet.Fl_O:tot:T'] - 518.67)
    print('OD0.inlet.Fl_O:tot:P', prob['OD0.inlet.Fl_O:tot:P'] - 14.69589998)
    print('OD0.inlet.Fl_O:stat:T', prob['OD0.inlet.Fl_O:stat:T'] - 487.1672388)
    print('OD0.inlet.Fl_O:stat:P', prob['OD0.inlet.Fl_O:stat:P'] - 11.80377127)
    print()
    print('OD0.comp.Fl_O:tot:T', prob['OD0.comp.Fl_O:tot:T'] - 1169.51252135)
    print('OD0.comp.Fl_O:tot:P', prob['OD0.comp.Fl_O:tot:P'] - 188.70782891)
    print('OD0.comp.Fl_O:stat:T', prob['OD0.comp.Fl_O:stat:T'] - 1169.42470341)
    print('OD0.comp.Fl_O:stat:P', prob['OD0.comp.Fl_O:stat:P'] - 188.65536647)
    print()
    print('OD0.burner.Fl_O:tot:T', prob['OD0.burner.Fl_O:tot:T'] - 2297.4995448)
    print('OD0.burner.Fl_O:tot:P', prob['OD0.burner.Fl_O:tot:P'] - 183.04659404)
    print('OD0.burner.Fl_O:stat:T', prob['OD0.burner.Fl_O:stat:T'] - 2297.35955207)
    print('OD0.burner.Fl_O:stat:P', prob['OD0.burner.Fl_O:stat:P'] - 182.99891039)
    print()
    print('OD0.turb.Fl_O:tot:T', prob['OD0.turb.Fl_O:tot:T'] - 1749.02543919)
    print('OD0.turb.Fl_O:tot:P', prob['OD0.turb.Fl_O:tot:P'] - 47.12910412)
    print('OD0.turb.Fl_O:stat:T', prob['OD0.turb.Fl_O:stat:T'] - 1704.39453313)
    print('OD0.turb.Fl_O:stat:P', prob['OD0.turb.Fl_O:stat:P'] - 42.438566)

    print(prob['DESIGN.fc.Fl_O:stat:gamma'] - 1.40019525)
    print(prob['DESIGN.inlet.Fl_O:stat:gamma'] - 1.40058022)
    print(prob['DESIGN.comp.Fl_O:stat:gamma'] - 1.36872902)
    print(prob['DESIGN.burner.Fl_O:stat:gamma'] - 1.30235009)
    print(prob['DESIGN.turb.Fl_O:stat:gamma'] - 1.32500477)

    print('DESIGN.fc.Fl_O:stat:P', prob.get_val('DESIGN.fc.Fl_O:stat:P', units='bar'), 1.01324664)
    print('DESIGN.inlet.Fl_O:stat:P', prob.get_val('DESIGN.inlet.Fl_O:stat:P', units='bar'), 0.79431779)
    print('DESIGN.comp.Fl_O:stat:P', prob.get_val('DESIGN.comp.Fl_O:stat:P', units='bar'), 13.67508573)
    print('DESIGN.burner.Fl_O:stat:P', prob.get_val('DESIGN.burner.Fl_O:stat:P', units='bar'), 13.26500923)
    print('DESIGN.turb.Fl_O:stat:P', prob.get_val('DESIGN.turb.Fl_O:stat:P', units='bar'), 3.08246428)

    print('DESIGN.fc.Fl_O:tot:h', prob.get_val('DESIGN.fc.Fl_O:tot:h', units='cal/g'), (-3.43655906))
    print('DESIGN.fc.Fl_O:stat:h', prob.get_val('DESIGN.fc.Fl_O:stat:h', units='cal/g'), (-3.43655906))
    print('DESIGN.inlet.Fl_O:tot:h', prob.get_val('DESIGN.inlet.Fl_O:tot:h', units='cal/g'), (-3.43655906))
    print('DESIGN.inlet.Fl_O:stat:h', prob.get_val('DESIGN.inlet.Fl_O:stat:h', units='cal/g'), (-8.08530673))
    print('DESIGN.comp.Fl_O:tot:h', prob.get_val('DESIGN.comp.Fl_O:tot:h', units='cal/g'), 88.24879942)
    print('DESIGN.comp.Fl_O:stat:h', prob.get_val('DESIGN.comp.Fl_O:stat:h', units='cal/g'), 88.23638231)
    print('DESIGN.burner.Fl_O:tot:h', prob.get_val('DESIGN.burner.Fl_O:tot:h', units='cal/g'), 86.72667856)
    print('DESIGN.burner.Fl_O:stat:h', prob.get_val('DESIGN.burner.Fl_O:stat:h', units='cal/g'), 86.70313771)
    print('DESIGN.turb.Fl_O:tot:h', prob.get_val('DESIGN.turb.Fl_O:tot:h', units='cal/g'), (-3.37728508))
    print('DESIGN.turb.Fl_O:stat:h', prob.get_val('DESIGN.turb.Fl_O:stat:h', units='cal/g'), (-10.50204152))