import parser, codegen, compile
import sys, os, unittest, subprocess

DIR = os.path.dirname(__file__)
TESTS_DIR = os.path.join(DIR, 'tests')

TESTS = [
	'hello', 'multi-stmt', 'arith-int', 'print-var',
]

def run(self, key):
	
	fullname = os.path.join(TESTS_DIR, key + '.lng')
	base = fullname.rsplit('.lng', 1)[0]
	bin = base + '.test'
	
	compile.compile(fullname, bin)
	out = subprocess.check_output([bin])
	if os.path.exists(base + '.out'):
		expected = open(base + '.out').read()
	else:
		expected = ''
	
	self.assertEquals(out, expected)

def testfunc(key):
	def do(self):
		return self._do(key)
	return do

attrs = {'_do': run}
for key in TESTS:
	m = testfunc(key)
	m.__name__ = 'test_%s' % key
	attrs[m.__name__] = m

LangTests = type('LangTests', (unittest.TestCase,), attrs)

def suite():
    return unittest.makeSuite(LangTests, 'test')

if __name__ == '__main__':
	if len(sys.argv) > 1:
		print run(None, sys.argv[1])
	else:
	    unittest.main(defaultTest='suite')
