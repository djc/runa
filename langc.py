#!/usr/bin/env python

from lang import tokenizer, ast, typer, codegen, blocks
import lang
import optparse, sys, os, subprocess

def tokens(fn, opts):
	for x in tokenizer.tokenize(open(fn)):
		print x

def parse(fn, opts):
	print ast.parse(tokenizer.tokenize(open(fn)))

def bl(fn, opts):
	mod = blocks.Module(ast.parse(tokenizer.tokenize(open(fn))))
	for k, obj in sorted(mod.code.iteritems()):
		print 'START', k
		print 'FLOW', obj.flow
		print
		print
	return mod

def ti(fn, opts):
	node = ast.parse(tokenizer.tokenize(open(fn)))
	mod = typer.Module(node)

def cfg(fn, opts):
	node = ast.parse(tokenizer.tokenize(open(fn)))
	mod = flow.Module(node)
	for name, fun in mod.functions.iteritems():
		if fun.rt: continue
		print 'GRAPH', name
		for i, block in enumerate(fun.graph):
			print '%02i' % i, [i.id for i in block.preds]
			for step in block.steps:
				print ' ', step
				pass

def generate(fn, opts):
	print lang.llir(fn, opts.full)

def compile(fn, opts):
	lang.compile(fn, os.path.basename(fn).rsplit('.lng')[0])

def run(fn, opts):
	kwargs = {i: subprocess.PIPE for i in ('stdin', 'stdout', 'stderr')}
	proc = subprocess.Popen(('lli',), **kwargs)
	out, err = proc.communicate(lang.llir(fn, True))
	sys.stdout.write(out)
	sys.stderr.write(err)

COMMANDS = {
	'tokens': tokens,
	'parse': parse,
	'blocks': bl,
	'ti': ti,
	'flow': cfg,
	'generate': generate,
	'compile': compile,
	'run': run,
}

def find(cmd):
	if cmd in COMMANDS: return COMMANDS[cmd]
	matched = sorted(i for i in COMMANDS if i.startswith(cmd))
	if len(matched) == 1:
		return COMMANDS[matched[0]]
	elif len(matched) > 1:
		print 'ambiguous command: %r' % cmd
		return lambda x, y: None
	else:
		print 'no command found: %r' % cmd
		return lambda x, y: None

if __name__ == '__main__':
	parser = optparse.OptionParser(description='the lang utility')
	parser.add_option('--full', help='include stdlib', action='store_true')
	opts, args = parser.parse_args()
	try:
		find(args[0])(args[1], opts)
	except lang.Error as e:
		sys.stderr.write(e.show(args[1]))
