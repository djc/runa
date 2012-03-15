import sys, tokenizer

# Base class

IGNORE = {'p', 'ln'}

class Node(object):
	def __init__(self, ln):
		self.ln = ln
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents if k not in IGNORE)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	def __hash__(self):
		values = tuple(sorted((k, v) for (k, v) in self.__dict__.iteritems()))
		return hash((self.__class__.__name__,) + values)

# Expression-level

class Terminal(Node):
	lbp = 0
	def nud(self, p):
		return self

class Statement(Node):
	lbp = 0

class Name(Terminal):
	def __init__(self, name, ln):
		Node.__init__(self, ln)
		self.name = name

class Int(Terminal):
	def __init__(self, num, ln):
		Node.__init__(self, ln)
		self.val = num

class End(Terminal):
	op = 'end'

class String(Terminal):
	def __init__(self, value, ln):
		Node.__init__(self, ln)
		self.value = value

class BinaryOp(Node):
	def led(self, p, left):
		self.left = left
		self.right = p.expr(self.lbp)
		return self

class RightPar(Terminal):
	op = ')'

class Elem(BinaryOp):
	
	op = '['
	lbp = 16
	fields = 'obj', 'key'
	
	def led(self, p, left):
		self.obj = left
		self.key = p.expr()
		p.advance(ElemEnd)
		return self

class ElemEnd(Terminal):
	op = ']'

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
	lbp = 5
	fields = 'left', 'right'

class And(BinaryOp):
	op = 'and'
	lbp = 40
	fields = 'left', 'right'

class Or(BinaryOp):
	op = 'or'
	lbp = 40
	fields = 'left', 'right'

class Colon(Terminal):
	op = ':'
	fields = 'left', 'right'

class Comma(Terminal):
	op = ','
	lbp = 0

class RType(Terminal):
	op = '->'

class Indent(Terminal):
	pass

class Dedent(Terminal):
	pass

class NL(Terminal):
	pass

class Comment(Terminal):
	op = '#'
	fields = ()
	def nud(self, p):
		while not isinstance(p.token, NL):
			p.advance()
		p.advance(NL)
		return self

class Call(BinaryOp, Node):
	
	op = '('
	lbp = 70
	fields = ('args',)
	
	def led(self, p, left):
		
		self.name = left
		self.args = []
		
		next = p.expr()
		while isinstance(p.token, Comma):
			self.args.append(next)
			p.advance(Comma)
			next = p.expr()
		
		self.args.append(next)
		p.advance(RightPar)
		return self
	
	def nud(self, p):
		expr = p.expr()
		p.token = p.next()
		return expr

class Suite(Node):
	
	fields = 'stmts',
	
	def advance(self):
		while isinstance(self.p.token, NL):
			self.p.advance()
	
	def __init__(self, p, ln):
		
		Node.__init__(self, ln)
		self.p = p
		self.stmts = []
		
		self.advance()
		p.advance(Indent)
		self.advance()
		
		while True:
			self.stmts.append(p.expr())
			self.advance()
			if isinstance(p.token, Dedent):
				break
		
		p.advance(Dedent)

class Argument(Node):
	fields = 'name',
	def __init__(self, ln):
		Node.__init__(self, ln)
		self.name = None
		self.type = None

class Function(Node):
	
	lbp = 0
	fields = 'name', 'args', 'rtype', 'suite'
	
	def nud(self, p):
		
		self.name = p.advance(Name)
		p.advance(Call)
		
		cur = Argument(self.ln)
		self.args = []
		next = p.expr()
		if not isinstance(next, RightPar):
			while p.token.__class__ in (Comma, Colon):
				
				if isinstance(p.token, Colon):
					cur.name = next
					p.advance(Colon)
				else:
					cur.type = next
					self.args.append(cur)
					cur = Argument(self.ln)
					p.advance(Comma)
				
				next = p.expr()
		
		if not isinstance(next, RightPar):
			cur.type = next
			self.args.append(cur)
			p.advance(RightPar)
		
		self.rtype = None
		if isinstance(p.token, RType):
			p.advance(RType)
			self.rtype = p.expr()
		
		p.advance(Colon)
		self.suite = Suite(p, self.ln + 1)
		return self

class Return(Node):
	lbp = 0
	fields = 'value',
	def nud(self, p):
		self.value = p.expr()
		return self

class Ternary(Node):
	
	lbp = 10
	fields = 'cond', 'values'
	
	def __init__(self, p, left, ln):
		Node.__init__(self, ln)
		self.cond = None
		self.values = []
		self.values.append(left)
		self.cond = p.expr()
		p.advance(Else)
		self.values.append(p.expr())

class If(Statement):
	
	lbp = 10
	fields = 'blocks',
	
	def led(self, p, left):
		return Ternary(p, left, self.ln)
	
	def nud(self, p):
		
		cond = p.expr()
		p.advance(Colon)
		block = Suite(p, self.ln)
		self.blocks = [(cond, block)]
		
		while isinstance(p.token, Elif):
			kw = p.advance(Elif)
			cond = p.expr()
			p.advance(Colon)
			block = Suite(p, kw.ln)
			self.blocks.append((cond, block))
		
		if isinstance(p.token, Else):
			kw = p.advance(Else)
			p.advance(Colon)
			block = Suite(p, kw.ln)
			self.blocks.append((None, block))
		
		return self

class Elif(Node):
	lbp = 0
	def nud(self, p):
		return self

class Else(Node):
	lbp = 0
	def nud(self, p):
		return self

class For(Statement):
	fields = 'lvar', 'source', 'suite'
	def nud(self, p):
		self.lvar = p.advance(Name)
		p.advance(In)
		self.source = p.expr()
		p.advance(Colon)
		self.suite = Suite(p, self.ln)
		return self

class Not(Node):
	lbp = 0
	fields = 'value',
	def nud(self, p):
		self.value = p.expr()
		return self

class In(Node):
	lbp = 70
	fields = 'left', 'right'
	def nud(self, p):
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
	'{': Elem, # tmp
	'}': ElemEnd, # tmp
	'->': RType,
	'#': Comment,
	'not': Not,
	'and': And,
	'or': Or,
	'in': In,
}

KEYWORDS = {
	'def': Function,
	'return': Return,
	'if': If,
	'elif': Elif,
	'else': Else,
	'for': For,
}

class Pratt(object):
	
	def __init__(self, tokens):
		self.next = self.wrap(tokens).next
		self.token = self.next()
	
	def wrap(self, tokens):
		for t, v, ln in tokens:
			if t == 'name':
				yield Name(v, ln)
			elif t == 'num' and '.' not in v:
				yield Int(v, ln)
			elif t == 'kw':
				yield KEYWORDS[v](ln)
			elif t == 'str':
				yield String(v, ln)
			elif t == 'op':
				yield OPERATORS[v](ln)
			elif t == 'indent' and v > 0:
				yield Indent(ln)
			elif t == 'indent' and v < 0:
				yield Dedent(ln)
			elif t == 'nl':
				yield NL(ln)
		yield End(ln)
	
	def advance(self, id=None):
		if id and not isinstance(self.token, id):
			raise Exception('expected %r, got %r' % (id, self.token))
		t = self.token
		self.token = self.next()
		return t
	
	def expr(self, rbp=0):
		t, self.token = self.token, self.next()
		left = t.nud(self)
		while rbp < self.token.lbp and not isinstance(left, Statement):
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
	p = Pratt(tokens)
	
	mod = Module()
	while not isinstance(p.token, End):
		mod.suite.append(p.expr())
	
	return mod

if __name__ == '__main__':
	print fromfile(sys.argv[1])
