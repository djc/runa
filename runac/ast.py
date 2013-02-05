import util

# Base class

IGNORE = {'pos'}

class Registry(type):
	types = []
	def __init__(cls, name, bases, dict):
		Registry.types.append(cls)

class Node(util.AttribRepr):
	__metaclass__ = Registry
	def __init__(self, pos):
		self.pos = pos
	def __hash__(self):
		values = tuple(sorted((k, v) for (k, v) in self.__dict__.iteritems()))
		return hash((self.__class__.__name__,) + values)

class Expr(Node):
	fields = ()
	def __init__(self, pos):
		Node.__init__(self, pos)
		self.type = None
		self.escapes = False

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

class Bool(Expr, Terminal):
	def __init__(self, val, pos):
		Expr.__init__(self, pos)
		self.val = True if val == 'True' else False

class Int(Expr, Terminal):
	def __init__(self, num, pos):
		Expr.__init__(self, pos)
		self.val = num

class Float(Expr, Terminal):
	def __init__(self, num, pos):
		Expr.__init__(self, pos)
		self.val = num

class String(Expr, Terminal):
	def __init__(self, value, pos):
		Expr.__init__(self, pos)
		self.val = value

class Name(Expr, Terminal):
	def __init__(self, name, pos):
		Expr.__init__(self, pos)
		self.name = name

# Expression-level

class BinaryOp(Expr):
	def led(self, p, left):
		self.left = left
		self.right = p.expr(self.lbp)
		return self

class Attrib(BinaryOp):
	
	op = '.'
	lbp = 100
	fields = 'obj',
	
	def led(self, p, left):
		self.obj = left
		self.attrib = p.advance(Name).name
		return self

class Slice(Expr):
	fields = 'values',
	def __init__(self, pos, vals):
		self.values = vals

class Elem(BinaryOp):
	
	op = '['
	lbp = 16
	fields = 'obj', 'key'
	
	def led(self, p, left):
		
		values = []
		while not isinstance(p.token, ElemEnd):
			if isinstance(p.token, Colon):
				values.append(None)
				p.advance(Colon)
			else:
				values.append(p.expr())
				if isinstance(p.token, Colon):
					p.advance(Colon)
					if isinstance(p.token, ElemEnd):
						values.append(None)
		
		self.obj = left
		if len(values) > 1:
			self.key = Slice(left.pos, values)
		else:
			self.key = values[0]
		
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

class Not(Expr):
	op = 'not'
	lbp = 0
	fields = 'value',
	def nud(self, p):
		self.value = p.expr()
		return self

class Owner(Node):
	op = '$'
	lbp = 0
	fields = 'value'
	def nud(self, p):
		self.value = p.expr()
		return self

class Ref(Node):
	op = '&'
	lbp = 0
	fields = 'value'
	def nud(self, p):
		self.value = p.expr()
		return self

class In(Expr):
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

class As(BinaryOp):
	op = 'as'
	lbp = 10
	fields = 'left', 'right'

class EQ(BinaryOp):
	op = '=='
	lbp = 20
	fields = 'left', 'right'

class NE(BinaryOp):
	op = '!='
	lbp = 20
	fields = 'left', 'right'

class LT(BinaryOp):
	op = '<'
	lbp = 20
	fields = 'left', 'right'

class GT(BinaryOp):
	op = '>'
	lbp = 20
	fields = 'left', 'right'

class As(BinaryOp):
	op = 'as'
	lbp = 30
	fields = 'left', 'right'

class Call(BinaryOp):
	
	op = '('
	lbp = 70
	fields = ('args',)
	
	def led(self, p, left):
		
		self.name = left
		self.fun = None # for type inferencing
		self.virtual = None # for type inferencing
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

class Assign(Statement):
	
	op = '='
	lbp = 5
	fields = 'left', 'right'
	
	def led(self, p, left):
		self.left = left
		self.right = p.expr(self.lbp)
		return self

class Yield(Statement):
	
	kw = 'yield'
	lbp = 0
	fields = 'value',
	
	def nud(self, p):
		self.value = p.expr()
		self.target = None # for use in blocks
		return self

class Suite(Statement):
	
	fields = 'stmts',
	
	def __init__(self, p, pos):
		
		Node.__init__(self, pos)
		self.stmts = []
		
		p.eat(NL)
		p.advance(Indent)
		p.eat(NL)
		
		while True:
			self.stmts.append(p.expr())
			p.eat(NL)
			if isinstance(p.token, Dedent):
				break
		
		p.advance(Dedent)

class Argument(Node):
	fields = 'name',
	def __init__(self, pos):
		Node.__init__(self, pos)
		self.name = None
		self.type = None

class Decl(Node):
	fields = 'decor', 'name', 'args', 'rtype'

class Function(Node):
	
	kw = 'def'
	lbp = 0
	fields = 'decor', 'name', 'args', 'rtype', 'suite'
	
	def nud(self, p):
		
		self.decor = set()
		self.name = p.advance(Name)
		p.advance(Call)
		
		self.args = []
		cur = Argument(self.pos)
		next = p.expr()
		cur.pos = next.pos
		while not isinstance(next, RightPar):
			
			cur.name = next
			if isinstance(p.token, Colon):
				p.advance(Colon)
				cur.type = p.expr()
			
			self.args.append(cur)
			cur	= Argument(self.pos)
			next = p.expr()
			
			if isinstance(next, Comma):
				next = p.expr()
			
			cur.pos = next.pos
		
		self.rtype = None
		if isinstance(p.token, RType):
			p.advance(RType)
			self.rtype = p.expr()
		
		if not isinstance(p.token, Colon):
			
			p.advance(NL)
			if isinstance(p.token, Indent):
				raise util.Error(p.token, "no ':' after function header")
			
			decl = Decl(self.pos)
			decl.decor = self.decor
			decl.name = self.name
			decl.args = self.args
			decl.rtype = self.rtype
			return decl
		
		p.advance(Colon)
		self.suite = Suite(p, self.pos)
		return self

