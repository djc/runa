
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
	def __init__(self, name):
		self.name = name
	def nud(self, parser):
		return self

class Number(Node):
	def __init__(self, num):
		self.val = num
	def nud(self, parser):
		return self

class End(Node):
	op = 'end'
	lbp = 0
	def nud(self, parser):
		return self

class String(Node):
	op = 'str'
	def __init__(self, value):
		self.value = value
	def nud(self, parser):
		return self

class BinaryOp(Node):
	def led(self, parser, left):
		self.left = left
		self.right = parser.expr(self.lbp)
		return self

class Call(BinaryOp, Node):
	
	op = '('
	lbp = 150
	fields = ('args',)
	
	def led(self, parser, left):
		self.name = left
		self.args = (parser.expr(),)
		parser.advance(RightPar)
		return self
	
	def nud(self, parser):
		expr = parser.expr()
		assert parser.token.op == ')'
		parser.token = parser.next()
		return expr

class RightPar(Node):
	op = ')'
	lbp = 0

class Add(BinaryOp):
	op = '+'
	lbp = 15
	fields = 'left', 'right'

class Sub(BinaryOp):
	op = '-'
	lbp = 15
	fields = 'left', 'right'

class Mul(BinaryOp):
	op = '*'
	lbp = 20
	fields = 'left', 'right'

class Assign(BinaryOp):
	op = '='
	lbp = 10
	fields = 'left', 'right'

class Pratt(object):
	
	def __init__(self):
		self.token = None
		self.next = next
	
	def wrap(self, tokens):
		for t, v in tokens:
			if t == 'name':
				yield Name(v)
			elif t == 'num':
				yield Number(v)
			elif v == '(':
				yield Call()
			elif v == ')':
				yield RightPar()
			elif v == '+':
				yield Add()
			elif v == '-':
				yield Sub()
			elif v == '*':
				yield Mul()
			elif v == '=':
				yield Assign()
			elif t == 'str':
				yield String(v)
			elif t == 'nl':
				yield End()
		yield End()
	
	def advance(self, id):
		if not isinstance(self.token, id):
			raise Exception('expected %r' % id)
		self.token = self.next()
	
	def expr(self, rbp=0):
		t, self.token = self.token, self.next()
		left = t.nud(self)
		while rbp < self.token.lbp:
			t, self.token = self.token, self.next()
			left = t.led(self, left)
		return left
	
	def parse(self, tokens):
		self.next = self.wrap(tokens).next
		self.token = self.next()
		return self.expr()

# Higher-level

class Statement(Node):
	
	@classmethod
	def parse(cls, tokens):
		return Pratt().parse(tokens)

class TypeExpr(Node):
	
	fields = ()
	
	def __init__(self, base, over=None):
		self.base = base
		self.over = over
	
	@classmethod
	def parse(cls, tokens):
		
		cur = next(tokens)
		assert cur[0] == 'name'
		base = cur[1]
		cur = next(tokens)
		if cur != ('op', '['):
			tokens.push(cur)
			return cls(base)
		
		cur = next(tokens)
		assert cur[0] == 'name'
		over = cur[1]
		cur = next(tokens)
		assert cur == ('op', ']')
		return cls(base, over)

class Suite(Node):
	
	fields = ('stmts',)
	
	def __init__(self, stmts):
		self.stmts = stmts
	
	@classmethod
	def parse(cls, tokens):
		cur = next(tokens)
		stmts = []
		while cur != ('indent', -1):
			tokens.push(cur)
			stmts.append(Statement.parse(tokens))
			cur = next(tokens)
		return cls(stmts)

class Function(Node):
	
	fields = 'rtype', 'code'
	
	def __init__(self, name, args, rtype, code):
		self.name = name
		self.args = args
		self.rtype = rtype
		self.code = code
	
	@classmethod
	def parse(cls, name, tokens):
		
		cur = next(tokens)
		args = []
		assert cur == ('op', '(')
		while cur in (('op', '('), ('op', ',')):
			cur = next(tokens)
			assert next(tokens) == ('op', ':')
			type = TypeExpr.parse(tokens)
			args.append((cur[1], type))
			cur = next(tokens)
		
		assert cur == ('op', ')')
		assert next(tokens) == ('op', '->')
		rtype = TypeExpr.parse(tokens)
		assert next(tokens) == ('op', ':')
		
		cur = next(tokens)
		while cur[0] == 'nl':
			cur = next(tokens)
		
		assert cur == ('indent', 1)
		code = Suite.parse(tokens)
		return cls(name, args, rtype, code)


class Module(Node):
	
	fields = ('values',)
	
	def __init__(self, values):
		self.values = values
	
	@classmethod
	def parse(cls, tokens):
		values = []
		cur = next(tokens)
		while cur:
			
			if cur[0] == 'nl':
				cur = next(tokens)
				continue
			
			if cur[0] == 'name' and cur[1] == 'def':
				cur = next(tokens)
				assert cur[0] == 'name'
				values.append(Function.parse(cur[1], tokens))
			else:
				assert False, 'unknown token ' + str(cur)
			
			try:
				cur = next(tokens)
			except StopIteration:
				break
			
		return cls(values)
