import sys, parser, codegen, os

def llir(fn):
	return codegen.source(parser.fromfile(fn))

def compile(fn):
	
	llfn = fn + '.ll'
	with open(llfn, 'w') as f:
		f.write(llir(fn))
	
	cmd = 'llvmc', '-o', fn.rsplit('.', 1)[0], llfn
	proc = os.popen(' '.join(cmd))
	proc.read()
	os.unlink(llfn)

if __name__ == '__main__':
	compile(sys.argv[1])
