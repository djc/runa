import sys, tokenizer

# Base class

class Node(object):
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	def __hash__(self):
		values = tuple(sorted((k, v) for (k, v) in self.__dict__.iteritems()))
		return hash((self.__class__.__name__,) + values)

# Expression-level

class Name(Node):
	lbp = 0
	def __init__(self, name):
		self.name = name
	def nud(self, parser):
		return self

class Int(Node):
	lbp = 0
	def __init__(self, num):
		self.val = num
	def nud(self, parser):
		return self

class End(Node):
	op = 'end'
	lbp = 0

class String(Node):
	op = 'str'
	lbp = 0
	def __init__(self, value):
		self.value = value
	def nud(self, parser):
		return self

class BinaryOp(Node):
	def led(self, parser, left):
		self.left = left
		self.right = parser.expr(self.lbp)
		return self

class RightPar(Node):
	op = ')'
	lbp = 0
	def nud(self, parser):
		return self

class Elem(BinaryOp):
	
	op = '['
	lbp = 16
	fields = 'obj', 'elem'
	
	def led(self, parser, left):
		self.obj = left
		self.elem = parser.expr()
		parser.advance(ElemEnd)
		return self

class ElemEnd(Node):
	op = ']'
	lbp = 0

class Add(BinaryOp):
	op = '+'
	lbp = 50
	fields = 'left', 'right'

class Sub(BinaryOp):
	op = '-'
	lbp = 50
	fields = 'left', 'right'

class Mul(BinaryOp):
	op = '*'
	lbp = 60
	fields = 'left', 'right'

class Div(BinaryOp):
	op = '/'
	lbp = 60
	fields = 'left', 'right'

class Assign(BinaryOp):
	op = '='
	lbp = 10
	fields = 'left', 'right'

class Colon(Node):
	op = ':'
	lbp = 0
	fields = 'left', 'right'
	def nud(self, parser):
		return self

class Comma(BinaryOp):
	op = ','
	lbp = 0

class RType(Node):
	op = '->'
	lbp = 0
	def nud(self, parser):
		return self

class Indent(Node):
	lbp = 0
	def nud(self, parser):
		return self

class Dedent(Node):
	lbp = 0
	def nud(self, parser):
		return self

class NL(Node):
	lbp = 0
	def nud(self, parser):
		return self

class Call(BinaryOp, Node):
	
	op = '('
	lbp = 70
	fields = ('args',)
	
	def led(self, parser, left):
		
		self.name = left
		self.args = []
		
		next = parser.expr()
		while isinstance(parser.token, Comma):
			self.args.append(next)
			parser.advance(Comma)
			next = parser.expr()
		
		self.args.append(next)
		parser.advance(RightPar)
		return self
	
	def nud(self, parser):
		expr = parser.expr()
		parser.token = parser.next()
		return expr

class Suite(Node):
	
	fields = 'stmts',
	
	def advance(self):
		while isinstance(self.parser.token, NL):
			self.parser.advance()
	
	def __init__(self, parser):
		
		self.parser = parser
		self.stmts = []
		
		self.advance()
		parser.advance(Indent)
		self.advance()
		
		while True:
			self.stmts.append(parser.expr())
			self.advance()
			if isinstance(parser.token, Dedent):
				break
		
		parser.advance(Dedent)

class Argument(Node):
	fields = 'name',
	def __init__(self):
		self.name = None
		self.type = None

class Function(Node):
	
	lbp = 0
	fields = 'name', 'args', 'rtype', 'suite'
	
	def nud(self, parser):
		
		self.name = parser.advance(Name)
		parser.advance(Call)
		
		cur = Argument()
		self.args = []
		next = parser.expr()
		if not isinstance(next, RightPar):
			while parser.token.__class__ in (Comma, Colon):
				
				if isinstance(parser.token, Colon):
					cur.name = next
					parser.advance(Colon)
				else:
					cur.type = next
					self.args.append(cur)
					parser.advance(Comma)
				
				next = parser.expr()
		
		if not isinstance(next, RightPar):
			cur.type = next
			self.args.append(cur)
			parser.advance(RightPar)
		
		self.rtype = None
		if isinstance(parser.token, RType):
			parser.advance(RType)
			self.rtype = parser.expr()
		
		parser.advance(Colon)
		self.suite = Suite(parser)
		return self

OPERATORS = {
	'(': Call,
	')': RightPar,
	'+': Add,
	'-': Sub,
	'*': Mul,
	'/': Div,
	'=': Assign,
	',': Comma,
	':': Colon,
	'[': Elem,
	']': ElemEnd,
	'->': RType,
}

class Pratt(object):
	
	def __init__(self, tokens):
		self.next = self.wrap(tokens).next
		self.token = self.next()
	
	def wrap(self, tokens):
		for t, v in tokens:
			if t == 'name':
				yield Name(v)
			elif t == 'num' and '.' not in v:
				yield Int(v)
			elif t == 'kw':
				yield Function()
			elif t == 'str':
				yield String(v)
			elif t == 'op':
				yield OPERATORS[v]()
			elif t == 'indent' and v > 0:
				yield Indent()
			elif t == 'indent' and v < 0:
				yield Dedent()
			elif t == 'nl':
				yield NL()
		yield End()
	
	def advance(self, id=None):
		if id and not isinstance(self.token, id):
			raise Exception('expected %r' % id)
		t = self.token
		self.token = self.next()
		return t
	
	def expr(self, rbp=0):
		t, self.token = self.token, self.next()
		left = t.nud(self)
		while rbp < self.token.lbp:
			t, self.token = self.token, self.next()
			left = t.led(self, left)
		return left

class Module(Node):
	fields = 'suite',
	def __init__(self):
		self.suite = []

def fromfile(fn):
	
	src = open(fn).read()
	tokens = tokenizer.indented(tokenizer.tokenize(src))
	parser = Pratt(tokens)
	
	mod = Module()
	while not isinstance(parser.token, End):
		mod.suite.append(parser.expr())
	
	return mod

if __name__ == '__main__':
	print fromfile(sys.argv[1])
