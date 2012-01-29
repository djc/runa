import sys, parser, codegen, subprocess, os

def llir(fn):
	return codegen.source(parser.fromfile(fn))

def compile(fn):
	
	llfn = fn + '.ll'
	with open(llfn, 'w') as f:
		f.write(llir(fn))
	
	cmd = 'clang', '-o', fn.rsplit('.', 1)[0], llfn
	subprocess.check_call(cmd)
	os.unlink(llfn)

if __name__ == '__main__':
	compile(sys.argv[1])
