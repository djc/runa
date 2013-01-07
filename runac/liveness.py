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
			
			used = []
			defined = {}
			for i, step in enumerate(bl.steps):
				
				self.vars = {}, {}
				self.visit(step)
				used.append(self.vars[0])
				
				for name, node in self.vars[1].iteritems():
					defined.setdefault(name, []).append((i, node))
			
			bl.needs = set()
			for i, step in enumerate(used):
				for name, node in step.iteritems():
					
					if name not in defined:
						bl.needs.add(name)
						continue
					
					first = sorted(defined[name])[0][0]
					if first >= i:
						bl.needs.add(name)
			
			bl.assigns = set(defined)

def liveness(mod):
	for name, code in mod.code:
		Analyzer(code).analyze()
