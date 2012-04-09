#!/usr/bin/env python

from lang import tokenizer, ast, codegen
import lang
import optparse, sys, subprocess, os
	
def tokens(fn, opts):
	for x in tokenizer.tokenize(open(fn)):
		print x

def parse(fn, opts):
	print ast.parse(tokenizer.tokenize(open(fn)))

def generate(fn, opts):
	try:
		print lang.llir(fn, opts.full)
	except codegen.Error as e:
		print e.show(fn)

def compile(fn, opts):
	lang.compile(fn, os.path.basename(fn).rsplit('.lng')[0])

COMMANDS = {
	'tokens': tokens,
	'parse': parse,
	'generate': generate,
	'compile': compile,
}

def find(cmd):
	if cmd in COMMANDS: return COMMANDS[cmd]
	full = set(COMMANDS)
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
