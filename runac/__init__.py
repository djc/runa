from util import Error
import os, subprocess

from .tokenizer import tokenize
from .ast import parse
from .blocks import module
from .ti import typer
from .specialize import specialize
from .codegen import generate

BASE = os.path.dirname(__path__[0])
CORE_DIR = os.path.join(BASE, 'core')

def merge(mod):
	for fn in os.listdir(CORE_DIR):
		if not fn.endswith('.rns'): continue
		with open(os.path.join(CORE_DIR, fn)) as f:
			mod.merge(module(parse(tokenize(f))))

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
		merge(mod)
		typer(mod)
		specialize(mod)
		compile(generate(mod), outfn)