class Pass(Statement):
	
	kw = 'pass'
	lbp = 0
	fields = ()
	
	def nud(self, p):
		return self

class Return(Statement):
	
	kw = 'return'
	lbp = 0
	fields = 'value',
	
	def nud(self, p):
		self.value = None
		if not isinstance(p.token, NL):
			self.value = p.expr()
		return self

class Ternary(Expr):
	
	lbp = 10
	fields = 'cond', 'values'
	
	def __init__(self, p, left, pos):
		Expr.__init__(self, pos)
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

class Import(Statement):
	kw = 'import'
	fields = 'names',
	def nud(self, p):
		self.names = []
		while isinstance(p.token, Name):
			self.names.append(p.expr())
			if isinstance(p.token, Comma):
				p.advance(Comma)
		return self

class RelImport(Statement):
	kw = 'from'
	fields = 'base', 'names'
	def nud(self, p):
		self.base = p.expr()
		self.names = []
		p.advance(Import)
		while isinstance(p.token, Name):
			self.names.append(p.expr())
			if isinstance(p.token, Comma):
				p.advance(Comma)
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

class Decorator(Node):
	
	lbp = 0
	
	def __init__(self, val, pos):
		Node.__init__(self, pos)
		self.decor = {val[1:]}
	
	def nud(self, p):
		p.eat(NL)
		obj = p.expr()
		assert hasattr(obj, 'decor')
		obj.decor |= self.decor
		return obj

class Class(Statement):
	
	kw = 'class'
	fields = 'decor', 'name', 'params', 'attribs', 'methods'
	
	def nud(self, p):
		
		self.decor = set()
		self.name = p.advance(Name)
		self.params = []
		
		if isinstance(p.token, Elem):
			p.advance(Elem)
			self.params.append(p.advance(Name))
			while not isinstance(p.token, ElemEnd):
				p.advance(Comma)
				self.params.append(p.advance(Name))
			p.advance(ElemEnd)
		
		p.advance(Colon)
		p.eat(NL)
		p.advance(Indent)
		p.eat(NL)
		
		self.attribs = []
		self.methods = []
		if isinstance(p.token, Pass):
			p.advance(Pass)
			p.eat(NL)
			p.advance(Dedent)
			return self
		
		while isinstance(p.token, Name):
			field = p.expr()
			p.advance(Colon)
			type = p.expr()
			self.attribs.append((type, field))
			p.eat(NL)
		
		while isinstance(p.token, Function):
			self.methods.append(p.expr())
			p.eat(NL)
		
		p.advance(Dedent)
		return self

class Trait(Statement):
	
	kw = 'trait'
	fields = 'decor', 'name', 'params', 'methods'
	
	def nud(self, p):
		
		self.decor = set()
		self.name = p.advance(Name)
		self.params = []
		
		if isinstance(p.token, Elem):
			p.advance(Elem)
			self.params.append(p.advance(Name))
			while not isinstance(p.token, ElemEnd):
				p.advance(Comma)
				self.params.append(p.advance(Name))
			p.advance(ElemEnd)
		
		p.advance(Colon)
		p.eat(NL)
		p.advance(Indent)
		p.eat(NL)
		
		self.methods = []
		while isinstance(p.token, Function):
			self.methods.append(p.expr())
			p.eat(NL)
		
		p.advance(Dedent)
		return self

# The core of the parsing algorithm

OPERATORS = {cls.op: cls for cls in Registry.types if hasattr(cls, 'op')}
KEYWORDS = {cls.kw: cls for cls in Registry.types if hasattr(cls, 'kw')}

class Pratt(object):
	
	def __init__(self, tokens):
		self.next = self.wrap(tokens).next
		self.token = self.next()
	
	def wrap(self, tokens):
		for t, v, s, e, l in tokens:
			if t == 'name' and v in {'True', 'False'}:
				yield Bool(v, (s, e, l))
			elif t == 'name':
				yield Name(v, (s, e, l))
			elif t == 'num' and '.' not in v:
				yield Int(v, (s, e, l))
			elif t == 'num' and '.' in v:
				yield Float(v, (s, e, l))
			elif t == 'kw':
				yield KEYWORDS[v]((s, e, l))
			elif t == 'str':
				yield String(v, (s, e, l))
			elif t == 'op':
				yield OPERATORS[v]((s, e, l))
			elif t == 'indent' and v > 0:
				yield Indent((s, e, l))
			elif t == 'indent' and v < 0:
				yield Dedent((s, e, l))
			elif t == 'nl':
				yield NL((s, e, l))
			elif t == 'com':
				continue
			elif t == 'deco':
				yield Decorator(v, (s, e, l))
		yield End((s, e))
	
	def eat(self, type):
		while isinstance(self.token, type):
			self.token = self.next()
	
	def advance(self, id):
		if not isinstance(self.token, id):
			bits = self.token.__class__.__name__, id.__name__
			raise util.Error(self.token, 'expected %r, got %r' % bits)
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
	p.eat(NL)
	while not isinstance(p.token, End):
		mod.suite.append(p.expr())
		p.eat(NL)
	return mod
