import openmdao.api as om

from pycycle.constants import AIR_MIX
from pycycle.cea.unit_comps import EngUnitStaticProps, EngUnitProps
from pycycle.cea import species_data
from pycycle.isentropic.entropy_map_data import AIR_MIX_entropy

class SetStatic(om.Group):

    def initialize(self):
        self.options.declare('mode', values=['Ps', 'area', 'MN'])
        self.options.declare('thermo_data', desc='thermodynamic data set', recordable=False)
        self.options.declare('fl_name',
                              default="flow",
                              desc='flowstation name of the output flow variables')
        self.options.declare('init_reacts',
                              default=AIR_MIX,
                              desc='initial amounts of each species in the flow')
        self.options.declare('computation_mode', default='CEA', values=('CEA', 'isentropic'), 
                              desc='mode of computation')
        self.options.declare('gamma', default=1.4, 
                              desc='ratio of specific heats, only used in isentropic mode')
        self.options.declare('S_data', default=AIR_MIX_entropy, desc='entropy property data')
        self.options.declare('h_base', default=0, desc='enthalpy at base temperature (units are cal/g)')
        self.options.declare('T_base', default=302.4629819, desc='base temperature (units are degK)')
        self.options.declare('Cp', default=0.24015494, desc='constant specific heat that is assumed (units are cal/(g*degK)')
        self.options.declare('MW', default=28.2, desc='molecular weight of gas in units of g/mol')

    def setup(self):

        mode = self.options['mode']

        thermo_data = self.options['thermo_data']
        init_reacts = self.options['init_reacts']
        fl_name = self.options['fl_name']
        comp_mode = self.options['computation_mode']

        if comp_mode == 'CEA':
            from pycycle.cea.set_total import SetTotal

            statics = SetTotal(mode='S',
                               fl_name=fl_name,
                               thermo_data=thermo_data,
                               init_reacts=init_reacts,
                               for_statics=mode)

        elif comp_mode == 'isentropic':
            from pycycle.isentropic.set_total import SetTotal
            

            statics = SetTotal(mode='S',
                               fl_name=fl_name,
                               thermo_data=thermo_data,
                               init_reacts=init_reacts,
                               for_statics=mode,
                               gamma=self.options['gamma'],
                               S_data=self.options['S_data'],
                               h_base=self.options['h_base'],
                               T_base=self.options['T_base'],
                               MW=self.options['MW'],
                               Cp=self.options['Cp'])

        # have to promote things differently depending on which mode we are
        if comp_mode == 'CEA':
            thermo = species_data.Thermo(thermo_data, init_reacts)
            if mode == 'Ps':
                self.add_subsystem('statics', statics,
                                   promotes_inputs=[('P', 'Ps'), 'S', 'ht', 'W', 'b0'],
                                   promotes_outputs=['MN', 'V', 'Vsonic', 'area',
                                                     'T', 'h', 'gamma', 'Cp', 'Cv', 'rho', 'n', 'n_moles'])
            elif mode == 'MN':
                self.add_subsystem('statics', statics,
                                   promotes_inputs=['MN', 'S', 'ht', 'W', 'guess:*', 'b0'],#
                                   promotes_outputs=['V', 'Vsonic', 'area',
                                                     'Ps', 'T', 'h', 'gamma', 'Cp', 'Cv', 'rho', 'n', 'n_moles'])

            else:
                self.add_subsystem('statics', statics,
                                   promotes_inputs=['area', 'S', 'ht', 'W', 'guess:*', 'b0'],#
                                   promotes_outputs=['V', 'Vsonic', 'MN',
                                                     'Ps', 'T', 'h', 'gamma', 'Cp', 'Cv', 'rho', 'n', 'n_moles'])

        elif comp_mode == 'isentropic':
            thermo = thermo_hack 
            if mode == 'Ps':
                self.add_subsystem('statics', statics,
                                   promotes_inputs=[('P', 'Ps'), 'S', 'ht', 'W', 'b0'],
                                   promotes_outputs=['MN', 'V', 'Vsonic', 'area',
                                                     'T', 'h', 'gamma', 'Cp', 'Cv', 'rho', 'n', 'n_moles'])
            elif mode == 'MN':
                self.add_subsystem('statics', statics,
                                   promotes_inputs=['MN', 'S', 'ht', 'W', 'b0'],#
                                   promotes_outputs=['V', 'Vsonic', 'area',
                                                     'Ps', 'T', 'h', 'gamma', 'Cp', 'Cv', 'rho', 'n', 'n_moles'])

            else:
                self.add_subsystem('statics', statics,
                                   promotes_inputs=['area', 'S', 'ht', 'W', 'b0'],#
                                   promotes_outputs=['V', 'Vsonic', 'MN',
                                                     'Ps', 'T', 'h', 'gamma', 'Cp', 'Cv', 'rho', 'n', 'n_moles'])

            self.set_input_defaults('MN', .5, units=None)


        p_inputs = ('T', 'P', 'h', 'S', 'gamma', 'Cp', 'Cv', 'rho', 'n', 'n_moles', 'b0')
        p_outputs = tuple(['{0}:{1}'.format(fl_name, in_name) for in_name in p_inputs])
        # need to redefine this so that P gets promoted as P. Needed the first definition for the list comprehension
        p_inputs = ('T', ('P', 'Ps'), 'h', 'S', 'gamma', 'Cp', 'Cv', 'rho', 'n', 'n_moles')

        self.add_subsystem('flow', EngUnitProps(thermo=thermo, fl_name=fl_name),
                            promotes_inputs=p_inputs,
                            promotes_outputs=p_outputs)

        p_inputs = ('area', 'W', 'V', 'Vsonic', 'MN')
        p_outputs = tuple(['{0}:{1}'.format(fl_name, in_name) for in_name in p_inputs])
        eng_units_statics = EngUnitStaticProps(thermo, fl_name)
        self.add_subsystem('flow_static', eng_units_statics,
                            promotes_inputs=p_inputs,
                            promotes_outputs=p_outputs)

        self.set_input_defaults('area', units='m**2', val=1.)
        # self.set_order(['statics', 'flow', 'flow_static'])

#thermo hack:
class thermo_hack():
    num_prod = 1
    b0 = -1

if __name__ == "__main__":
    from pycycle import constants


    thermo=species_data.Thermo(species_data.janaf, constants.AIR_MIX)

    # p = om.Problem()
    # p.model = SetStatic(mode='area', thermo_data=species_data.janaf)
    # p.model.set_input_defaults('b0', thermo.b0)
    # p.model.set_input_defaults('S', 1., units="cal/(g*degK)")
    # p.model.set_input_defaults('W', 1., units='kg/s')
    # p.setup(force_alloc_complex=True)
    # p.run_model()
    # p.check_partials(method='cs', compact_print=True)

    p = om.Problem()
    # indeps = p.model.add_subsystem('des_vars', om.IndepVarComp(), promotes=['*'])
    # indeps.add_output('T', 1500, units="degK")
    # indeps.add_output('P', 1.034210, units="bar")

    p.model = SetStatic(mode='Ps', thermo_data=species_data.janaf)
    p.model.set_input_defaults('S', 1., units="cal/(g*degK)")
    p.model.set_input_defaults('W', 1., units="kg/s")
    p.model.set_input_defaults('b0', thermo.b0)
    p.model.set_input_defaults('Ps', 1.034210, units="bar")
    p.setup()
    p.run_model()
