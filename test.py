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
		return e.show()
	except runac.ParseError as e:
		return e.show()

def run(self, key):
	
	fullname = os.path.join(TEST_DIR, key + '.rns')
	base = fullname.rsplit('.rns', 1)[0]
	bin = base + '.test'
	
	spec = getspec(fullname)
	out = compile(fullname, bin)
	if not out:
		cmd = [bin] + spec.get('args', [])
		opts = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
		proc = subprocess.Popen(cmd, **opts)
		res = [proc.wait(), proc.stdout.read(), proc.stderr.read()]
	else:
		res = [0, '', out]
	
	expected = [spec.get('ret', 0), '', '']
	for i, ext in enumerate(('.out', '.err')):
		if os.path.exists(base + ext):
			expected[i + 1] = open(base + ext).read()
	
	if self is None:
		return res == expected
	elif res[1]:
		self.assertEqual(expected[0], res[0])
		self.assertMultiLineEqual(expected[1], res[1])
		self.assertMultiLineEqual(expected[2], res[2])
	elif res[2]:
		self.assertMultiLineEqual(expected[2], res[2])
		self.assertMultiLineEqual(expected[1], res[1])
		self.assertEqual(expected[0], res[0])

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

IGNORE = 'Memcheck WARNING: HEAP SUMMARY: LEAK SUMMARY: For counts'.split()

def valgrind(bin, spec):
	
	cmd = ['valgrind', '--leak-check=full', bin] + spec.get('args', [])
	streams = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
	proc = subprocess.Popen(cmd, **streams)
	proc.wait()
	err = proc.stderr.read()
	
	blocks, cur = [], []
	for ln in err.splitlines():
		
		if not ln.startswith('=='):
			continue
		
		ln = ln.split(' ', 1)[1]
		if not ln.strip():
			if cur:
				blocks.append(cur)
				cur = []
			continue
		
		cur.append(ln)
	
	errors = []
	for bl in blocks:
		if not any(flag for flag in IGNORE if bl[0].startswith(flag)):
			errors.append(bl)
	
	return len(errors)

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
