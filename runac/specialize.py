import ast, types

class Specializer(object):
	
	def __init__(self, mod, fun):
		self.mod = mod
		self.fun = fun
		self.cfg = fun.flow
		self.track = {}
	
	def visit(self, node, type=None):
		if hasattr(self, node.__class__.__name__):
			getattr(self, node.__class__.__name__)(node, type)
	
	def specialize(self, node, dst):
		if node.type == dst:
			return
		elif node.type == types.anyint() and dst is None:
			node.type = types.get('int')
		elif node.type == types.anyfloat() and dst is None:
			node.type = types.get('float')
		elif node.type == types.anyint() and types.unwrap(dst) in types.INTS:
			if isinstance(node, ast.Int):
				dst = types.unwrap(dst)
				node.type = dst
				if not dst.signed:
					assert node.val >= 0
			else:
				assert False, (node.type, dst)
		elif node.type == types.anyfloat() and types.unwrap(dst) in types.FLOATS:
			if isinstance(node, ast.Float):
				node.type = types.unwrap(dst)
			else:
				assert False, (node.type, dst)
		elif isinstance(types.unwrap(dst), types.trait):
			if node.type == types.anyint():
				node.type = types.get('int')
			elif node.type == types.anyfloat():
				node.type = types.get('float')
			else:
				assert False, 'specialize %s to trait' % node.type
		else:
			assert False, '%s -> %s' % (node.type, dst)
	
	# Constants
	
	def Int(self, node, type=None):
		self.specialize(node, type)
	
	def Float(self, node, type=None):
		self.specialize(node, type)
	
	def Name(self, node, type=None):
		if not types.generic(node.type):
			return
		elif isinstance(types.unwrap(type), types.trait):
			self.specialize(node, type)
		elif type is not None:
			self.track[node.name] = type
		else:
			self.specialize(node, type)
	
	# Comparison operators
	
	def compare(self, node, type):
		if types.generic(node.left.type) and types.generic(node.right.type):
			self.visit(node.left)
			self.visit(node.right)
		elif types.generic(node.left.type):
			self.visit(node.left, node.right.type)
			self.visit(node.right)
		elif types.generic(node.right.type):
			self.visit(node.right, node.left.type)
			self.visit(node.left)
	
	def EQ(self, node, type=None):
		self.compare(node, type)
	
	def NE(self, node, type=None):
		self.compare(node, type)
	
	def LT(self, node, type=None):
		self.compare(node, type)
	
	def GT(self, node, type=None):
		self.compare(node, type)
	
	# Arithmetic operators
	
	def arith(self, op, node, type):
		self.visit(node.left, type)
		self.visit(node.right, type)
		assert node.left.type == node.right.type
		node.type = node.left.type
	
	def Add(self, node, type=None):
		self.arith('add', node, type)
	
	def Sub(self, node, type=None):
		self.arith('sub', node, type)
	
	def Mul(self, node, type=None):
		self.arith('mul', node, type)
	
	def Div(self, node, type=None):
		self.arith('div', node, type)
	
	# Miscellaneous
	
	def CondBranch(self, node, type=None):
		self.visit(node.cond, types.get('ToBool'))
	
	def Assign(self, node, type=None):
		if isinstance(node.left, ast.Name):
			self.visit(node.right, self.track.get(node.left.name))
	
	def Attrib(self, node, type=None):
		self.visit(node.obj)
		assert not types.generic(node.type)
	
	def Return(self, node, type=None):
		if node.value is not None:
			self.visit(node.value, self.fun.rtype)
	
	def Call(self, node, type=None):
		for i, arg in enumerate(node.args):
			
			if not types.generic(arg.type):
				self.visit(arg)
				continue
			
			self.visit(arg, node.fun.type.over[1][i])
			if not isinstance(arg, ast.Name):
				assert not types.generic(arg.type), arg.type
	
	def Ternary(self, node, type=None):
		
		if types.generic(node.cond.type):
			self.visit(node.cond, types.get('ToBool'))
		
		self.visit(node.values[0], type)
		self.visit(node.values[1], type)
		assert node.values[0].type == node.values[1].type
		node.type = node.values[0].type
	
	def propagate(self):
		for i, bl in self.cfg.blocks.iteritems():
			for step in reversed(bl.steps):
				self.visit(step)

def specialize(mod):
	for name, code in mod.code:
		Specializer(mod, code).propagate()
