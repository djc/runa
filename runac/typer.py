import types, ast, blocks, util

class Object(object):
	
	def __init__(self, type, val=None):
		self.type = type
		self.val = val
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%r' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

class Init(ast.Expr):
	def __init__(self, type):
		ast.Expr.__init__(self, None)
		self.type = type

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

class Decl(object):
	
	def __init__(self, name, rtype, atypes):
		self.decl = name
		self.rtype = rtype
		self.atypes = atypes
	
	def __repr__(self):
		name = self.__class__.__name__
		atypes = ', '.join(self.atypes)
		return '<%s(%r, %s, (%s))>' % (name, self.decl, self.rtype, atypes)
	
	def realize(self):
		rtype = types.get(self.rtype)
		atypes = [types.get(t) for t in self.atypes]
		return Function(self.decl, types.function(rtype, atypes))

ROOT = Module('', {
	'__internal__': Module('__internal__', {
		'__malloc__': Decl('runa.malloc', '$byte', ('uint',)),
		'__free__': Decl('runa.free', 'void', ('$byte',)),
		'__memcpy__': Decl('runa.memcpy', 'void', ('&byte', '&byte', 'u32')),
		'__offset__': Decl('runa.offset', '&byte', ('&byte', 'uint')),
	}),
	'libc': Module('libc', {
		'stdio': Module('libc.stdio', {
			'snprintf': Decl('snprintf', 'i32', (
				'&byte', 'i32', '&byte', '...'
			)),
		}),
		'string': Module('libc.string', {
			'strncmp': Decl('strncmp', 'i32', ('&byte', '&byte', 'uint')),
		}),
		'unistd': Module('libc.unistd', {
			'write': Decl('write', 'int', ('i32', '&byte', 'uint')),
		}),
	}),
})

def resolve(mod, n):
	parts = n.split('.')
	if parts[0] in mod.scope:
		return mod.scope[parts[0]]
	elif parts[0] in ROOT:
		obj = ROOT
		for p in parts:
			obj = obj[p]
		return obj
	elif parts[0] in mod.names:
		method = mod.names[parts[0]].methods[parts[1]]
		return Function(method[0], types.function(method[1], method[2]))
	elif parts[0] in types.ALL:
		method = types.get(parts[0]).methods[parts[1]]
		return Function(method[0], types.function(method[1], method[2]))
	else:
		assert False, 'cannot resolve %s' % (tuple(parts),)

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
		if isinstance(node, ast.Name) and node.name not in self:
			raise util.Error(node, "type '%s' not found" % node.name)
		if isinstance(node, ast.Name):
			assert self[node.name].type == types.Type()
			return self[node.name]
		elif isinstance(node, ast.Elem):
			inner = self.resolve(node.key)
			return self[node.obj.name][inner]
		elif isinstance(node, ast.Ref):
			return types.ref(self.resolve(node.value))
		elif isinstance(node, ast.Owner):
			return types.owner(self.resolve(node.value))
		else:
			assert False

