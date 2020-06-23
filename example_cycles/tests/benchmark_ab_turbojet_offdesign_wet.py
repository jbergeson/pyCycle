import numpy as np
import unittest
import os

import openmdao.api as om
import pycycle.api as pyc
from openmdao.utils.assert_utils import assert_near_equal

from example_cycles.afterburning_turbojet import ABTurbojet


class ABTurbojetOffdesignWetTestCase(unittest.TestCase):

    def setUp(self):

        self.prob = om.Problem()

        self.prob.model = pyc.MPCycle()

        self.prob.model.pyc_add_pnt('OD', ABTurbojet(design=False))

        self.prob.set_solver_print(level=-1)
        self.prob.set_solver_print(level=2, depth=1)
        self.prob.setup(check=False)
        self.prob.final_setup()

        self.prob.set_val('OD.fc.alt', 0.0, units='ft')
        self.prob.set_val('OD.fc.MN', 0.000001)
        self.prob.set_val('OD.balance.rhs:FAR', 2370.0, units='degR')
        self.prob.set_val('OD.balance.rhs:W', 2.0)
        self.prob.set_val('OD.ab.Fl_I:FAR', 0.031523391)

        self.prob.set_val('OD.duct1.dPqP', 0.02)
        self.prob.set_val('OD.burner.dPqP', 0.03)
        self.prob.set_val('OD.ab.dPqP', 0.06)
        self.prob.set_val('OD.nozz.Cv', 0.99)

        self.prob.set_val('OD.comp.cool1:frac_W', 0.0789)
        self.prob.set_val('OD.comp.cool1:frac_P', 1.0)
        self.prob.set_val('OD.comp.cool1:frac_work', 1.0)

        self.prob.set_val('OD.comp.cool2:frac_W', 0.0383)
        self.prob.set_val('OD.comp.cool2:frac_P', 1.0)
        self.prob.set_val('OD.comp.cool2:frac_work', 1.0)

        self.prob.set_val('OD.turb.cool1:frac_P', 1.0)
        self.prob.set_val('OD.turb.cool2:frac_P', 0.0)

        self.prob.set_val('OD.comp.s_PR', 2.97619047619)
        self.prob.set_val('OD.comp.s_Wc', 5.71447539197)
        self.prob.set_val('OD.comp.s_eff', 0.975323149236)
        self.prob.set_val('OD.comp.s_Nc', 8070.0)

        self.prob.set_val('OD.turb.s_PR', 0.692263737296)
        self.prob.set_val('OD.turb.s_Wp', 0.259890960213)
        self.prob.set_val('OD.turb.s_eff', 0.927123760241)
        self.prob.set_val('OD.turb.s_Np', 1.65767490056)

        self.prob.set_val('OD.inlet.area', 581.693962336, units='inch**2')
        self.prob.set_val('OD.duct1.area', 593.565267689, units='inch**2')
        self.prob.set_val('OD.comp.area', 148.263145086, units='inch**2')
        self.prob.set_val('OD.burner.area', 224.924279335, units='inch**2')
        self.prob.set_val('OD.turb.area', 504.741845228, units='inch**2')
        self.prob.set_val('OD.ab.area', 536.954431167, units='inch**2')


        self.prob['OD.balance.W'] = 168.453135137
        self.prob['OD.balance.FAR'] = 0.0175506829934
        self.prob['OD.balance.Nmech'] = 8070.0
        self.prob['OD.fc.balance.Pt'] = 14.6955113159
        self.prob['OD.fc.balance.Tt'] = 518.665288153
        self.prob['OD.turb.PR'] = 4.46138725662

    def benchmark_case1(self):
        # ADP Point
        np.seterr(divide='raise')

        self.prob.run_model()
        tol = 1e-3

        print()

        reg_data = 168.005
        pyc = self.prob['OD.inlet.Fl_O:stat:W'][0]
        print('W:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 13.500
        pyc = self.prob['OD.perf.OPR'][0]
        print('OPR:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 0.01755
        pyc = self.prob['OD.balance.FAR'][0]
        print('Main FAR:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 8070.00
        pyc = self.prob['OD.balance.Nmech'][0]
        print('HP Nmech:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 17799.7
        pyc = self.prob['OD.perf.Fg'][0]
        print('Fg:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 1.61420
        pyc = self.prob['OD.perf.TSFC'][0]
        print('TSFC:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 1190.18
        pyc = self.prob['OD.comp.Fl_O:tot:T'][0]
        print('Tt3:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        print()

    def benchmark_case2(self):
        np.seterr(divide='raise')
        self.prob['OD.fc.MN'] = 0.8
        self.prob['OD.fc.alt'] = 0.0
        self.prob['OD.balance.rhs:FAR'] = 2370.0
        self.prob['OD.ab.Fl_I:FAR'] = 0.022759941
        self.prob['OD.balance.rhs:W'] = 2.0

        self.prob.run_model()
        tol = 1e-3

        print()

        reg_data = 225.917
        pyc = self.prob['OD.inlet.Fl_O:stat:W'][0]
        print('W:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 11.971
        pyc = self.prob['OD.perf.OPR'][0]
        print('OPR:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 0.01629
        pyc = self.prob['OD.balance.FAR'][0]
        print('Main FAR:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 8288.85
        pyc = self.prob['OD.balance.Nmech'][0]
        print('HP Nmech:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 24085.2
        pyc = self.prob['OD.perf.Fg'][0]
        print('Fg:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 1.71066
        pyc = self.prob['OD.perf.TSFC'][0]
        print('TSFC:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        reg_data = 1280.18
        pyc = self.prob['OD.comp.Fl_O:tot:T'][0]
        print('Tt3:', reg_data, pyc)
        assert_near_equal(pyc, reg_data, tol)

        print()


if __name__ == "__main__":
    unittest.main()
