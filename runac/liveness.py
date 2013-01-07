import ast

class Analyzer(object):
	
	def __init__(self, fun):
		self.fun = fun
		self.flow = fun.flow
		self.vars = None
		
	def visit(self, node):
		
		if node is None:
			return
		
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
		self.vars[0][node.name] = node
	
	def Attrib(self, node):
		self.visit(node.obj)
	
	def As(self, node):
		self.visit(node.left)
	
	def Assign(self, node):
		if isinstance(node.left, ast.Name):
			self.vars[1][node.left.name] = node
		else:
			self.visit(node.left)
		self.visit(node.right)
	
	def analyze(self):
		for id, bl in self.fun.flow.blocks.iteritems():
			bl.uses = {}
			bl.assigns = {}
			for i, step in enumerate(bl.steps):
				self.vars = {}, {}
				self.visit(step)
				for name, node in self.vars[0].iteritems():
					bl.uses.setdefault(name, set()).add(i)
				for name, node in self.vars[1].iteritems():
					bl.assigns.setdefault(name, set()).add(i)

def liveness(mod):
	for name, code in mod.code:
		Analyzer(code).analyze()
