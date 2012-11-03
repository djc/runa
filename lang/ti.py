from lang import types, ast

class Object(object):
	
	def __init__(self, type, val=None):
		self.type = type
		self.val = val
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%r' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

class Module(object):
	
	def __init__(self, name, init):
		self.name = name
		self.attribs = init
		self.type = types.module(name)
		for k, val in init.iteritems():
			if isinstance(val, Function):
				self.type.functions[k] = val.type
				val.name = '%s.%s' % (name, k)
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%r' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	
	def __getitem__(self, key):
		return self.attribs[key]
	
	def __contains__(self, key):
		return key in self.attribs
	
	def iteritems(self):
		return self.attribs.iteritems()

class Function(object):
	
	def __init__(self, decl, type):
		self.decl = decl
		self.type = type
		self.name = decl # might be overridden by the Module
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%r' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

ROOT = Module('', {
	'__builtin__': Module('__builtin__', {
		'u32': types.u32(),
		'byte': types.byte(),
		'bool': types.bool(),
		'False': Object(types.bool(), 0),
		'True': Object(types.bool(), 1),
	}),
	'__internal__': Module('__internal__', {
		'__ptr__': types.__ptr__,
		'__malloc__': Function('lang.malloc',
			types.function(types.__ptr__(types.byte()), (types.uword(),))
		),
		'__free__': Function('lang.free', types.function(types.void(), (
			types.__ptr__(types.byte()),
		))),
		'__memcpy__': Function('llvm.memcpy.p0i8.p0i8.i32',
			types.function(types.void(), (
				types.__ptr__(types.byte()),
				types.__ptr__(types.byte()),
				types.u32(),
				types.u32(),
				types.bool(),
			)
		)),
	}),
	'libc': Module('libc', {
		'string': Module('libc.string', {
			'strncmp': Function('strncmp', types.function(types.i32(), (
				types.__ptr__(types.byte()),
				types.__ptr__(types.byte()),
				types.uword(),
			))),
		}),
	}),
})

def resolve(mod, n):
	parts = n.split('.')
	if parts[0] in ROOT:
		obj = ROOT
		for p in parts:
			obj = obj[p]
		return obj
	elif parts[0] in mod.types:
		method = mod.types[parts[0]].methods[parts[1]]
		return Function(method[0], types.function(method[1], method[2]))
	elif parts[0] in types.ALL:
		method = types.get(parts[0]).methods[parts[1]]
		return Function(method[0], types.function(method[1], method[2]))

class Scope(object):
	
	def __init__(self, parent=None):
		self.parent = parent
		self.vars = {}
	
	def __contains__(self, key):
		if key in self.vars:
			return True
		elif self.parent is not None:
			return key in self.parent
		else:
			return False
	
	def __getitem__(self, key):
		if key in self.vars:
			return self.vars[key]
		elif self.parent is not None and key in self.parent:
			return self.parent[key]
		else:
			raise KeyError(key)
	
	def __setitem__(self, key, val):
		self.vars[key] = val
	
	def resolve(self, node):
		if isinstance(node, ast.Name):
			assert self[node.name].type == types.Type()
			return self[node.name]
		elif isinstance(node, ast.Elem):
			inner = self.resolve(node.key)
			outer = self.resolve(node.obj)
			return outer(inner)
		else:
			assert False

