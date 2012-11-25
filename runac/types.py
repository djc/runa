import ast

class Type(object):
	def __eq__(self, other):
		return self.__class__ == other.__class__

class base(object):
	
	byval = False
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
	
	def __hash__(self):
		return hash((self.__class__, getattr(self, 'over', None)))
	
	def __eq__(self, other):
		if self.__class__ != other.__class__:
			return False
		if getattr(self, 'over', None) != getattr(other, 'over', None):
			return False
		return True
	
	def __ne__(self, other):
		return not self.__eq__(other)

class concrete(base):
	pass

class template(base):
	
	@property
	def ir(self):
		raise TypeError('not a concrete type')
	
	def __repr__(self):
		return '<template: %s>' % self.__class__.__name__
	
	def __getitem__(self, params):
		
		params = params if isinstance(params, tuple) else (params,)
		name = '%s[%s]' % (self.name, ', '.join(p.name for p in params))
		internal = name.replace('$', '_').replace('.', '_')
		cls = ALL[(self.name, params)] = type(internal, (concrete,), {
			'ir': '%' + self.name + '$' + '.'.join(t.name for t in params),
			'name': name,
			'methods': {},
			'attribs': {},
		})
		
		trans = {k: v for (k, v) in zip(self.params, params)}
		for k, v in self.attribs.iteritems():
			if isinstance(v[1], Stub):
				cls.attribs[k] = v[0], trans[v[1].name]
			elif isinstance(v[1], WRAPPERS) and isinstance(v[1].over, Stub):
				cls.attribs[k] = v[0], v[1].__class__(trans[v[1].over.name])
			else:
				cls.attribs[k] = v[0], v[1]
		
		return cls()

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

BASIC = {
	'bool': 'i1',
}

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
		return '$%s' % self.over.name
	
	@property
	def ir(self):
		return self.over.ir + '*'
	
	def __repr__(self):
		return '<type: $%s>' % (self.over.name)

class ref(base):
	
	def __init__(self, over):
		self.over = over
	
	@property
	def name(self):
		return '&%s' % self.over.name
	
	@property
	def ir(self):
		return self.over.ir + '*'
	
	def __repr__(self):
		return '<type: &%s>' % (self.over.name)

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

class Stub(object):
	def __init__(self, name):
		self.name = name
	def __repr__(self):
		return '<%s(%r)>' % (self.__class__.__name__, self.name)

def get(t, stubs={}):
	if t is None:
		return void()
	elif isinstance(t, base):
		return t
	elif isinstance(t, basestring) and t[0] == '$':
		return owner(get(t[1:], stubs))
	elif isinstance(t, basestring) and t[0] == '&':
		return ref(get(t[1:], stubs))
	elif isinstance(t, basestring):
		return stubs[t] if t in stubs else ALL[t]()
	elif isinstance(t, ast.Name):
		return stubs[t.name] if t.name in stubs else ALL[t.name]()
	elif isinstance(t, ast.Elem):
		return ALL[t.obj.name](get(t.key, stubs))
	elif isinstance(t, ast.Owner):
		return owner(get(t.value, stubs))
	elif isinstance(t, ast.Ref):
		return ref(get(t.value, stubs))
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
	parent = base if not node.params else template
	ALL[node.name.name] = type(node.name.name, (parent,), {
		'ir': '%' + node.name.name,
		'methods': {},
		'attribs': {},
	})

def fill(node):
	
	cls = ALL[node.name.name]
	if node.name.name in BASIC:
		cls.ir = BASIC[node.name.name]
		cls.byval = True
	
	cls.params = tuple(n.name for n in node.params)
	stubs = {n.name: Stub(n.name) for n in node.params}
	for i, (atype, name) in enumerate(node.attribs):
		cls.attribs[name.name] = i, get(atype, stubs)
	
	for method in node.methods:
		
		name = method.name.name
		irname = '%s.%s' % (node.name.name, name)
		rtype = void() if method.rtype is None else get(method.rtype, stubs)
		
		args = []
		for i, arg in enumerate(method.args):
			if not i and arg.name.name == 'self':
				wrapper = owner if name == '__del__' else ref
				args.append(('self', wrapper(get(node.name, stubs))))
			else:
				args.append((arg.name.name, get(arg.type, stubs)))
		
		cls.methods[name] = irname, rtype, args
		method.irname = irname
	
	return cls()
