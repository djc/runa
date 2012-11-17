#!/usr/bin/env python

import runac
import optparse, sys, os, subprocess

def tokens(fn, opts):
	for x in runac.tokenize(open(fn)):
		print x

def parse(fn, opts):
	print runac.parse(runac.tokenize(open(fn)))

def bl(fn, opts):
	return runac.module(runac.parse(runac.tokenize(open(fn))))

def ti(fn, opts):
	mod = bl(fn, opts)
	runac.type(mod)

def specialize(fn, opts):
	mod = bl(fn, opts)
	runac.type(mod)
	runac.spec(mod)

def generate(fn, opts):
	mod = bl(fn, opts)
	runac.type(mod)
	runac.spec(mod)
	print runac.generate(mod)

def compile(fn, opts):
	mod = bl(fn, opts)
	runac.type(mod)
	runac.spec(mod)
	ir = runac.generate(mod)
	runac.compile(ir, os.path.basename(fn).rsplit('.rns')[0])

def run(fn, opts):
	kwargs = {i: subprocess.PIPE for i in ('stdin', 'stdout', 'stderr')}
	proc = subprocess.Popen(('lli',), **kwargs)
	out, err = proc.communicate(runac.llir(fn, True))
	sys.stdout.write(out)
	sys.stderr.write(err)

COMMANDS = {
	'tokens': tokens,
	'parse': parse,
	'blocks': bl,
	'ti': ti,
	'specialize': specialize,
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
	except runac.Error as e:
		sys.stderr.write(e.show(args[1]))
