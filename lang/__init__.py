from . import tokenizer, ast, blocks, ti, specialize, codegen
from util import Error
import sys, os, subprocess, tempfile

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
	with open('core/rt.ll') as f:
		rt = f.read()
	return triple + rt + '\n' + codegen.source(mod)

def compile(ir, outfn):
	
	fd, name = tempfile.mkstemp('.ll', dir='.')
	f = os.fdopen(fd, 'wb')
	f.write(ir)
	f.close()
	
	subprocess.check_call(('clang', '-o', outfn, name))
	os.unlink(f.name)