class TypeChecker(object):
	
	def __init__(self, fun):
		self.fun = fun
		self.flow = fun.flow
		self.scopes = {}
		self.cur = None
	
	def check(self, scope):
		self.scopes[None] = scope
		for i, b in sorted(self.flow.blocks.iteritems()):
			
			self.cur = b
			scope = Scope(self.scopes[b.preds[0] if b.preds else None])
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
	
	# Constants
	
	def Name(self, node, scope):
		if node.name not in scope:
			raise util.Error(node, "undefined name '%s'" % node.name)
		node.type = scope[node.name].type
		self.cur.uses.add(node.name)
	
	def Bool(self, node, scope):
		node.type = scope['bool']
	
	def Int(self, node, scope):
		node.type = types.anyint()
	
	def Float(self, node, scope):
		node.type = types.anyfloat()
	
	def String(self, node, scope):
		node.type = types.ref(scope['str'])
	
	# Boolean operators
	
	def boolean(self, op, node, scope):
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		if node.left.type == node.right.type:
			node.type = node.left.type
		else:
			node.type = scope['bool']
	
	def And(self, node, scope):
		self.boolean('and', node, scope)
	
	def Or(self, node, scope):
		self.boolean('or', node, scope)
	
	# Comparison operators
	
	def compare(self, op, node, scope):
		
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		
		lt, rt = types.unwrap(node.left.type), types.unwrap(node.right.type)
		if node.left.type == node.right.type:
			node.type = scope['bool']
		elif lt in types.INTS and rt not in types.INTS:
			msg = "value of type '%s' may only be compared to integer type"
			raise util.Error(node, msg % node.left.type.name)
		elif lt in types.FLOATS and rt not in types.FLOATS:
			msg = "value of type '%s' may only be compared to float type"
			raise util.Error(node, msg % node.left.type.name)
		elif lt not in types.INTS and lt not in types.FLOATS:
			assert False, '%s sides different types (%s, %s)' % (op, lt, rt)
		
		node.type = scope['bool']
	
	def EQ(self, node, scope):
		self.compare('eq', node, scope)
	
	def NE(self, node, scope):
		self.compare('ne', node, scope)
	
	def LT(self, node, scope):
		self.compare('lt', node, scope)
	
	def GT(self, node, scope):
		self.compare('gt', node, scope)
	
	# Arithmetic operators
	
	def arith(self, op, node, scope):
		self.visit(node.left, scope)
		self.visit(node.right, scope)
		if node.left.type == node.right.type:
			node.type = node.left.type
		else:
			assert False, op + ' sides different types'
	
	def Add(self, node, scope):
		self.arith('add', node, scope)
	
	def Sub(self, node, scope):
		self.arith('sub', node, scope)
	
	def Mul(self, node, scope):
		self.arith('mul', node, scope)
	
	def Div(self, node, scope):
		self.arith('div', node, scope)
	
	def As(self, node, scope):
		self.visit(node.left, scope)
		node.type = scope[node.right.name]
	
	def Attrib(self, node, scope):
		
		self.visit(node.obj, scope)
		t = node.obj.type
		if isinstance(t, types.WRAPPERS):
			t = t.over
		
		node.type = t.attribs[node.attrib.name][1]
		assert node.type is not None, 'FAIL'
	
	def Call(self, node, scope):
		
		actual = []
		for arg in node.args:
			self.visit(arg, scope)
			actual.append(arg.type)
		
		if isinstance(node.name, ast.Attrib):
			
			self.visit(node.name.obj, scope)
			if node.name.obj.type == types.module():
				
				mod = scope[node.name.obj.name]
				fun = mod.type.functions[node.name.attrib.name]
				qual = mod.name + '.' + node.name.attrib.name
				node.fun = Function(qual, fun)
				node.type = fun.over[0]
				
			else:
				
				t = types.unwrap(node.name.obj.type)
				if isinstance(t, types.trait):
					node.virtual = True
				
				meth = t.methods[node.name.attrib.name]
				node.args.insert(0, node.name.obj)
				actual = [a.type for a in node.args]
				mtype = types.function(meth[1], [i[1] for i in meth[2]])
				node.fun = Function(meth[0], mtype)
				node.type = mtype.over[0]
			
			if not types.compat(actual, node.fun.type.over[1]):
				assert False
			
			return
		
		assert isinstance(node.name, ast.Name), 'call non-{attrib,name,type}'
		if node.name.name not in scope:
			msg = "function '%s' not found"
			raise util.Error(node.name, msg % node.name.name)
		
		obj = scope[node.name.name]
		if not isinstance(obj, types.base):
			
			node.fun = obj
			node.type = node.fun.type.over[0]
			if not types.compat(actual, node.fun.type.over[1]):
				astr = ', '.join(t.name for t in actual)
				fstr = ', '.join(t.name for t in node.fun.type.over[1])
				msg = 'arguments (%s) cannot be passed as (%s)'
				raise util.Error(node, msg % (astr, fstr))
		
		else:
			
			methods = []
			if '__init__' in obj.methods:
				methods.append(obj.methods['__init__'])
			if '__new__' in obj.methods:
				methods.append(obj.methods['__new__'])
			
			res = []
			for decl, rt, args in methods:
				
				tmp = actual
				if '__init__' in decl:
					tmp = [types.owner(obj)] + actual
				
				formal = [a[1] for a in args]
				if types.compat(tmp, formal):
					res.append((decl, rt, args))
			
			if not res:
				
				formals = []
				for t in methods:
					formals.append(', '.join(i[1].name for i in t[2]))
				
				astr = ', '.join(t.name for t in actual)
				bits = astr, '), ('.join(formals)
				msg = '(%s) does not fit any of (%s)'
				raise util.Error(node, msg % bits)
			
			assert len(res) == 1, res
			method = res[0]
			node.name.name = method[0]
			
			mtype = types.function(method[1], [i[1] for i in method[2]])
			node.fun = Function(method[0], mtype)
			node.type = types.owner(obj)
			if '__init__' in method[0]:
				node.args.insert(0, Init(types.owner(obj)))
		
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
		
		name = node.left.name
		self.visit(node.right, scope)
		if name in scope and scope[name].type != node.right.type:
			assert False, 'reassignment'
		
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
			bits = tuple(i.type.name for i in node.values)
			raise util.Error(node, "unmatched types '%s', '%s'" % bits)
	
	def Return(self, node, scope):
		
		if node.value is None and self.fun.rtype != types.void():
			msg = "function may not return value of type 'void'"
			raise util.Error(node, msg)
		elif node.value is None:
			return
		
		self.visit(node.value, scope)
		if node.value.type == self.fun.rtype:
			return
		elif isinstance(node.value.type, types.anyint):
			assert self.fun.rtype in types.INTS
		else:
			msg = "return value does not match declared return type '%s'"
			raise util.Error(node.value, msg % self.fun.rtype.name)

