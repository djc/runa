import ast

class Analyzer(object):
	
	def __init__(self):
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
	
def liveness(mod):
	
	analyzer = Analyzer()
	for name, code in mod.code:
		
		for id, bl in code.flow.blocks.iteritems():
			
			bl.uses = {}
			bl.assigns = {}
			
			for i, step in enumerate(bl.steps):
				
				analyzer.vars = {}, {}
				analyzer.visit(step)
				
				for name, node in analyzer.vars[0].iteritems():
					bl.uses.setdefault(name, set()).add(i)
				
				for name, node in analyzer.vars[1].iteritems():
					bl.assigns.setdefault(name, set()).add(i)
