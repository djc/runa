#!/usr/bin/env python
from lang import tokenizer, ast, codegen
import optparse, sys, subprocess, os

def llir(fn, inline=None):
	return codegen.source(ast.parse(tokenizer.tokenize(open(fn))), inline)

def compile(fn, opts=None, outfn=None):
	
	llfn = fn + '.ll'
	with open(llfn, 'w') as f:
		f.write(llir(fn))
	
	outfn = outfn if outfn else fn.rsplit('.', 1)[0]
	subprocess.check_call(('clang', '-o', outfn, 'std.ll', llfn))
	os.unlink(llfn)
	
def tokens(fn, opts):
	for x in tokenizer.tokenize(open(fn)):
		print x

def parse(fn, opts):
	print ast.parse(tokenizer.tokenize(open(fn)))

def generate(fn, opts):
	print llir(fn, opts.inline)

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
	parser.add_option('--inline', help='inline stdlib', action='store_true')
	opts, args = parser.parse_args()
	find(args[0])(args[1], opts)
