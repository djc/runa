import ast, types

class Specializer(object):
	
	def __init__(self, mod, fun):
		self.mod = mod
		self.fun = fun
		self.cfg = fun.flow
	
	def visit(self, node):
		
		if hasattr(self, node.__class__.__name__):
			getattr(self, node.__class__.__name__)(node)
			return
		
		for k in node.fields:
			attr = getattr(node, k)
			if isinstance(attr, list):
				for v in attr:
					self.visit(v)
			else:
				self.visit(attr)
	
	def specialize(self, node, dst):
		if not isinstance(node.type, types.GENERIC):
			return
		elif node.type == types.int() and dst in types.INTS:
			if isinstance(node, ast.Int):
				node.type = dst
				if not dst.signed:
					assert node.val >= 0
			else:
				assert False
		elif isinstance(types.unwrap(dst), types.trait):
			node.type = types.get('word')
		else:
			assert False, '%s -> %s' % (node.type, dst)
	
	# Constants
	
	def Name(self, node):
		assert not isinstance(node.type, types.GENERIC)
	
	# Comparison operators
	
	def compare(self, node):
		if isinstance(node.left.type, types.GENERIC):
			assert not isinstance(node.right.type, types.GENERIC)
			self.specialize(node.left, node.right.type)
		elif isinstance(node.right.type, types.GENERIC):
			assert not isinstance(node.left.type, types.GENERIC)
			self.specialize(node.right, node.left.type)
	
	def EQ(self, node):
		self.compare(node)
	
	def NE(self, node):
		self.compare(node)
	
	def LT(self, node):
		self.compare(node)
	
	def GT(self, node):
		self.compare(node)
	
	def Attrib(self, node):
		self.visit(node.obj)
		assert not isinstance(node.type, types.GENERIC)
	
	def Return(self, node):
		
		if node.value is None:
			return
		
		self.visit(node.value)
		self.specialize(node.value, self.fun.rtype)
	
	def Call(self, node):
		for i, arg in enumerate(node.args):
			if not isinstance(arg.type, types.GENERIC): continue
			self.specialize(arg, node.fun.type.over[1][i])
			assert not isinstance(arg.type, types.GENERIC)
	
	def propagate(self):
		for i, bl in self.cfg.blocks.iteritems():
			for step in bl.steps:
				self.visit(step)

def specialize(mod):
	for name, code in mod.code:
		Specializer(mod, code).propagate()
