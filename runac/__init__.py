from . import (
	parser, blocks, liveness, typer, specialize,
	escapes, destructor, codegen, util, pretty
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

def show(fn, last):
	
	mod = blocks.module(parser.parse(fn))
	names = [name for (name, code) in mod.code]
	
	merge(mod)
	for name, fun in PASSES.iteritems():
		fun(mod)
		if name == last:
			break
	
	data = {}
	for name, code in mod.code:
		if name not in names:
			continue
		data[name] = pretty.prettify(name, code)
	
	return data

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
