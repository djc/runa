import ast, types, ti

GENERIC = {types.int(), types.float()}

class Specializer(object):
	
	def __init__(self, mod, cfg):
		self.mod = mod
		self.cfg = cfg
	
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
	
	def Name(self, node):
		assert node.type not in GENERIC
	
	def Attrib(self, node):
		self.visit(node.obj)
		assert node.type not in GENERIC
	
	def Return(self, node):
		self.visit(node.value)
	
	def specialize(self, node, dst):
		if node.type == types.int() and dst in types.INTS:
			if isinstance(node, ast.Int):
				node.type = dst
				if not dst.signed:
					assert node.val >= 0
			else:
				assert False
		else:
			assert False
	
	def compare(self, node):
		if node.left.type in GENERIC:
			assert node.right.type not in GENERIC
			self.specialize(node.left, node.right.type)
		elif node.right.type in GENERIC:
			assert node.left.type not in GENERIC
			self.specialize(node.right, node.left.type)
	
	def Eq(self, node):
		self.compare(node)
	
	def GT(self, node):
		self.compare(node)
	
	def LT(self, node):
		self.compare(node)
	
	def Call(self, node):
		
		assert node.type not in GENERIC
		if hasattr(node.name, 'type'):
			ftype = node.name.type
		else:
			ftype = ti.resolve(self.mod, node.name.name).type
		
		for i, arg in enumerate(node.args):
			if arg.type not in GENERIC: continue
			self.specialize(arg, ftype.over[1][i])
			assert arg.type not in GENERIC
	
	def propagate(self):
		for i, bl in self.cfg.blocks.iteritems():
			for step in bl.steps:
				self.visit(step)

def specialize(mod):
	for name, code in mod.code:
		Specializer(mod, code.flow).propagate()
