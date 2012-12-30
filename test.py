import runac
import sys, os, unittest, subprocess, json

DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(DIR, 'tests')
TESTS = [i[:-4] for i in os.listdir(TEST_DIR) if i.endswith('.rns')]

def run(self, key):
	
	fullname = os.path.join(TEST_DIR, key + '.rns')
	base = fullname.rsplit('.rns', 1)[0]
	bin = base + '.test'
	
	spec = {}
	with open(fullname) as f:
		h = f.readline()
		if h.startswith('# test: '):
			spec.update(json.loads(h[8:]))
	
	out = None
	try:
		runac.compile(runac.ir(fullname), bin)
	except runac.Error as e:
		ret = 0
		out = e.show(fullname)
	
	if not out:
		cmd = [bin] + spec.get('args', [])
		proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
		ret = proc.wait()
		out = proc.stdout.read()
	
	if os.path.exists(base + '.out'):
		expected = open(base + '.out').read()
	else:
		expected = ''
	
	expret = spec.get('ret', 0)
	if self is None:
		return expret == ret and expected == out
	else:
		self.assertEqual(ret, expret)
		self.assertMultiLineEqual(expected, out)

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
