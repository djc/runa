from . import tokenizer, ast, flow, codegen
from util import Error
import sys, os, subprocess

BASE = os.path.dirname(__path__[0])
RT_DIR = os.path.join(BASE, 'rt')

TRIPLES = {
	'darwin': 'x86_64-apple-darwin11.0.0',
	'linux2': 'x86_64-pc-linux-gnu',
}

def llir(fn, full=True):
	
	node = ast.parse(tokenizer.tokenize(open(fn)))
	src = codegen.source(flow.Module(node))
	if not full:
		return src
	
	std = []
	for fn in sorted(os.listdir(RT_DIR)):
		with open(os.path.join(RT_DIR, fn)) as f:
			std.append(f.read() + '\n')
	
	triple = 'target triple = "%s"\n\n' % TRIPLES[sys.platform]
	return triple + ''.join(std) + src

def compile(fn, outfn):
	
	llfn = fn + '.ll'
	try:
		with open(llfn, 'w') as f:
			f.write(llir(fn))
	except Exception:
		os.unlink(llfn)
		raise
	
	subprocess.check_call(('clang', '-o', outfn, llfn))
	os.unlink(llfn)
