from util import Error
import ast, types, copy

class Object(object):
	def __init__(self, type, val):
		self.type = type
		self.val = val

class Function(Object):
	def __init__(self, name, rtype, atypes):
		ftype = types.function(rtype, atypes)
		Object.__init__(self, ftype, name)

class Module(object):
	def __init__(self, init):
		self.attribs = init
		self.type = types.module()
		for k, val in init.iteritems():
			if isinstance(val, Function):
				self.type.functions[k] = val.type

NS = Module({
	'__builtin__': Module({
		'u32': types.u32(),
		'byte': types.byte(),
		'bool': types.bool(),
		'False': Object(types.bool(), 0),
		'True': Object(types.bool(), 1),
	}),
	'__internal__': Module({
		'__ptr__': types.__ptr__,
		'__malloc__': Function('lang.malloc', types.__ptr__(types.byte()), (
			types.uword(),
		)),
		'__free__': Function('lang.free', types.void(), (
			types.__ptr__(types.byte()),
		)),
		'__memcpy__': Function('llvm.memcpy.p0i8.p0i8.i32', types.void(), (
			types.__ptr__(types.byte()),
			types.__ptr__(types.byte()),
			types.u32(),
			types.u32(),
			types.bool(),
		)),
	}),
	'libc': Module({
		'string': Module({
			'strncmp': Function('strncmp', types.i32(), (
				types.__ptr__(types.byte()),
				types.__ptr__(types.byte()),
				types.uword(),
			)),
		}),
	}),
})

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

