'''The escapes pass marks objects that will escape the function.

This pass exists for memory management purposes. We want to free
heap-allocated objects that do not survive the current function call, so we
must know which objects are returned to the caller or stored in an object.
This can either be a returned object, or something that was passed in that
survives this call. Escaping objects will not be freed before returning.

This data is also important for our survival analysis (yet to be implemented),
where data on survival requirements becomes part of the function type.
For example, "argument 3 must live at least as long as argument 1".
'''

from . import ast, blocks, types

class EscapeFinder(object):
	
	def __init__(self, mod, fun):
		self.mod = mod
		self.fun = fun
		self.cfg = fun.flow
		self.track = set()
		self.cur = None
	
	def visit(self, node, escape=None):
		getattr(self, node.__class__.__name__)(node, escape)
	
	# Constants
	
	def NoneVal(self, node, escape=None):
		pass
	
	def Bool(self, node, escape=None):
		pass
	
	def Int(self, node, escape=None):
		pass
	
	def Float(self, node, escape=None):
		pass
	
	def String(self, node, escape=None):
		if not escape:
			node.type = types.get('&str')
		else:
			node.escapes = True
	
	def Name(self, node, escape=None):
		if not escape: return
		self.track.add(node.name)
	
	def Tuple(self, node, escape=None):
		for n in node.values:
			self.visit(n)
	
	# Boolean operators
	
	def Not(self, node, escape=None):
		pass
	
	def And(self, node, escape=None):
		pass
	
	def Or(self, node, escape=None):
		pass
	
	# Comparison operators
	
	def Is(self, node, escape=None):
		pass
	
	def EQ(self, node, escape=None):
		pass
	
	def NE(self, node, escape=None):
		pass
	
	def LT(self, node, escape=None):
		pass
	
	def GT(self, node, escape=None):
		pass
	
	# Arithmetic operators
	
	def Add(self, node, escape=None):
		pass
		
	def Sub(self, node, escape=None):
		pass
	
	def Mod(self, node, escape=None):
		pass
	
	def Mul(self, node, escape=None):
		pass
	
	def Div(self, node, escape=None):
		pass
	
	# Bitwise operators
	
	def BWAnd(self, node, escape=None):
		pass
		
	def BWOr(self, node, escape=None):
		pass
	
	def BWXor(self, node, escape=None):
		pass
	
	def Raise(self, node, escape=None):
		self.visit(node.value, True)
	
	def Init(self, node, escape=None):
		if escape:
			node.escapes = True
	
	def As(self, node, escape=None):
		self.visit(node.left, escape)
	
	def Assign(self, node, escape=None):
		
		if isinstance(node.left, ast.Tuple):
			tracked = [n.name in self.track for n in node.left.values]
			if sum(1 if i else 0 for i in tracked) not in {0, len(tracked)}:
				assert False, 'partly tracked tuple elements'
			else:
				self.visit(node.right, all(tracked))
		elif isinstance(node.left, ast.Name):
			self.visit(node.right, node.left.name in self.track)
		elif isinstance(node.left, blocks.SetAttr):
			
			self.visit(node.left.obj)
			if not node.left.obj.escapes:
				return
			
			assert False, 'assign to escaping object'
			
		else:
			assert False
	
	def IAdd(self, node, escape=None):
		allowed = tuple(t.__class__ for t in types.INTS | types.FLOATS)
		assert isinstance(node.left.type, allowed)
	
	def Pass(self, node, escape=None):
		pass
	
	def CondBranch(self, node, escape=None):
		pass
	
	def Branch(self, node, escape=None):
		pass
	
	def Attrib(self, node, escape=None):
		assert not escape or not isinstance(node.type, types.WRAPPERS)
	
	def Elem(self, node, escape=None):
		self.Attrib(node, escape)
	
	def LoopSetup(self, node, escape=None):
		pass
	
	def LoopHeader(self, node, escape=None):
		pass
	
	def Phi(self, node, escape=None):
		self.visit(node.left[1], escape)
		self.visit(node.right[1], escape)
	
	def DeOpt(self, node, escape=None):
		self.visit(node.value, escape)
	
	def NoValue(self, node, escape=None):
		self.visit(node.value, escape)
	
	def LPad(self, node, escape=None):
		pass
	
	def Call(self, node, escape=None):
		
		if node.fun.name == 'runa.free' and self.fun.name.name == '__del__':
			return
		
		for i, arg in enumerate(node.fun.type.over[1]):
			if isinstance(arg, types.owner):
				self.visit(node.args[i], True)
				self.note(node.args[i])
			else:
				self.visit(node.args[i])
		
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
		self.note(node.value)
	
	def note(self, val):
		
		if isinstance(val, ast.String):
			return
		
		assert isinstance(val, ast.Name), val
		ls = self.cur[0].escapes.setdefault(val.name, [])
		ls.append((self.cur[1], val.type))
	
	def find(self):
		for bl in reversed(self.cfg.blocks.values()):
			for i, step in reversed(list(enumerate(bl.steps))):
				self.cur = bl, i
				self.visit(step)

def escapes(mod):
	for name, code in mod.code:
		EscapeFinder(mod, code).find()
