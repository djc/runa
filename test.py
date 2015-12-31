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
			return '\n'.join(runac.show(self.fn, None)) + '\n'
		try:
			runac.compile(self.fn, self.bin)
			return None
		except util.Error as e:
			return e.show()
		except util.ParseError as e:
			return e.show()
	
	def runTest(self):
		
		out = self.compile()
		if out and sys.version_info[0] > 2:
			out = out.encode('utf-8')
		
		if not out:
			cmd = [self.bin] + self.opts.get('args', [])
			opts = {'stdout': subprocess.PIPE, 'stderr': subprocess.PIPE}
			proc = subprocess.Popen(cmd, **opts)
			res = [proc.wait(), proc.stdout.read(), proc.stderr.read()]
			proc.stdout.close()
			proc.stderr.close()
		elif self.opts.get('type', 'test') == 'show':
			res = [0, out, bytes()]
		else:
			res = [0, bytes(), out]
		
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

def suite():
	suite = unittest.TestSuite()
	for fn in os.listdir(TEST_DIR):
		fn = os.path.join(TEST_DIR, fn)
		if fn.endswith('.rns'):
			suite.addTest(RunaTest(fn))
	return suite

IGNORE = [
	'Memcheck', 'WARNING:', 'HEAP SUMMARY:', 'LEAK SUMMARY:',
	'All heap blocks', 'For counts',
]

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
		
		print('Running %s...' % bin, end=' ')
		count = valgrind(bin, getspec(test))
		print(' ' * (40 - len(bin)), '%3i' % count)

if __name__ == '__main__':
	if len(sys.argv) > 1 and sys.argv[1] == '--leaks':
		leaks()
	elif len(sys.argv) > 1:
		print(run(None, sys.argv[1]))
	else:
	    unittest.main(defaultTest='suite')
