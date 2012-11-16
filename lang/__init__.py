from . import tokenizer, ast, blocks, ti, specialize, codegen
from util import Error
import sys, os, subprocess, tempfile

BASE = os.path.dirname(__path__[0])
CORE_DIR = os.path.join(BASE, 'core')

TRIPLES = {
	'darwin': 'x86_64-apple-darwin11.0.0',
	'linux2': 'x86_64-pc-linux-gnu',
}

def tokenize(f):
	return tokenizer.tokenize(f)

def parse(tokens):
	return ast.parse(tokens)

def module(ast):
	
	mod = blocks.Module(ast)
	for fn in os.listdir(CORE_DIR):
		
		if not fn.endswith('.lng'):
			continue
		
		with open(os.path.join(CORE_DIR, fn)) as f:
			mod.merge(blocks.Module(parse(tokenize(f))))
	
	return mod

def type(mod):
	ti.typer(mod)

def spec(mod):
	specialize.specialize(mod)

def generate(mod):
	triple = 'target triple = "%s"\n\n' % TRIPLES[sys.platform]
	with open('core/rt.ll') as f:
		rt = f.read()
	return triple + rt + '\n' + codegen.source(mod)

def compile(ir, outfn):
	
	fd, name = tempfile.mkstemp('.ll', dir='.')
	f = os.fdopen(fd, 'wb')
	f.write(ir)
	f.close()
	
	try:
		subprocess.check_call(('clang', '-o', outfn, name))
	except Exception:
		pass
	finally:
		os.unlink(name)
