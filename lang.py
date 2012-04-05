import tokenizer, ast, codegen
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

if __name__ == '__main__':
	parser = optparse.OptionParser(description='the lang utility')
	parser.add_option('--inline', help='inline stdlib', action='store_true')
	opts, args = parser.parse_args()
	COMMANDS[args[0]](args[1], opts)
