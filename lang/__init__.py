from . import tokenizer, ast, codegen
import os, subprocess

def llir(fn, inline=None):
	return codegen.source(ast.parse(tokenizer.tokenize(open(fn))), inline)

def compile(fn, outfn):
	
	llfn = fn + '.ll'
	with open(llfn, 'w') as f:
		f.write(llir(fn))
	
	subprocess.check_call(('clang', '-o', outfn, 'std.ll', llfn))
	os.unlink(llfn)