def variant(mod, t):
	if isinstance(t, types.WRAPPERS):
		variant(mod, t.over)
	elif hasattr(t, 'over') or isinstance(t, types.concrete):
		mod.variants.add(t)

VOID = {'__init__', '__del__'}

def process(mod, base, fun):
	
	if fun.name.name in VOID and fun.rtype is not None:
		msg = "method '%s' must return type 'void'"
		raise util.Error(fun.rtype, msg % fun.name.name)
	
	start = Scope(base)
	if fun.rtype is None:
		fun.rtype = types.void()
	if not isinstance(fun.rtype, types.base):
		fun.rtype = start.resolve(fun.rtype)
		variant(mod, fun.rtype)
	
	for arg in fun.args:
		if not isinstance(arg.type, types.base):
			arg.type = start.resolve(arg.type)
		start[arg.name.name] = Object(arg.type)
		variant(mod, arg.type)
	
	checker = TypeChecker(fun)
	checker.check(start)

def typer(mod):
	
	for k, v in mod.names.iteritems():
		if isinstance(v, (ast.Class, ast.Trait)):
			types.add(v)
	
	base = Scope()
	for name, obj in mod.names.iteritems():
		
		if not isinstance(obj, basestring):
			continue
		
		ns = ROOT
		path = obj.split('.')
		while len(path) > 1:
			ns = ns.attribs[path.pop(0)]
		
		val = ns.attribs[path[0]]
		base[name] = val.realize() if isinstance(val, Decl) else val
		mod.names[name] = base[name]
	
	for k, v in mod.names.iteritems():
		if not isinstance(v, blocks.Constant):
			continue
		if isinstance(v.node, ast.String):
			v.node.type = types.get('&str')
		elif isinstance(v.node, ast.Int):
			v.node.type = types.get('&int')
		else:
			assert False, v.node
		base[k] = v.node
	
	for k, v in mod.names.iteritems():
		if isinstance(v, (ast.Class, ast.Trait)):
			base[k] = mod.names[k] = types.fill(v)
	
	for k, fun in mod.code:
		
		if not isinstance(k, basestring):
			continue
		
		rtype = types.void() if fun.rtype is None else base.resolve(fun.rtype)
		atypes = [base.resolve(a.type) for a in fun.args]
		type = types.function(rtype, atypes)
		base[fun.name.name] = Function(fun.name.name, type)
		
		if k == 'main' and atypes and atypes[0] != types.ref(base['str']):
			msg = '1st argument to main() must be of type &str'
			raise util.Error(fun.args[0].type, msg)
		
		compare = types.ref(base['array'][base['str']])
		if k == 'main' and atypes and atypes[1] != compare:
			msg = '2nd argument to main() must be of type &array[str]'
			raise util.Error(fun.args[1].type, msg)
		
		if k == 'main' and rtype not in {types.void(), base['i32']}:
			raise util.Error(fun, 'main() return type must be i32')
	
	mod.scope = base
	for k, fun in mod.code:
		
		if isinstance(k, tuple) and k[1] != '__new__':
			if not fun.args:
				raise util.Error(fun, "missing 'self' argument")
			elif fun.args[0].name.name != 'self':
				msg = "first method argument must be called 'self'"
				raise util.Error(fun.args[0], msg)
			elif fun.args[0].type is not None:
				if fun.args[0].type.name != k[0]:
					msg = "first method argument must be of type '%s'"
					raise util.Error(fun.args[0].type, msg % k[0])
		
		if fun.args and fun.args[0].type is None:
			if fun.name.name == '__del__':
				fun.args[0].type = types.owner(base[k[0]])
			else:
				fun.args[0].type = types.ref(base[k[0]])
		
		process(mod, base, fun)