class TypeChecker(object):
	
	def __init__(self, fun):
		self.flow = fun.flow
		self.scopes = {}
		self.cur = None
	
	def check(self, scope):
		self.scopes[None] = scope
		for i, b in sorted(self.flow.blocks.iteritems()):
			
			self.cur = b
			preds = self.flow.redges.get(i, [None])
			scope = Scope(self.scopes[preds[0]])
			for step in b.steps:
				self.visit(step, scope)
			
			self.scopes[i] = scope
	
	def visit(self, node, scope):
		
		if hasattr(self, node.__class__.__name__):
			getattr(self, node.__class__.__name__)(node, scope)
			return
		
		for k in node.fields:
			attr = getattr(node, k)
			if isinstance(attr, list):
				for v in attr:
					self.visit(v, scope)
			else:
				self.visit(attr, scope)
	
	def Name(self, node, scope):
		node.type = scope[node.name].type
		self.cur.uses.add(node.name)
	
	def Bool(self, node, scope):
		node.type = types.bool()
	
	def Int(self, node, scope):
		node.type = types.int()
	
	def Attrib(self, node, scope):
		self.visit(node.obj, scope)
		node.type = node.obj.type.attribs[node.attrib.name][1]
		assert node.type is not None, 'FAIL'
	
	def Add(self, node, scope):
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		if node.left.type == node.right.type:
			node.type = node.left.type
		else:
			assert False, 'add sides different types'
	
	def LT(self, node, scope):
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		if node.left.type == node.right.type:
			node.type = types.bool()
		elif node.left.type == types.int():
			node.type = types.bool()
		elif node.right.type == types.int():
			node.type = types.bool()
		else:
			assert False, 'lt sides different types'
	
	def GT(self, node, scope):
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		if node.left.type == node.right.type:
			node.type = types.bool()
		elif node.left.type == types.int():
			node.type = types.bool()
		elif node.right.type == types.int():
			node.type = types.bool()
		else:
			assert False, 'gt sides different types'
	
	def Eq(self, node, scope):
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		if node.left.type == node.right.type:
			node.type = types.bool()
		elif node.left.type == types.int():
			node.type = types.bool()
		elif node.right.type == types.int():
			node.type = types.bool()
		else:
			assert False, 'eq sides different types'
	
	def NEq(self, node, scope):
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		if node.left.type == node.right.type:
			node.type = types.bool()
		elif node.left.type == types.int():
			node.type = types.bool()
		elif node.right.type == types.int():
			node.type = types.bool()
		else:
			assert False, 'neq sides different types'
	
	def Call(self, node, scope):
		
		for arg in node.args:
			self.visit(arg, scope)
		
		if isinstance(node.name, ast.Attrib):
			self.visit(node.name.obj, scope)
			if node.name.obj.type == types.module():
				mod = scope[node.name.obj.name]
				fun = mod.type.functions[node.name.attrib.name]
				qual = mod.name + '.' + node.name.attrib.name
				node.name = ast.Name(qual, node.name.pos)
				node.type = fun.over[0]
			else:
				meth = node.name.obj.type.methods[node.name.attrib.name]
				mtype = types.function(meth[1], meth[2])
				node.name = Function(meth[0], mtype)
				node.type = mtype.over[0]
			return
		
		assert isinstance(node.name, ast.Name), 'call non-{attrib,name,type}'
		obj = scope[node.name.name]
		if not isinstance(obj, types.base):
			node.type = scope[node.name.name].type.over[0]
		else:
			node.name.name = '%s.__init__' % node.name.name
			node.type = obj
		
		if isinstance(obj, Function):
			node.name.name = obj.name
	
	def CondBranch(self, node, scope):
		self.visit(node.cond, scope)
	
	def Assign(self, node, scope):
		
		if not isinstance(node.left, ast.Name):
			self.visit(node.left, scope)
			self.visit(node.right, scope)
			if node.left.type != node.right.type:
				assert False, 'assign incorrect type to not-a-name'
			return
		
		if node.left.name in scope:
			assert False, 'reassignment'
		
		self.visit(node.right, scope)
		assert node.right.type is not None
		scope[node.left.name] = Object(node.right.type)
		node.left.type = node.right.type
	
	def Ternary(self, node, scope):
		self.visit(node.cond, scope)
		self.visit(node.values[0], scope)
		self.visit(node.values[1], scope)
		if node.values[0].type == node.values[1].type:
			node.type = node.values[0].type
		else:
			assert False, 'ternary sides different types'

def process(base, fun):
	
	start = Scope(base)
	for arg in fun.args:
		if not isinstance(arg.type, types.base):
			arg.type = start.resolve(arg.type)
		start[arg.name.name] = Object(arg.type)
	
	checker = TypeChecker(fun)
	checker.check(start)
	

def typer(mod):
	
	base = Scope()
	for name, val in ROOT['__builtin__'].iteritems():
		base[name] = val
	
	for name, ref in mod.refs.iteritems():
		ns = ROOT
		path = ref.split('.')
		while len(path) > 1:
			ns = ns.attribs[path.pop(0)]
		base[name] = ns.attribs[path[0]]
	
	for k, v in mod.constants.iteritems():
		assert False, 'unimplemented'
	
	for k, v in mod.types.iteritems():
		base[k] = v
	
	for k, fun in mod.code.iteritems():
		if fun.args[0].type is None:
			assert len(k) > 1
			assert fun.args[0].name.name == 'self'
			fun.args[0].type = base[k[0]]
		process(base, fun)
