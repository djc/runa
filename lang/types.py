import ast

class Type(object):
	def __eq__(self, other):
		return self.__class__ == other.__class__

class base(object):
	
	byval = False
	iface = False
	attribs = {}
	methods = {}
	type = Type()
	
	@property
	def name(self):
		return self.__class__.__name__
	
	@property
	def ir(self):
		return '%' + self.name
	
	def __repr__(self):
		return '<type: %s>' % self.__class__.__name__
	
	def __eq__(self, other):
		if self.__class__ != other.__class__:
			return False
		if getattr(self, 'over', None) != getattr(other, 'over', None):
			return False
		return True
	
	def __ne__(self, other):
		return not self.__eq__(other)
	
	def __hash__(self):
		return hash(self.__class__)

class void(base):
	ir = 'void'
	byval = True

class float(base):
	@property
	def ir(self):
		raise TypeError('not a concrete type')

class int(base):
	@property
	def ir(self):
		raise TypeError('not a concrete type')

class module(base):
	def __init__(self, path=None):
		self.path = path
		self.functions = {}

class owner(base):
	
	def __init__(self, over):
		self.over = over
		self.methods = {
			'offset': (
				'owner.offset',
				ref(self.over),
				[('self', ref(self.over)), ('n', uword())]
			),
		}
	
	@property
	def name(self):
		return 'owner[%s]' % self.over.name
	
	@property
	def ir(self):
		return self.over.ir + '*'
	
	def __repr__(self):
		return '<type: %s[%s]>' % (self.__class__.__name__, self.over.name)

class ref(base):
	
	def __init__(self, over):
		self.over = over
	
	@property
	def name(self):
		return 'ref[%s]' % self.over.name
	
	@property
	def ir(self):
		return self.over.ir + '*'
	
	def __repr__(self):
		return '<type: %s[%s]>' % (self.__class__.__name__, self.over.name)

class function(base):
	
	def __init__(self, rtype, formal):
		self.over = rtype, formal
	
	def __repr__(self):
		if not self.over[1] or isinstance(self.over[1][0], tuple):
			formal = ['%r' % i[1] for i in self.over[1]]
		else:
			formal = ['%r' % i for i in self.over[1]]
		return '<fun %r <- [%s]>' % (self.over[0], ', '.join(formal))
	
	@property
	def ir(self):
		raise NotImplementedError

class bool(base):
	ir = 'i1'
	byval = True

class byte(base):
	ir = 'i8'
	bits = 8
	signed = False
	byval = True

class i32(base):
	ir = 'i32'
	bits = 32
	signed = True
	byval = True

class u32(base):
	ir = 'i32'
	bits = 32
	signed = False
	byval = True

class word(base):
	ir = 'i64'
	bits = 64
	signed = True
	byval = True

class uword(base):
	ir = 'i64'
	bits = 64
	signed = False
	byval = True

class array(base):
	def __init__(self, over):
		self.over = over
		self.attribs = {
			'len': (0, u32()),
			'data': (1, owner(over)),
		}
	@property
	def ir(self):
		return '%array.' + self.over.ir[1:]
	def __repr__(self):
		return '<type: %s[%s]>' % (self.__class__.__name__, self.over.name)

def get(t):
	if t is None:
		return void()
	elif isinstance(t, base):
		return t
	elif isinstance(t, basestring):
		return ALL[t]()
	elif isinstance(t, ast.Name):
		return ALL[t.name]()
	elif isinstance(t, ast.Elem):
		return ALL[t.obj.name](get(t.key))
	elif isinstance(t, ast.Owner):
		return owner(get(t.value))
	elif isinstance(t, ast.Ref):
		return ref(get(t.value))
	else:
		assert False, 'no type %s' % t

ALL = {}
for k in globals().keys():
	obj = globals()[k]
	if type(obj) == type and base in obj.__bases__:
		ALL[k] = globals()[k]

for k, cls in ALL.iteritems():
	for m, mdata in cls.methods.iteritems():
		rtype = get(mdata[1])
		atypes = [(n, get(t)) for (n, t) in mdata[2]]
		cls.methods[m] = (m[0], rtype, atypes)

SINTS = {i32(), int(), word()}
UINTS = {byte(), u32(), uword()}
INTS = SINTS | UINTS
FLOATS = {float()}
WRAPPERS = owner, ref

def add(node):
	
	cls = ALL[node.name.name] = type(node.name.name, (base,), {
		'ir': '%' + node.name.name,
		'methods': {},
		'attribs': {},
	})
	
	for i, (atype, name) in enumerate(node.attribs):
		cls.attribs[name.name] = i, get(atype)
	
	for method in node.methods:
		
		name = method.name.name
		irname = '%s.%s' % (node.name.name, name)
		rtype = void() if method.rtype is None else get(method.rtype)
		
		args = []
		for i, arg in enumerate(method.args):
			if not i and arg.name.name == 'self':
				wrapper = owner if name == '__del__' else ref
				args.append(('self', wrapper(get(node.name))))
			else:
				args.append((arg.name.name, get(arg.type)))
		
		cls.methods[name] = irname, rtype, args
		method.irname = irname
	
	return cls()
