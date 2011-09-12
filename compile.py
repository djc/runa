import sys, tokenizer, parser, ast, codegen, os

def llir(fn):
	src = open(fn).read()
	tokens = tokenizer.indented(tokenizer.tokenize(src))
	mod = ast.Module.parse(parser.Buffer(tokens))
	return codegen.source(mod)

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
