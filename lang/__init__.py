from . import tokenizer, ast, blocks, ti, specialize, codegen
from util import Error
import sys, os, subprocess

BASE = os.path.dirname(__path__[0])
RT_DIR = os.path.join(BASE, 'rt')

TRIPLES = {
	'darwin': 'x86_64-apple-darwin11.0.0',
	'linux2': 'x86_64-pc-linux-gnu',
}

def tokenize(f):
	return tokenizer.tokenize(f)

def parse(tokens):
	return ast.parse(tokens)

def module(ast):
	return blocks.Module(ast)

def type(mod):
	ti.typer(mod)

def spec(mod):
	specialize.specialize(mod)

def generate(mod):
	triple = 'target triple = "%s"\n\n' % TRIPLES[sys.platform]
	return triple + codegen.source(mod)

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
