# Base class

IGNORE = {'p', 'pos'}

class Registry(type):
	types = []
	def __init__(cls, name, bases, dict):
		Registry.types.append(cls)

class Node(object):
	__metaclass__ = Registry
	def __init__(self, pos):
		self.pos = pos
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents if k not in IGNORE)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	def __hash__(self):
		values = tuple(sorted((k, v) for (k, v) in self.__dict__.iteritems()))
		return hash((self.__class__.__name__,) + values)

# Terminals

class Terminal(Node):
	lbp = 0
	def nud(self, p):
		return self

class End(Terminal):
	pass

class RightPar(Terminal):
	op = ')'

class ElemEnd(Terminal):
	op = ']'

class Colon(Terminal):
	op = ':'

class Comma(Terminal):
	op = ','

class RType(Terminal):
	op = '->'

class Indent(Terminal):
	pass

class Dedent(Terminal):
	pass

class NL(Terminal):
	pass

class Bool(Terminal):
	def __init__(self, val, pos):
		Node.__init__(self, pos)
		self.val = True if val == 'True' else False

class Name(Terminal):
	def __init__(self, name, pos):
		Node.__init__(self, pos)
		self.name = name

class Int(Terminal):
	def __init__(self, num, pos):
		Node.__init__(self, pos)
		self.val = num

class Float(Terminal):
	def __init__(self, num, pos):
		Node.__init__(self, pos)
		self.val = num

class String(Terminal):
	def __init__(self, value, pos):
		Node.__init__(self, pos)
		self.value = value

# Expression-level

class BinaryOp(Node):
	def led(self, p, left):
		self.left = left
		self.right = p.expr(self.lbp)
		return self

class Elem(BinaryOp):
	
	op = '['
	lbp = 16
	fields = 'obj', 'key'
	
	def led(self, p, left):
		self.obj = left
		self.key = p.expr()
		p.advance(ElemEnd)
		return self

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

class Not(Node):
	op = 'not'
	lbp = 0
	fields = 'value',
	def nud(self, p):
		self.value = p.expr()
		return self

class In(Node):
	op = 'in'
	lbp = 70
	fields = 'left', 'right'
	def nud(self, p):
		return self

class And(BinaryOp):
	op = 'and'
	lbp = 40
	fields = 'left', 'right'

class Or(BinaryOp):
	op = 'or'
	lbp = 40
	fields = 'left', 'right'

class Eq(BinaryOp):
	op = '=='
	lbp = 20
	fields = 'left', 'right'

class NEq(BinaryOp):
	op = '!='
	lbp = 20
	fields = 'left', 'right'

class LT(BinaryOp):
	op = '<'
	lbp = 20
	fields = 'left', 'right'

class Call(BinaryOp):
	
	op = '('
	lbp = 70
	fields = ('args',)
	
	def led(self, p, left):
		
		self.name = left
		self.args = []
		if isinstance(p.token, RightPar):
			p.advance(RightPar)
			return self
		
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

# Statement-level

class Statement(Node):
	lbp = 0

class Suite(Node):
	
	fields = 'stmts',
	
	def advance(self):
		while isinstance(self.p.token, NL):
			self.p.advance()
	
	def __init__(self, p, pos):
		
		Node.__init__(self, pos)
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
	def __init__(self, pos):
		Node.__init__(self, pos)
		self.name = None
		self.type = None

class Function(Node):
	
	kw = 'def'
	lbp = 0
	fields = 'name', 'args', 'rtype', 'suite'
	
	def nud(self, p):
		
		self.name = p.advance(Name)
		p.advance(Call)
		
		cur = Argument(self.pos)
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
					cur = Argument(self.pos)
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
		self.suite = Suite(p, self.pos)
		return self

class Return(Node):
	
	kw = 'return'
	lbp = 0
	fields = 'value',
	
	def nud(self, p):
		self.value = p.expr()
		return self

class Ternary(Node):
	
	lbp = 10
	fields = 'cond', 'values'
	
	def __init__(self, p, left, pos):
		Node.__init__(self, pos)
		self.cond = None
		self.values = []
		self.values.append(left)
		self.cond = p.expr()
		p.advance(Else)
		self.values.append(p.expr())

class If(Statement):
	
	kw = 'if'
	lbp = 10
	fields = 'blocks',
	
	def led(self, p, left):
		return Ternary(p, left, self.pos)
	
	def nud(self, p):
		
		cond = p.expr()
		p.advance(Colon)
		block = Suite(p, self.pos)
		self.blocks = [(cond, block)]
		
		while isinstance(p.token, Elif):
			kw = p.advance(Elif)
			cond = p.expr()
			p.advance(Colon)
			block = Suite(p, kw.pos)
			self.blocks.append((cond, block))
		
		if isinstance(p.token, Else):
			kw = p.advance(Else)
			p.advance(Colon)
			block = Suite(p, kw.pos)
			self.blocks.append((None, block))
		
		return self

class Elif(Node):
	kw = 'elif'
	lbp = 0
	def nud(self, p):
		return self

class Else(Node):
	kw = 'else'
	lbp = 0
	def nud(self, p):
		return self

class For(Statement):
	kw = 'for'
	fields = 'lvar', 'source', 'suite'
	def nud(self, p):
		self.lvar = p.advance(Name)
		p.advance(In)
		self.source = p.expr()
		p.advance(Colon)
		self.suite = Suite(p, self.pos)
		return self

class While(Statement):
	kw = 'while'
	fields = 'cond', 'suite'
	def nud(self, p):
		self.cond = p.expr()
		p.advance(Colon)
		self.suite = Suite(p, self.pos)
		return self

# The core of the parsing algorithm

OPERATORS = {cls.op: cls for cls in Registry.types if hasattr(cls, 'op')}
KEYWORDS = {cls.kw: cls for cls in Registry.types if hasattr(cls, 'kw')}

class Pratt(object):
	
	def __init__(self, tokens):
		self.next = self.wrap(tokens).next
		self.token = self.next()
	
	def wrap(self, tokens):
		for t, v, s, e in tokens:
			if t == 'name' and v in {'True', 'False'}:
				yield Bool(v, (s, e))
			elif t == 'name':
				yield Name(v, (s, e))
			elif t == 'num' and '.' not in v:
				yield Int(v, (s, e))
			elif t == 'num' and '.' in v:
				yield Float(v, (s, e))
			elif t == 'kw':
				yield KEYWORDS[v]((s, e))
			elif t == 'str':
				yield String(v, (s, e))
			elif t == 'op':
				yield OPERATORS[v]((s, e))
			elif t == 'indent' and v > 0:
				yield Indent((s, e))
			elif t == 'indent' and v < 0:
				yield Dedent((s, e))
			elif t == 'nl':
				yield NL((s, e))
			elif t == 'com':
				continue
		yield End((s, e))
	
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

def parse(tokens):
	mod = Module()
	p = Pratt(tokens)
	while not isinstance(p.token, End):
		mod.suite.append(p.expr())
	return mod
