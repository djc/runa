import sys, parser, codegen, subprocess, os

def llir(fn):
	return codegen.source(parser.fromfile(fn))

def compile(fn, outfn=None):
	
	llfn = fn + '.ll'
	with open(llfn, 'w') as f:
		f.write(llir(fn))
	
	outfn = outfn if outfn else fn.rsplit('.', 1)[0]
	subprocess.check_call(('clang', '-o', outfn, llfn))
	os.unlink(llfn)

if __name__ == '__main__':
	compile(sys.argv[1])
