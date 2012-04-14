import ast

class base(object):
	iface = False
	@property
	def name(self):
		return self.__class__.__name__
	def __repr__(self):
		return '<type: %s>' % self.__class__.__name__
	def __eq__(self, other):
		classes = self.__class__, other.__class__
		return classes[0] == classes[1] and self.__dict__ == other.__dict__
	def __ne__(self, other):
		return not self.__eq__(other)

class void(base):
	ir = 'void'
	methods = {}

class bool(base):
	ir = 'i1'
	methods = {
		'__str__': ('bool.__str__', 'str', []),
		'__eq__': ('bool.__eq__', 'bool', [('v', 'bool')]),
	}

class int(base):
	ir = 'i64'
	methods = {
		'__bool__': ('int.__bool__', 'bool', []),
		'__str__': ('int.__str__', 'str', []),
		'__eq__': ('int.__eq__', 'bool', [('v', 'int')]),
		'__lt__': ('int.__lt__', 'bool', [('v', 'int')]),
		'__add__': ('int.__add__', 'int', [('v', 'int')]),
		'__sub__': ('int.__sub__', 'int', [('v', 'int')]),
		'__mul__': ('int.__mul__', 'int', [('v', 'int')]),
		'__div__': ('int.__div__', 'int', [('v', 'int')]),
	}

class float(base):
	ir = 'double'
	methods = {
		'__str__': ('float.__str__', 'str', []),
	}

class str(base):
	ir = '%str'
	methods = {
		'__bool__': ('str.__bool__', 'bool', []),
		'__eq__': ('str.__eq__', 'bool', [('s', 'str')]),
		'__lt__': ('str.__lt__', 'bool', [('s', 'str')]),
		'__add__': ('str.__add__', 'str', [('s', 'str')]),
		'__del__': ('str.__del__', 'void', []),
	}

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

class file(base):
	ir = '%file'
	methods = {
		'read': ('file.read', 'str', [('size', 'int')]),
		'close': ('file.close', 'void', []),
	}

class array(base):
	def __init__(self, over):
		self.over = over
	@property
	def ir(self):
		return '%array.' + self.over.ir[1:]
	def __repr__(self):
		return '<type: %s[%s]>' % (self.__class__.__name__, self.over.name)

class intiter(base):
	ir = '%intiter'
	methods = {
		'__next__': ('intiter.__next__', 'int', []),
	}

def add(node):
	
	attribs = {}
	for i, (atype, name) in enumerate(node.attribs):
		attribs[name.name] = i, ALL[atype.name]()
	
	vars = {
		'ir': '%' + node.name.name,
		'methods': {},
		'attribs': attribs,
	}
	
	for method in node.methods:
		
		name = method.name.name
		irname = '@%s.%s' % (node.name.name, name)
		rtype = 'void' if not method.rtype else method.rtype.name
		
		args = []
		for arg in method.args:
			args.append(arg.type.name)
		
		vars['methods'][name] = irname, rtype, args
		method.irname = irname
	
	cls = type(node.name.name, (base,), vars)
	ALL[node.name.name] = cls
	return cls()

ALL = {}
for k in globals().keys():
	obj = globals()[k]
	if type(obj) == type and base in obj.__bases__:
		ALL[k] = globals()[k]

CONST = {
	ast.Bool: ALL['bool'],
	ast.Int: ALL['int'],
	ast.Float: ALL['float'],
	ast.String: ALL['str'],
}

def get(t):
	if isinstance(t, base):
		return t
	elif isinstance(t, basestring):
		return ALL[t]()
	elif isinstance(t, ast.Name):
		return ALL[t.name]()
	elif t.__class__ in CONST:
		return CONST[t.__class__]()
	elif isinstance(t, ast.Elem):
		return ALL[t.obj.name](get(t.key))
	else:
		assert False, 'no type %s' % t
