#!/usr/bin/env python

import lang
import optparse, sys, os, subprocess

def tokens(fn, opts):
	for x in lang.tokenize(open(fn)):
		print x

def parse(fn, opts):
	print lang.parse(lang.tokenize(open(fn)))

def bl(fn, opts):
	mod = lang.module(lang.parse(lang.tokenize(open(fn))))
	#for k, obj in sorted(mod.code.iteritems()):
	#	print 'START', k
	#	print 'FLOW', obj.flow
	#	print
	#	print
	return mod

def ti(fn, opts):
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
