'''The liveness pass collects data on uses of and assignments to variables,
and stores it in the CFG's ``Block`` objects for easy reference in further
passes.

Because local types are inferred and
because no variable declarations are required,
finding the assignments that dominate any given use of a variable
isn't completely trivial.
While we can simply store pointers on the stack in many cases
during code generation in order to leave analysis to LLVM,
all the analyses we have to do
still need somewhat accurate data on variable usage.
'''

from . import ast, util

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
			self.visit(getattr(node, k))
	
	def Name(self, node):
		self.vars[0].add(node.name)
	
	def Tuple(self, node):
		for n in node.values:
			self.visit(n)
	
	def Attrib(self, node):
		self.visit(node.obj)
	
	def SetAttr(self, node):
		self.visit(node.obj)
	
	def As(self, node):
		self.visit(node.left)
	
	def LoopSetup(self, node):
		self.visit(node.loop.source)
	
	def LoopHeader(self, node):
		self.vars[1].add(node.lvar.name)
	
	def Assign(self, node):
		if isinstance(node.left, ast.Tuple):
			for n in node.left.values:
				if isinstance(n, ast.Name):
					self.vars[1].add(n.name)
				else:
					self.visit(n)
		elif isinstance(node.left, ast.Name):
			self.vars[1].add(node.left.name)
		else:
			self.visit(node.left)
		self.visit(node.right)
	
	def Call(self, node):
		self.visit(node.name)
		for arg in node.args:
			self.visit(arg)
	
	def Phi(self, node):
		self.visit(node.left[1])
		self.visit(node.right[1])

def liveness(mod):
	
	analyzer = Analyzer()
	for fname, code in mod.code:
		
		vars = code.flow.vars
		for arg in code.args:
			name = arg.name.name
			sets = vars.setdefault(name, {}).setdefault('sets', {})
			sets[None] = {-1: None}
		
		blocks = sorted(util.items(code.flow.blocks))
		for id, bl in blocks:
			
			for i, step in enumerate(bl.steps):
				
				analyzer.vars = set(), set()
				analyzer.visit(step)
				
				for name in analyzer.vars[0]:
					uses = vars.setdefault(name, {}).setdefault('uses', {})
					uses.setdefault(id, set()).add(i)
				
				for name in analyzer.vars[1]:
					sets = vars.setdefault(name, {}).setdefault('sets', {})
					sets.setdefault(id, {})[i] = None
