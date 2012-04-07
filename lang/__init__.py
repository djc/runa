from . import tokenizer, ast, codegen
import sys, os, subprocess

TRIPLES = {
	'darwin': 'x86_64-apple-darwin11.0.0',
	'linux2': 'x86_64-pc-linux-gnu',
}

def llir(fn, full=True):
	src = codegen.source(ast.parse(tokenizer.tokenize(open(fn))))
	if not full: return src
	triple = 'target triple = "%s"\n' % TRIPLES[sys.platform]
	std = open('std.ll').read()
	return triple + std + src

def compile(fn, outfn):
	
	llfn = fn + '.ll'
	with open(llfn, 'w') as f:
		f.write(llir(fn))
	
	subprocess.check_call(('clang', '-o', outfn, llfn))
	os.unlink(llfn)
