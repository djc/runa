import ast, blocks, types

class EscapeFinder(object):
	
	def __init__(self, mod, fun):
		self.mod = mod
		self.fun = fun
		self.cfg = fun.flow
		self.track = set()
	
	def visit(self, node, escape=None):
		getattr(self, node.__class__.__name__)(node, escape)
	
	def String(self, node, escape=None):
		if not escape:
			node.type = types.get('&str')
		else:
			node.escapes = True
	
	def Name(self, node, escape=None):
		if not escape: return
		self.track.add(node.name)
	
	def Yield(self, node, escape=None):
		self.visit(node.value, True)
	
	def Assign(self, node, escape=None):
		
		if isinstance(node.left, ast.Name):
			
			if node.left.name not in self.track:
				return
			
			self.visit(node.right, True)
		
		elif isinstance(node.left, blocks.SetAttr):
			
			self.visit(node.left.obj)
			if not node.left.obj.escapes:
				return
			
			assert False, 'assign to escaping object'
			
		else:
			assert False
	
	def Ternary(self, node, escape=None):
		for val in node.values:
			self.visit(val, escape)
	
	def CondBranch(self, node, escape=None):
		pass
	
	def Branch(self, node, escape=None):
		pass
	
	def Attrib(self, node, escape=None):
		assert not escape or not isinstance(node.type, types.WRAPPERS)
	
	def LoopHeader(self, node, escape=None):
		pass
	
	def Phi(self, node, escape=None):
		self.visit(node.left[1], escape)
		self.visit(node.right[1], escape)
	
	def Call(self, node, escape=None):
		
		if node.fun.name == 'runa.free' and self.fun.name.name == '__del__':
			return
		
		for i, arg in enumerate(node.fun.type.over[1]):
			if not isinstance(arg, types.owner): continue
			self.visit(node.args[i], True)
		
		if not escape:
			return
		
		if node.fun.name == 'runa.malloc':
			node.escapes = True
			return
		
		if node.fun.name.endswith('.__init__'):
			node.args[0].escapes = True
	
	def Yield(self, node, escape=None):
		self.Return(node, escape)
	
	def Return(self, node, escape=None):
		if node.value is None:
			return
		if not isinstance(node.value.type, types.owner):
			return
		self.visit(node.value, True)
	
	def find(self):
		for i, bl in reversed(self.cfg.blocks.items()):
			for step in reversed(bl.steps):
				self.visit(step)

def escapes(mod):
	for name, code in mod.code:
		EscapeFinder(mod, code).find()
