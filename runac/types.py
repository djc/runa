'''Functionality for the Runa type system.

The core types are outlined in this file:

- void
- bool, byte
- i8, u8, i32, u32, int, uint, float
- function
- iter
- tuple (as a `build_tuple()` constructor)
- owner, ref, opt

Actual implementations attached to these types are mostly contained in the
core library. Additionally, helpers are provided for template types and their
concrete variants; these are used for traits and generics support.
'''

from . import ast, util
import copy, platform

WORD_SIZE = int(platform.architecture()[0][:2])

BASIC = {
	'bool': 'i1',
	'byte': 'i8',
	'i8': 'i8',
	'u8': 'i8',
	'i32': 'i32',
	'u32': 'i32',
	'u64': 'i64',
	'int': 'i%i' % WORD_SIZE,
	'uint': 'i%i' % WORD_SIZE,
	'float': 'double',
}

INTEGERS = {
	'i8': (True, 8),
	'u8': (False, 8),
	'i32': (True, 32),
	'u32': (False, 32),
	'u64': (False, 64),
	'int': (True, WORD_SIZE),
	'uint': (False, WORD_SIZE),
}

BASIC_FLOATS = {'float': 64}

class Type(object):
	def __eq__(self, other):
		return self.__class__ == other.__class__

class ReprId(object):
	
	def __hash__(self):
		return hash(repr(self))
	
	def __eq__(self, other):
		return repr(self) == repr(other)
	
	def __ne__(self, other):
		return not self.__eq__(other)
	
	def select(self, node, name, positional, named):
		
		if name not in self.methods:
			msg = "%s does not have a method '%s'"
			if node.args:
				t = node.args[0].type.name
			elif isinstance(node.name.type, Type):
				t = node.name.name
			else:
				assert False, node
			raise util.Error(node, msg % (t, name))
		
		opts = copy.copy(self.methods[name])
		if name == '__init__' and '__new__' in self.methods:
			opts += self.methods['__new__']
		
		if named:
			assert False, named
		
		res, candidates = [], []
		for fun in opts:
			
			tmp = positional
			if '__init__' in fun.decl:
				tmp = [ref(self)] + positional
			
			candidates.append((fun.name, tmp, fun.type.over[1]))
			if len(fun.type.over[1]) != len(tmp) + len(named):
				continue
			
			score = 0
			for at, ft in zip(tmp, fun.type.over[1]):
				if not compat(at, ft, 'args'):
					score -= 1000
					break
				elif at == ft:
					score += 10
				else:
					score += 1
			
			if score > 0:
				res.append(fun)
			
		if not res:
			msg = ['no matching method found, candidates tried:']
			for name, atypes, ftypes in candidates:
				anames = ', '.join(t.name for t in atypes)
				fnames = ', '.join(t.name for t in ftypes)
				display = name.split('$', 1)[0]
				msg.append('    (%s) -> %s(%s)' % (anames, display, fnames))
			raise util.Error(node, '\n'.join(msg))
		
		assert len(res) == 1, res
		return res[0]

class base(ReprId):
	
	byval = False
	mut = False
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

class trait(ReprId):
	
	byval = False
	attribs = {}
	methods = {}
	type = Type()
	
	@property
	def name(self):
		return self.__class__.__name__
	
	@property
	def ir(self):
		return '%%%s.wrap' % self.name
	
	def __repr__(self):
		return '<trait: %s>' % self.name

class concrete(base):
	attribs = {}
	methods = {}

class template(ReprId):
	
	byval = False
	attribs = {}
	methods = {}
	type = Type()
	
	@property
	def name(self):
		return self.__class__.__name__
	
	@property
	def ir(self):
		assert False, '%s is not a concrete type' % self.name
	
	def __repr__(self):
		return '<template: %s>' % self.__class__.__name__

class iter(template):
	params = 'T',
	attribs = {}
	methods = {}

class void(base):
	ir = 'void'
	attribs = {}
	methods = {}
	byval = True

class anyint(base):
	
	attribs = {}
	methods = {}
	
	@property
	def ir(self):
		assert False, 'not a concrete type'

class anyfloat(base):
	
	attribs = {}
	methods = {}
	
	@property
	def ir(self):
		assert False, 'not a concrete type'

class module(base):
	def __init__(self, path=None):
		self.path = path
		self.functions = {}

class owner(base):
	
	def __init__(self, over):
		self.over = over
		self.mut = True
	
	@property
	def name(self):
		return '$%s' % self.over.name
	
	@property
	def ir(self):
		return self.over.ir + '*'
	
	def __repr__(self):
		return '<type: $%s>' % (self.over.name)

