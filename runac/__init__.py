from . import (
	parser, blocks, liveness, typer, specialize,
	escapes, destructor, codegen, util,
)
import os, subprocess, collections

PASSES = collections.OrderedDict((
	('liveness', liveness.liveness),
	('typer', typer.typer),
	('specialize', specialize.specialize),
	('escapes', escapes.escapes),
	('destruct', destructor.destruct),
))

def lex(f):
	return parser.lex(f)

def parse(fn):
	return parser.parse(fn)

def merge(mod):
	for fn in os.listdir(util.CORE_DIR):
		if not fn.endswith('.rns'): continue
		fn = os.path.join(util.CORE_DIR, fn)
		mod.merge(blocks.module(parser.parse(fn)))

def ir(fn):
	mod = blocks.module(parser.parse(fn))
	merge(mod)
	for name, fun in PASSES.iteritems():
		fun(mod)
	return codegen.generate(mod)

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
