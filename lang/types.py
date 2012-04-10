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
		'__str__': ('@bool.__str__', 'str'),
		'__eq__': ('@bool.__eq__', 'bool', 'bool'),
	}

class int(base):
	ir = 'i64'
	methods = {
		'__bool__': ('@int.__bool__', 'bool'),
		'__str__': ('@int.__str__', 'str'),
		'__eq__': ('@int.__eq__', 'bool', 'int'),
		'__lt__': ('@int.__lt__', 'bool', 'int'),
		'__add__': ('@int.__add__', 'int', 'int'),
		'__sub__': ('@int.__sub__', 'int', 'int'),
		'__mul__': ('@int.__mul__', 'int', 'int'),
		'__div__': ('@int.__div__', 'int', 'int'),
	}

class float(base):
	ir = 'double'
	methods = {
		'__str__': ('@float.__str__', 'str'),
	}

class str(base):
	ir = '%str'
	methods = {
		'__bool__': ('@str.__bool__', 'bool'),
		'__eq__': ('@str.__eq__', 'bool', 'str'),
		'__lt__': ('@str.__lt__', 'bool', 'str'),
		'__add__': ('@str.__add__', 'str', 'str'),
		'__del__': ('@str.__del__', 'void'),
	}

class IStr(base):
	ir = '%IStr.wrap'
	iface = True
	vttype = '%IStr'
	impl = '@IStr'

class file(base):
	ir = '%file'
	methods = {
		'read': ('@file.read', 'str', 'file', 'int'),
		'close': ('@file.close', 'void'),
	}

class array(base):
	def __init__(self, over):
		self.over = over
	@property
	def ir(self):
		return '%array.' + self.over.ir[1:]

class intiter(base):
	ir = '%intiter'
	methods = {
		'__next__': ('@intiter.__next__', 'int', 'intiter'),
	}

def add(node):
	
	attribs = {}
	for i, (atype, name) in enumerate(node.attribs):
		attribs[name.name] = i, ALL[atype.name]
	
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
		
		meta = (irname, rtype) + tuple(args)
		vars['methods'][name] = meta
		method.irname = irname
	
	cls = type(node.name.name, (base,), vars)
	ALL[node.name.name] = cls
	return cls()

ALL = {}
for k in globals().keys():
	obj = globals()[k]
	if type(obj) == type and base in obj.__bases__:
		ALL[k] = globals()[k]
