import sys, tokenizer, ast

class Buffer(object):
	def __init__(self, gen):
		self.next = None
		self.gen = gen
	def __iter__(self):
		return self
	def peek(self):
		if self.next is None:
			self.next = next(self.gen)
		return self.next
	def push(self, val):
		self.next = val
	def next(self):
		if self.next is not None:
			tmp = self.next
			self.next = None
			return tmp
		else:
			return next(self.gen)

def fromfile(fn):
	src = open(fn).read()
	tokens = tokenizer.indented(tokenizer.tokenize(src))
	return ast.Module.parse(Buffer(tokens))

if __name__ == '__main__':
	print fromfile(sys.argv[1])
