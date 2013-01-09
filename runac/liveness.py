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
		self.vars[0].add(node.name)
	
	def Attrib(self, node):
		self.visit(node.obj)
	
	def As(self, node):
		self.visit(node.left)
	
	def Assign(self, node):
		if isinstance(node.left, ast.Name):
			self.vars[1].add(node.left.name)
		else:
			self.visit(node.left)
		self.visit(node.right)
	
	def Call(self, node):
		if isinstance(node.name, ast.Attrib):
			self.visit(node.name)
		for arg in node.args:
			self.visit(arg)

def defined(name, bl, seen):
	
	if name in bl.assigns:
		return {bl.id}
	elif not bl.preds:
		return {None}
	
	all = set()
	for p in bl.preds:
		if p.id not in seen:
			all.update(defined(name, p, seen | {bl.id}))
	
	return all

def liveness(mod):
	
	analyzer = Analyzer()
	for fname, code in mod.code:
		
		refs = {}
		for id, bl in code.flow.blocks.iteritems():
			
			bl.uses = {}
			bl.assigns = {}
			
			for i, step in enumerate(bl.steps):
				
				analyzer.vars = set(), set()
				analyzer.visit(step)
				
				for name in analyzer.vars[0]:
					bl.uses.setdefault(name, set()).add(i)
					refs.setdefault(id, []).append((i, name))
				
				for name in analyzer.vars[1]:
					bl.assigns.setdefault(name, set()).add(i)
					refs.setdefault(id, []).append((i, name))
		
		for id, bl in sorted(code.flow.blocks.iteritems()):
			
			bl.origin = {}
			for sid, name in refs.get(id, []):
				
				origin = bl.origin[name, sid] = set()
				if name in bl.assigns and min(bl.assigns[name]) < sid:
					origin.add(id)
					continue
				elif not bl.preds:
					origin.add(None)
					continue
				
				for p in bl.preds:
					origin.update(defined(name, p, set()))
