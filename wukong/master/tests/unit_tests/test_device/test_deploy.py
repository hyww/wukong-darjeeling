import os, sys
import unittest
sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../..'))
from test_environment_device import WuTest


class TestDeploy(unittest.TestCase):
    def setUp(self):
        self.test = WuTest(False, False)

    def test_application(self):        
        nodes_info = self.test.discovery()
        self.test.loadApplication("../../applications/ac49daab4d351391b3d544fb182c3074") 
    	self.test.mapping(nodes_info)
    	self.test.deploy_with_discovery()
    def test_super_application(self):
        for i in xrange(10):
            nodes_info = self.test.discovery()
            self.test.loadApplication("../../applications/ac49daab4d351391b3d544fb182c3074") 
            self.test.mapping(nodes_info)
            self.test.deploy_with_discovery()


if __name__ == '__main__':
    unittest.main()

