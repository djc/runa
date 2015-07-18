from __future__ import print_function
from . import (
	parser, blocks, liveness, typer, specialize,
	escapes, destructor, codegen, util, pretty
)
import os, subprocess, collections, re

PASSES = collections.OrderedDict((
	('liveness', liveness.liveness),
	('typer', typer.typer),
	('specialize', specialize.specialize),
	('escapes', escapes.escapes),
	('destruct', destructor.destruct),
))

def lex(src):
	'''Takes a string containing source code, returns list of token tuples'''
	return parser.lex(src)

def parse(fn):
	'''Takes a string containing file name, returns an AST File node'''
	return parser.parse(fn)

def _core():
	fn = os.path.join(util.CORE_DIR, '__builtins__.rns')
	base = {t.__name__: t() for t in types.BASE}
	mod = blocks.Module('Runa.core', parse(fn), base)
	for name, fun in util.items(PASSES):
		fun(mod)
	return mod

CORE = _core()

def module(path, name='Runa.__main__'):
	'''Takes a file (or directory, at some point), returns a Module containing
	declarations and code objects, to be submitted for further processing.'''
	assert not os.path.isdir(path), path
	return blocks.Module(name, parser.parse(path), CORE.scope)

def show(fn, last):
	'''Show Runa high-level intermediate representation for the source code
	in the given file name (`fn`). `last` contains the last pass from
	PASSES to apply to the module before generating the IR.
	
	Returns a dict with function names (string or tuple) -> IR (string).
	Functions from modules other than the given module are ignored.'''
	
	mod = module(fn)
	for name, fun in util.items(PASSES):
		fun(mod)
		if name == last:
			break
	
	data = []
	for name, code in mod.code:
		data.append(pretty.prettify(name, code))
	
	return data

def ir(fn):
	'''Generate LLVM IR for the given module. Takes a string file name and
	returns a string of LLVM IR, for the host architecture.'''
	mod = module(fn)
	for name, fun in util.items(PASSES):
		fun(mod)
	return codegen.generate(mod)

CORE_IR = codegen.generate(CORE)
RT_IR = codegen.rt()

def compile(fn, outfn):
	'''Compiles LLVM IR into a binary. Takes a string file name and a string
	output file name. Writes the IR to a temporary file, then calls clang on
	it. (Shelling out to clang is pretty inefficient.)'''
	
	with open('builtins.ll', 'w') as f:
		f.write(CORE_IR.encode('ascii'))
	
	name = os.path.basename(fn).rsplit('.rns')[0]
	mod_fn = name + '.ll'
	with open(mod_fn, 'w') as f:
		try:
			f.write(ir(fn).encode('ascii'))
		except Exception:
			os.unlink(mod_fn)
			raise
	
	with open('rt.ll', 'w') as f:
		f.write(RT_IR)

	eh_fn = os.path.join(util.CORE_DIR, 'personality.ll')
	files = eh_fn, 'rt.ll', 'builtins.ll', mod_fn
	triple = codegen.triple()
	if 'windows-msvc' in triple:
		cmd = ['clang-cl', '-Fe' + outfn, '-m64'] + files
		cmd += ['/link', 'msvcrt.lib']
	else:
		cmd = ['clang', '-o', outfn]
		cmd.append('-m64' if triple.split('-')[0] == 'x86_64' else '-m32')
		cmd += files
	
	try:
		subprocess.check_call(cmd)
	except OSError as e:
		if e.errno == 2:
			print('error: clang not found')
		else:
			raise
	except subprocess.CalledProcessError:
		pass
	finally:
		os.unlink('rt.ll')
		os.unlink('builtins.ll')
		os.unlink(mod_fn)
