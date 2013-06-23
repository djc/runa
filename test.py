import runac
import sys, os, unittest, subprocess, json

DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(DIR, 'tests')
TESTS = [i[:-4] for i in os.listdir(TEST_DIR) if i.endswith('.rns')]

def getspec(src):
	with open(src) as f:
		h = f.readline()
		if h.startswith('# test: '):
			return json.loads(h[8:])
		else:
			return {}

def compile(src, bin):
	try:
		runac.compile(runac.ir(src), bin)
		return None
	except runac.Error as e:
		return e.show(src)

def run(self, key):
	
	fullname = os.path.join(TEST_DIR, key + '.rns')
	base = fullname.rsplit('.rns', 1)[0]
	bin = base + '.test'
	
	spec = getspec(fullname)
	out = compile(fullname, bin)
	if not out:
		cmd = [bin] + spec.get('args', [])
		proc = subprocess.Popen(cmd, stdout=subprocess.PIPE)
		ret = proc.wait()
		out = proc.stdout.read()
	else:
		ret = 0
	
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

def valgrind(bin, spec):
	
	cmd = ['valgrind', '--leak-check=full', bin] + spec.get('args', [])
	streams = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
	proc = subprocess.Popen(cmd, **streams)
	ret = proc.wait()
	err = proc.stderr.read()
	
	if 'LEAK SUMMARY:' not in err:
		return 0
	
	lines = [i.split(' ', 1)[1] for i in err.splitlines()]
	start = lines.index('HEAP SUMMARY:')
	end = lines.index('LEAK SUMMARY:')
	return sum(1 for ln in lines[start:end] if not ln.strip()) - 1

def leaks():
	
	for fn in sorted(os.listdir('tests')):
		
		if not fn.endswith('.rns'):
			continue
		
		test = os.path.join('tests', fn)
		bin = test[:-4] + '.test'
		compiled = os.path.exists(bin)
		if not compiled or os.stat(test).st_mtime >= os.stat(bin).st_mtime:
			out = compile(test, bin)
			if out is not None:
				continue
		
		print 'Running %s...' % bin,
		count = valgrind(bin, getspec(test))
		print ' ' * (40 - len(bin)), '%3i' % count

if __name__ == '__main__':
	if len(sys.argv) > 1 and sys.argv[1] == '--leaks':
		leaks()
	elif len(sys.argv) > 1:
		print run(None, sys.argv[1])
	else:
	    unittest.main(defaultTest='suite')
