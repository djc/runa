from __future__ import print_function
import sys, os, unittest, subprocess, json
from runac import util
import runac

DIR = os.path.dirname(__file__)
TEST_DIR = os.path.join(DIR, 'tests')

class RunaTest(unittest.TestCase):

	def __init__(self, fn):
		unittest.TestCase.__init__(self)
		self.fn = fn
		self.base = self.fn.rsplit('.rns', 1)[0]
		self.bin = self.base + '.test'
		self.opts = self.getspec()

	def getspec(self):
		with open(self.fn) as f:
			h = f.readline()
			if h.startswith('# test: '):
				return json.loads(h[8:])
			else:
				return {}
	
	def compile(self):
		if self.opts.get('type', 'test') == 'show':
			return [0, '\n'.join(runac.show(self.fn, None)) + '\n', bytes()]
		try:
			runac.compile(self.fn, self.bin)
			return [0, bytes(), bytes()]
		except util.Error as e:
			return [0, bytes(), e.show()]
		except util.ParseError as e:
			return [0, bytes(), e.show()]
	
	def runTest(self):
		
		res = self.compile()
		if any(res) and sys.version_info[0] > 2:
			for i, s in enumerate(res[1:]):
				res[i + 1] = s.encode('utf-8')
		
		if not any(res):
			cmd = [self.bin] + self.opts.get('args', [])
			opts = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
			proc = subprocess.Popen(cmd, **opts)
			res = [proc.wait(), proc.stdout.read(), proc.stderr.read()]
			proc.stdout.close()
			proc.stderr.close()
		
		expected = [self.opts.get('ret', 0), bytes(), bytes()]
		for i, ext in enumerate(('.out', '.err')):
			if os.path.exists(self.base + ext):
				with open(self.base + ext, 'rb') as f:
					expected[i + 1] = f.read()
		
		if self is None:
			return res == expected
		elif res[1]:
			self.assertEqual(expected[0], res[0])
			self.assertEqual(expected[1], res[1])
			self.assertEqual(expected[2], res[2])
		elif res[2]:
			self.assertEqual(expected[2], res[2])
			self.assertEqual(expected[1], res[1])
			self.assertEqual(expected[0], res[0])

def tests():
	tests = []
	for fn in os.listdir(TEST_DIR):
		fn = os.path.join(TEST_DIR, fn)
		if fn.endswith('.rns'):
			tests.append(RunaTest(fn))
	return tests

def suite():
	suite = unittest.TestSuite()
	suite.addTests(tests())
	return suite

IGNORE = [
	'Memcheck', 'WARNING:', 'HEAP SUMMARY:', 'LEAK SUMMARY:',
	'All heap blocks', 'For counts',
]

def valgrind(test):
	
	args = test.opts.get('args', [])
	cmd = ['valgrind', '--leak-check=full', test.bin] + args
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
	
	for test in tests():
		
		compiled = os.path.exists(test.bin)
		if not compiled or os.stat(test.fn).st_mtime >= os.stat(test.bin).st_mtime:
			res = test.compile()
			if res[2] is not None:
				continue
		
		print('Running %s...' % test.bin, end=' ')
		count = valgrind(test)
		print(' ' * (40 - len(test.bin)), '%3i' % count)

if __name__ == '__main__':
	if len(sys.argv) > 1 and sys.argv[1] == '--leaks':
		leaks()
	elif len(sys.argv) > 1:
		print(run(None, sys.argv[1]))
	else:
	    unittest.main(defaultTest='suite')