class ref(base):
	
	def __init__(self, over, mut=False):
		self.over = over
		self.mut = mut
	
	@property
	def name(self):
		return '%s&%s' % ('~' if self.mut else '', self.over.name)
	
	@property
	def ir(self):
		return self.over.ir + '*'
	
	def __repr__(self):
		return '<type: &%s>' % (self.over.name)

class opt(base):
	
	def __init__(self, over):
		self.over = over
	
	@property
	def name(self):
		return '?%s' % self.over.name
	
	@property
	def ir(self):
		return self.over.ir
	
	def __repr__(self):
		return '<type: ?%s>' % (self.over.name)

SINTS = {anyint()}
UINTS = set()
INTS = {anyint()}
FLOATS = {anyfloat()}
WRAPPERS = owner, ref
BASE = void, anyint, anyfloat, iter

class function(base):
	
	def __init__(self, rtype, formal):
		self.over = rtype, formal
		self.args = None
	
	def __repr__(self):
		if not self.over[1] or isinstance(self.over[1][0], tuple):
			formal = ['%r' % i[1] for i in self.over[1]]
		else:
			formal = ['%r' % i for i in self.over[1]]
		return '<fun %r <- [%s]>' % (self.over[0], ', '.join(formal))
	
	@property
	def ir(self):
		args = ', '.join(a.ir for a in self.over[1])
		return '%s (%s)*' % (self.over[0].ir, args)

def wrapped(t):
	return isinstance(t, WRAPPERS)

def unwrap(t):
	while isinstance(t, WRAPPERS):
		t = t.over
	return t

def generic(t):
	return isinstance(unwrap(t), (anyint, anyfloat))

def wrangle(s):
	s = s.replace('&', 'R')
	s = s.replace('$', 'O')
	s = s.replace('[', 'BT')
	s = s.replace(']', 'ET')
	return s

def compat(a, f, mode='default'):
	
	assert mode in {'default', 'args', 'return'}
	if isinstance(a, concrete) and isinstance(f, concrete):
		pairs = zip(a.params, f.params)
		return all(compat(i[0], i[1], mode) for i in pairs)
	
	if isinstance(a, (tuple, list)) and isinstance(f, (tuple, list)):
		if len(a) != len(f):
			return False
		if f and f[-1] == VarArgs():
			return all(compat(i[0], i[1], mode) for i in zip(a, f[:-1]))
		return all(compat(i[0], i[1], mode) for i in zip(a, f))
	
	if a == f:
		return True
	elif isinstance(a, anyint) and f in INTS:
		return True
	elif isinstance(a, ref) and isinstance(f, owner):
		return False
	elif mode == 'return' and isinstance(a, owner) and isinstance(f, ref):
		return False
	elif not isinstance(a, opt) and isinstance(f, opt):
		return compat(a, f.over, mode)
	elif a in UINTS and f in UINTS:
		return a.bits < f.bits
	
	if wrapped(a) and wrapped(f):
		return compat(unwrap(a), unwrap(f), mode)
	elif mode == 'args' and (wrapped(a) or wrapped(f)):
		return compat(unwrap(a), unwrap(f), mode)
	
	if not isinstance(f, trait):
		return False
	
	for k, malts in util.items(f.methods):
		
		if k not in a.methods:
			return False
		
		art = a.methods[k][0].type.over[0]
		frt = malts[0].type.over[0]
		rc = compat(art, frt, mode)
		if not rc:
			return False
		
		tmalts = set()
		for fun in malts:
			tmalts.add(tuple(at for at in fun.type.over[1][1:]))
		
		amalts = set()
		for fun in a.methods[k]:
			amalts.add(tuple(at for at in fun.type.over[1][1:]))
		
		if tmalts != amalts:
			return False
	
	return True

class Stub(object):
	def __init__(self, name):
		self.name = name
	def __repr__(self):
		return '<%s(%r)>' % (self.__class__.__name__, self.name)

class VarArgs(base):
	@property
	def ir(self):
		return '...'

