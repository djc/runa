'''Specialize any* types and traits, where necessary.
Propagate type information so that imprecisely typed variables
get a concrete type.
In cases where no specific information is available for number types,
we just pick ``int`` (word-sized) or ``float`` (C double, so 64 bits).

TODO: Rust has changed their defaults a number of times. Read up on
http://discuss.rust-lang.org/t/restarting-the-int-uint-discussion/1131,
see if it makes sense to change int to be ``i32``. Currently, we only have
a single float type; it seems like ``float`` == ``f64`` might make sense.
'''

from . import ast, types, util

class Specializer(object):
	
	def __init__(self, mod, fun):
		self.mod = mod
		self.fun = fun
		self.cfg = fun.flow
		self.track = {}
	
	def visit(self, node, type=None):
		getattr(self, node.__class__.__name__)(node, type)
	
	def specialize(self, node, dst):
		if node.type == dst:
			return
		elif node.type == types.anyint() and dst is None:
			node.type = self.mod.type('int')
		elif node.type == types.anyfloat() and dst is None:
			node.type = self.mod.type('float')
		elif dst is None:
			return
		elif node.type == types.anyint() and types.unwrap(dst) in types.INTS:
			if isinstance(node, ast.Int):
				dst = types.unwrap(dst)
				node.type = dst
				if not dst.signed:
					assert int(node.val) >= 0
			else:
				assert False, (node.type, dst)
		elif node.type == types.anyfloat() and types.unwrap(dst) in types.FLOATS:
			if isinstance(node, ast.Float):
				node.type = types.unwrap(dst)
			else:
				assert False, (node.type, dst)
		elif isinstance(dst, types.concrete):
			ttypes = []
			for i, e in enumerate(node.type.params):
				assert types.compat(e, dst.params[i])
				ttypes.append(dst.params[i])
			node.type = self.mod.type(('tuple', ttypes))
		elif isinstance(types.unwrap(dst), types.trait):
			if node.type == types.anyint():
				node.type = self.mod.type('int')
			elif node.type == types.anyfloat():
				node.type = self.mod.type('float')
			else:
				assert False, 'specialize %s to trait' % node.type
		else:
			assert False, '%s -> %s' % (node.type, dst)
	
	def binspec(self, node, type):
		if types.generic(node.left.type) and types.generic(node.right.type):
			self.visit(node.left)
			self.visit(node.right)
		elif types.generic(node.left.type):
			self.visit(node.left, node.right.type)
			self.visit(node.right)
		elif types.generic(node.right.type):
			self.visit(node.right, node.left.type)
			self.visit(node.left)
	
	# Constants
	
	def NoneVal(self, node, type=None):
		pass
	
	def Bool(self, node, type=None):
		pass
	
	def Int(self, node, type=None):
		self.specialize(node, type)
	
	def Float(self, node, type=None):
		self.specialize(node, type)
	
	def String(self, node, type=None):
		pass
	
	def Name(self, node, type=None):
		
		params = []
		if hasattr(node.type, 'params'):
			params = [types.generic(t) for t in node.type.params]
		
		if not types.generic(node.type) and not any(params):
			return
		else:
			self.specialize(node, type)
	
	def Tuple(self, node, type=None):
		ttypes = [None] * len(node.values) if type is None else type.params
		for i, e in enumerate(node.values):
			if types.generic(e.type):
				self.specialize(e, ttypes[i])
		node.type = self.mod.type(('tuple', (n.type for n in node.values)))
	
	def Init(self, node, type=None):
		pass
	
	# Boolean operators
	
	def Not(self, node, type=None):
		self.specialize(node.value, None)
	
	def And(self, node, type=None):
		self.specialize(node.left, None)
		self.specialize(node.right, None)
	
	def Or(self, node, type=None):
		self.specialize(node.left, None)
		self.specialize(node.right, None)
	
	# Comparison operators
	
	def Is(self, node, type):
		self.binspec(node, type)
	
	def compare(self, node, type):
		self.binspec(node, type)
	
	def EQ(self, node, type=None):
		self.compare(node, type)
	
	def NE(self, node, type=None):
		self.compare(node, type)
	
	def LT(self, node, type=None):
		self.compare(node, type)
	
	def GT(self, node, type=None):
		self.compare(node, type)
	
	# Arithmetic operators
	
	def arith(self, op, node, type):
		self.binspec(node, type)
		assert node.left.type == node.right.type
		node.type = node.left.type
	
	def Add(self, node, type=None):
		self.arith('add', node, type)
	
	def Sub(self, node, type=None):
		self.arith('sub', node, type)
	
	def Mod(self, node, type=None):
		self.arith('mod', node, type)
	
	def Mul(self, node, type=None):
		self.arith('mul', node, type)
	
	def Div(self, node, type=None):
		self.arith('div', node, type)
	
	# Bitwise operators
	
	def bitwise(self, op, node, type):
		self.binspec(node, type)
	
	def BWAnd(self, node, type=None):
		self.bitwise('and', node, type)
	
	def BWOr(self, node, type=None):
		self.bitwise('or', node, type)
	
	def BWXor(self, node, type=None):
		self.bitwise('xor', node, type)
	
	# Miscellaneous
	
	def Pass(self, node, type=None):
		pass
	
	def LPad(self, node, type=None):
		pass
	
	def Resume(self, node, type=None):
		pass
	
	def As(self, node, type=None):
		if types.generic(node.left.type):
			self.visit(node.left, node.type)
		else:
			self.visit(node.left)
	
	def LoopSetup(self, node, type=None):
		self.visit(node.loop.source, type)
	
	def LoopHeader(self, node, type=None):
		self.visit(node.lvar, self.track.get(node.lvar.name))
	
	def CondBranch(self, node, type=None):
		self.visit(node.cond, self.mod.type('ToBool'))
	
	def Assign(self, node, type=None):
		if isinstance(node.left, ast.Name):
			self.visit(node.right, self.track.get(node.left.name))
		else:
			self.visit(node.right, node.left.type)
	
	def IAdd(self, node, type=None):
		if isinstance(node.left, ast.Name):
			self.visit(node.right, self.track.get(node.left.name))
		else:
			self.visit(node.right, node.left.type)
	
	def Elem(self, node, type=None):
		self.visit(node.obj)
		self.visit(node.key)
		# TODO: should specialize key type
		assert not types.generic(node.type)
	
	def Attrib(self, node, type=None):
		self.visit(node.obj)
		assert not types.generic(node.type)
	
	def SetAttr(self, node, type=None):
		self.Attrib(node, type)
	
	def Return(self, node, type=None):
		if node.value is not None:
			self.visit(node.value, self.fun.rtype)
	
	def Yield(self, node, type=None):
		if node.value is not None:
			self.visit(node.value, self.fun.rtype.params[0])
	
	def Call(self, node, type=None):
		for i, arg in enumerate(node.args):
			
			if not types.generic(arg.type):
				self.visit(arg)
				continue
			
			self.visit(arg, node.fun.type.over[1][i])
			if not isinstance(arg, ast.Name):
				assert not types.generic(arg.type), arg.type
	
	def Phi(self, node, type=None):
		
		self.visit(node.left[1], type)
		self.visit(node.right[1], type)
		
		if node.left[1].type == node.right[1].type:
			node.type = node.left[1].type
			return
		
		if node.left[1].type == self.mod.type('NoType'):
			assert node.type == types.opt(node.right[1].type)
			node.left[1].type = node.type
			return
		elif node.right[1].type == self.mod.type('NoType'):
			assert node.type == types.opt(node.left[1].type)
			node.right[1].type = node.type
			return
		
		assert False, (node.left[1].type, node.right[1].type)
	
	def Branch(self, node, type=None):
		pass
	
	def Raise(self, node, type=None):
		pass
	
	def propagate(self):
		for i, bl in util.items(self.cfg.blocks):
			for step in reversed(bl.steps):
				self.visit(step)

def specialize(mod):
	for name, code in mod.code:
		Specializer(mod, code).propagate()
