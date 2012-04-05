import ast, codegen
import sys, subprocess, os

def llir(fn):
	return codegen.source(ast.fromfile(fn))

def compile(fn, outfn=None):
	
	llfn = fn + '.ll'
	with open(llfn, 'w') as f:
		f.write(llir(fn))
	
	outfn = outfn if outfn else fn.rsplit('.', 1)[0]
	subprocess.check_call(('clang', '-o', outfn, 'std.ll', llfn))
	os.unlink(llfn)

COMMANDS = {
	'compile': compile,
}

if __name__ == '__main__':
	cmd = sys.argv[1]
	COMMANDS[cmd](*sys.argv[2:])