class FunctionDecl(util.AttribRepr):
	
	def __init__(self, decl, type):
		self.decl = decl
		self.type = type
		self.name = decl # might be overridden by the Module
	
	@classmethod
	def from_decl(cls, mod, node):
		atypes = [mod.type(a.type) for a in node.args]
		funtype = function(mod.type(node.rtype), atypes)
		return cls(node.name.name, funtype)
	
	@classmethod
	def from_ast(cls, mod, node, type=None, stubs={}):
		
		args = []
		for i, arg in enumerate(node.args):
			if not i and arg.name.name == 'self':
				wrapper = owner if node.name.name == '__del__' else ref
				args.append((wrapper(type), 'self'))
			elif arg.type is None:
				msg = "missing type for argument '%s'"
				raise util.Error(arg, msg % arg.name.name)
			else:
				args.append((mod.type(arg.type, stubs), arg.name.name))
		
		rtype = void()
		if node.rtype is not None:
			rtype = mod.type(node.rtype, stubs)
		
		funtype = function(rtype, tuple(i[0] for i in args))
		funtype.args = tuple(i[1] for i in args)
		
		name = node.name.name
		irname = mod.name + '.' + name
		if type is not None:
			irname = mod.name + '.%s.%s' % (type.name, name)
			if name in type.methods:
				wrangled = '.'.join(wrangle(t.name) for t in funtype.over[1])
				irname = irname + '$' + wrangled
				assert funtype.over[0] == type.methods[name][0].type.over[0]
		
		irname = 'main' if irname == 'Runa.__main__.main' else irname
		return cls(irname, funtype)

def create(node):
	
	if isinstance(node, ast.Trait):
		parent = trait
	elif node.params:
		parent = template
	else:
		parent = base
	
	if isinstance(node, ast.Trait):
		fields = {'methods': {}}
	elif node.params:
		fields = {'methods': {}, 'attribs': {}, 'params': {}}
	else:
		fields = {'methods': {}, 'attribs': {}}
	
	if node.name.name in BASIC:
		fields['ir'] = BASIC[node.name.name]
		fields['byval'] = True
	
	return type(node.name.name, (parent,), fields)()

def build_tuple(params):
	params = tuple(params)
	name = 'tuple[%s]' % ', '.join(p.name for p in params)
	internal = name.replace('%', '_').replace('.', '_')
	return type(internal, (concrete,), {
		'ir': '%tuple$' + '.'.join(wrangle(t.name) for t in params),
		'name': name,
		'params': params,
		'methods': {'v%i' % i: (i, t) for (i, t) in enumerate(params)},
		'attribs': {},
	})()

def apply(tpl, params):
	
	assert isinstance(params, tuple)
	name = '%s[%s]' % (tpl.name, ', '.join(p.name for p in params))
	internal = name.replace('$', '_').replace('.', '_')
	cls = type(internal, (concrete,), {
		'ir': '%' + tpl.name + '$' + '.'.join(t.name for t in params),
		'name': name,
		'params': params,
		'methods': {},
		'attribs': {},
	})
	
	trans = {k: v for (k, v) in zip(tpl.params, params)}
	for k, v in util.items(tpl.attribs):
		if isinstance(v[1], Stub):
			cls.attribs[k] = v[0], trans[v[1].name]
		elif isinstance(v[1], WRAPPERS) and isinstance(v[1].over, Stub):
			cls.attribs[k] = v[0], v[1].__class__(trans[v[1].over.name])
		else:
			cls.attribs[k] = v[0], v[1]
	
	for k, mtypes in util.items(tpl.methods):
		for method in mtypes:
			
			rtype = method.type.over[0]
			if rtype == tpl:
				rtype = cls()
			
			formal = method.type.over[1]
			formal = (ref(cls()),) + formal[1:]
			t = function(rtype, formal)
			
			pmd = tpl.name + '$' + '.'.join(t.name for t in params)
			decl = method.decl.replace(tpl.name, pmd)
			cls.methods.setdefault(k, []).append(FunctionDecl(decl, t))
	
	return cls()

def fill(mod, node):
	
	obj = mod.scope[node.name.name]
	cls, stubs = obj.__class__, {}
	if not isinstance(node, ast.Trait):
		cls.params = tuple(n.name for n in node.params)
		stubs = {n.name: Stub(n.name) for n in node.params}
		for i, (atype, name) in enumerate(node.attribs):
			cls.attribs[name.name] = i, mod.type(atype, stubs)
	
	for method in node.methods:
		name = method.name.name
		fun = FunctionDecl.from_ast(mod, method, obj, stubs)
		cls.methods.setdefault(name, []).append(fun)
		method.irname = fun.decl
	
	if node.name.name in INTEGERS:
		
		cls.signed, cls.bits = INTEGERS[node.name.name]
		INTS.add(obj)
		if cls.signed:
			SINTS.add(obj)
		else:
			UINTS.add(obj)
		
		mod.scope['anyint'].methods.update(cls.methods)
	
	elif node.name.name in BASIC_FLOATS:
		cls.bits = BASIC_FLOATS[node.name.name]
		FLOATS.add(obj)
		mod.scope['anyfloat'].methods.update(cls.methods)
