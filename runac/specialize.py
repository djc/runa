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
		elif node.type == types.int() and types.unwrap(dst) in types.INTS:
			if isinstance(node, ast.Int):
				dst = types.unwrap(dst)
				node.type = dst
				if not dst.signed:
					assert node.val >= 0
			else:
				assert False, (node.type, dst)
		elif isinstance(types.unwrap(dst), types.trait):
			node.type = types.get('word')
		else:
			assert False, '%s -> %s' % (node.type, dst)
	
	# Constants
	
	def Int(self, node, type=None):
		if type is not None:
			self.specialize(node, type)
	
	def Name(self, node, type=None):
		assert not isinstance(node.type, types.GENERIC)
		if type is not None:
			self.track[node.name] = type
	
	# Comparison operators
	
	def compare(self, node, type):
		if isinstance(node.left.type, types.GENERIC):
			assert not isinstance(node.right.type, types.GENERIC)
			self.visit(node.left, node.right.type)
			self.visit(node.right)
		elif isinstance(node.right.type, types.GENERIC):
			assert not isinstance(node.left.type, types.GENERIC)
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
	
	# Miscellaneous
	
	def CondBranch(self, node, type=None):
		self.visit(node.cond, types.get('ToBool'))
	
	def Assign(self, node, type=None):
		self.visit(node.right)
	
	def Attrib(self, node, type=None):
		self.visit(node.obj)
		assert not isinstance(node.type, types.GENERIC)
	
	def Return(self, node, type=None):
		if node.value is not None:
			self.visit(node.value, self.fun.rtype)
	
	def Call(self, node, type=None):
		for i, arg in enumerate(node.args):
			
			if not isinstance(arg.type, types.GENERIC):
				self.visit(arg)
				continue
			
			self.visit(arg, node.fun.type.over[1][i])
			assert not isinstance(arg.type, types.GENERIC), arg.type
	
	def Ternary(self, node, type=None):
		
		if isinstance(node.cond.type, types.GENERIC):
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