class Checker(object):
	
	def __init__(self, mod, name, code):
		
		self.scope = Scope(mod.scope)
		mdata = types.ALL[name[0]].methods[name[1]]
		self.name = mdata[0]
		self.rtype = mdata[1]
		
		self.scope['self'] = types.get(name[0])
		for name, type in mdata[2]:
			self.scope[name] = type
		
		self.visit(code)
	
	def visit(self, node):
		getattr(self, node.__class__.__name__)(node)
	
	# Terminals
	
	def Bool(self, node):
		node.type = types.bool()
	
	def Int(self, node):
		node.type = types.int()
	
	def Float(self, node):
		node.type = types.float()
	
	def String(self, node):
		node.type = types.str()
	
	def Name(self, node):
		if node.name not in self.scope:
			raise Error(node, "undefined name '%s'" % node.name)
		node.type = self.scope[node.name]
	
	# Boolean operators
	
	def Not(self, node):
		node.type = types.bool()
		# XXX implements IBool?
	
	def And(self, node):
		node.type = types.bool()
		# XXX may be any IBool
	
	def Or(self, node):
		node.type = types.bool()
		# XXX may be any IBool
	
	# Arithmetic operators
	
	def math(self, op, node):
		
		self.visit(node.left)
		self.visit(node.right)
		
		if node.left.type == node.right.type:
			node.type = node.left.type
			return
		
		if node.left.type == types.int() and node.right.type in types.INTS:
			node.type = types.int()
		elif node.right.type == types.int() and node.left.type in types.INTS:
			node.type = types.int()
		else:
			assert False
	
	def Add(self, node):
		self.math('add', node)
	
	def Sub(self, node):
		self.math('sub', node)
	
	def Mul(self, node):
		self.math('mul', node)
	
	def Div(self, node):
		self.math('div', node)
	
	# Comparison operators
	
	def compare(self, op, node):
		
		self.visit(node.left)
		self.visit(node.right)
		
		if node.left.type == node.right.type:
			node.type = node.left.type
			return
		
		if node.left.type == types.int() and node.right.type in types.INTS:
			node.type = types.bool()
		elif node.right.type == types.int() and node.left.type in types.INTS:
			node.type = types.bool()
		else:
			assert False
	
	def Eq(self, node):
		self.compare('eq', node)
	
	def NEq(self, node):
		self.compare('ne', node)
	
	def LT(self, node):
		self.compare('lt', node)
	
	def GT(self, node):
		self.compare('gt', node)
	
	# Other operators
	
	def Return(self, node):
		self.visit(node.value)
		if node.value.type != self.rtype:
			bits = self.name, self.rtype.name
			msg = "%s() return type must be of type '%s'" % bits
			raise Error(node.value, msg)
	
	def Elem(self, node):
		assert False
	
	def Attrib(self, node):
		
		self.visit(node.obj)
		if node.obj.type == types.module():
			if node.attrib.name in node.obj.type.functions:
				node.type = node.obj.type.functions[node.attrib.name]
				return
			assert False
		
		if node.attrib.name in node.obj.type.attribs:
			node.type = node.obj.type.attribs[node.attrib.name][1]
			return
		
		if node.attrib.name in node.obj.type.methods:
			mdata = node.obj.type.methods[node.attrib.name]
			# XXX if node.obj is a type
			if not mdata[2] or len(mdata[2][0]) == 2:
				atypes = [('self', node.obj.type)] + mdata[2]
			else:
				atypes = [node.obj.type] + mdata[2]
			node.type = types.function(mdata[1], atypes)
			return
		
		bits = node.obj.type.name, node.attrib
		msg = "type '%s' has no attribute '%s'" % bits
		raise Error(node.attrib, msg)
	
	def Ternary(self, node):
		
		self.visit(node.values[0])
		self.visit(node.values[1])
		
		# XXX extend to LUB
		if node.values[0].type != node.values[1].type:
			bits = node.values[0].type.name, node.values[1].type.name
			raise Error(node, "unmatched types '%s', '%s'" % bits)
		
		node.type = node.values[0].type
	
	def Assign(self, node):
		
		self.visit(node.right)
		if isinstance(node.left, ast.Attrib):
			self.visit(node.left)
			if node.left.type != node.right.type:
				msg = "invalid assignment of type '%s' to type '%s'"
				bits = node.right.type.name, node.left.type.name
				raise Error(node, msg % bits)
			return
		
		self.scope[node.left.name] = node.right.type
	
	def Call(self, node):
		
		actual = []
		for arg in node.args:
			self.visit(arg)
			actual.append(arg)
		
		self.visit(node.name)
		if isinstance(node.name, ast.Attrib):
			funtype = node.name.type
			# XXX if node.name.obj is a type
			if node.name.obj.type != types.module():
				actual.insert(0, node.name.obj)
		elif not isinstance(node.name.type, types.function):
			assert isinstance(node.name.type.type, types.Type)
			mdata = node.name.type.methods['__init__']
			funtype = types.function(node.name.type, mdata[2])
			actual.insert(0, Object(node.name.type, None))
		else:
			funtype = node.name.type
		
		for form, act in zip(funtype.over[1], actual):
			
			at = act.type
			ft = form if isinstance(form, types.base) else form[1]
			if at == ft:
				continue
			
			if at in types.INTS and ft in types.INTS:
				if at == types.int():
					# XXX check for wide const value
					continue
				elif at.signed != ft.signed:
					assert False
				elif at.bits > ft.bits:
					assert False
				else:
					continue
			
			assert False
		
		node.type = funtype.over[0]
	
	# Block statements
	
	def Suite(self, node):
		for stmt in node.stmts:
			val = self.visit(stmt)
			if val is None: continue
			self.push(val)
	
	def If(self, node):
		pass
	
	def While(self, node):
		pass
	
	def For(self, node):
		pass

def resolve(base, name):
	if base:
		return NS.attribs[base].attribs[name]
	else:
		return NS.attribs[name]

class Module(object):
	
	def __init__(self, node):
		self.scope = Scope(NS.attribs['__builtin__'].attribs)
		self.build(node)

	def build(self, node):
		
		bodies = {}
		for n in node.suite:
			
			if isinstance(n, ast.RelImport):
				for name in n.names:
					obj = resolve(n.base.name, name.name)
					self.scope[name.name] = obj.type
			
			elif isinstance(n, ast.Class):
				t = self.scope[n.name.name] = types.add(n)
				for m in n.methods:
					bodies[(t.name, m.name.name)] = m.suite
		
		for name, code in bodies.iteritems():
			Checker(self, name, code)
