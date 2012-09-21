import ast

class Type(object):
	def __eq__(self, other):
		return self.__class__ == other.__class__

class base(object):
	
	iface = False
	forward = False
	attribs = {}
	methods = {}
	type = Type()
	
	@property
	def name(self):
		return self.__class__.__name__
	
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

class module(base):
	def __init__(self):
		self.functions = {}

class __ptr__(base):
	
	def __init__(self, over):
		self.over = over
		self.methods = {
			'offset': (
				'__ptr__.offset',
				self,
				[('n', get('u32'))]
			),
		}
	
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

class float(base):
	@property
	def ir(self):
		raise TypeError('not a concrete type')

class int(base):
	@property
	def ir(self):
		raise TypeError('not a concrete type')

class void(base):
	ir = 'void'

class bool(base):
	ir = 'i1'
	methods = {
		'__str__': ('bool.__str__', 'str', []),
		'__eq__': ('bool.__eq__', 'bool', [('v', 'bool')]),
	}

class byte(base):
	ir = 'i8'

class i32(base):
	ir = 'i32'
	bits = 32
	signed = True

class u32(base):
	ir = 'i32'
	bits = 32
	signed = False

class i64(base):
	ir = 'i64'
	bits = 64
	signed = True

class word(base):
	ir = 'i64'
	bits = 64
	signed = True

class uword(base):
	ir = 'i64'
	bits = 64
	signed = False

class str(base):
	forward = True

class IStr(base):
	ir = '%IStr.wrap'
	iface = True
	vttype = '%IStr'
	impl = '@IStr'

class IBool(base):
	ir = '%IBool.wrap'
	iface = True
	vttype = '%IBool'
	impl = '@IBool'

class array(base):
	def __init__(self, over):
		self.over = over
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

INTS = {i32(), u32(), i64(), int(), word(), uword()}
FLOATS = {float()}

def add(node):
	
	if node.name.name in ALL and ALL[node.name.name].forward:
		cls = ALL[node.name.name]
	else:
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
		rtype = get('void' if not method.rtype else method.rtype.name)
		
		args = []
		for i, arg in enumerate(method.args):
			if not i and arg.name.name == 'self':
				args.append(('self', get(node.name)))
			else:
				args.append((arg.name.name, get(arg.type)))
		
		cls.methods[name] = irname, rtype, args
		method.irname = irname
	
	return cls()
