#!/usr/bin/env python

from lang import tokenizer, ast, flow, codegen
import lang
import optparse, sys, os
	
def tokens(fn, opts):
	for x in tokenizer.tokenize(open(fn)):
		print x

def parse(fn, opts):
	print ast.parse(tokenizer.tokenize(open(fn)))

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
	try:
		print lang.llir(fn, opts.full)
	except lang.Error as e:
		sys.stderr.write(e.show(fn))

def compile(fn, opts):
	lang.compile(fn, os.path.basename(fn).rsplit('.lng')[0])

COMMANDS = {
	'tokens': tokens,
	'parse': parse,
	'flow': cfg,
	'generate': generate,
	'compile': compile,
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
	find(args[0])(args[1], opts)
