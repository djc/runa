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
		
		if not fn.endswith('.rns'):
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
	
	name = outfn + '.ll'
	with open(name, 'wb') as f:
		f.write(ir)
	
	try:
		subprocess.check_call(('clang', '-o', outfn, name))
	except OSError as e:
		if e.errno == 2:
			print 'error: clang not found'
	except subprocess.CalledProcessError:
		pass
	finally:
		os.unlink(name)

def full(fn, outfn):
	with open(fn) as f:
		mod = module(parse(tokenize(f)))
		type(mod)
		spec(mod)
		compile(generate(mod), outfn)
