'''The blocks phase turns an AST into a set of CFGs. Nested expressions are
moved into temporary variables to make subsequent passes possible.

A new ``Module`` object is created to contain a mapping
from names to language-level things:
an object imported from another module,
a class,
a function,
a trait or a constant.
Both functions and class methods are appended to a list of code objects,
represented as a tuple of a name and a ``FlowGraph`` object.
The ``FlowGraph`` object represents a directed graph of ``Block`` objects,
which will end up as a basic block in LLVM IR.

The construction of flow graphs is done by the ``FlowFinder`` class,
which is structured as a syntax tree walking class.
The important functionality here is the deconstruction of nested expressions
into temporary variables (see the ``inter()`` method)
and the transformation of the various source-level flow control features
into a control flow graph of basic blocks.
'''

from . import ast, util, types

class SetAttr(ast.Attrib):
	pass

class Branch(util.AttribRepr):
	fields = ()
	def __init__(self, target):
		self.label = target

class CondBranch(util.AttribRepr):
	fields = ('cond',)
	def __init__(self, cond, tg1, tg2):
		self.cond = cond
		self.tg1 = tg1
		self.tg2 = tg2

class Phi(util.AttribRepr):
	fields = ()
	def __init__(self, pos, left, right):
		self.pos = pos
		self.left = left
		self.right = right
		self.type = None

class Constant(object):
	def __init__(self, node):
		self.node = node

class LoopSetup(util.AttribRepr):
	fields = 'loop',
	def __init__(self, loop):
		self.loop = loop
		self.type = None

class LoopHeader(util.AttribRepr):
	fields = 'ctx', 'lvar'
	def __init__(self, ctx, lvar, tg1, tg2):
		self.ctx = ctx
		self.lvar = lvar
		self.tg1 = tg1
		self.tg2 = tg2

class LPad(util.AttribRepr):
	fields = ()
	def __init__(self, map):
		self.map = map

class Block(util.AttribRepr):
	
	def __init__(self, id, anno=None):
		self.id = id
		self.anno = anno
		self.returns = False
		self.raises = False
		self.steps = []
		self.preds = []
		self.assigns = None
		self.uses = None
		self.escapes = {}
		self.checks = {}
	
	def push(self, inst):
		self.steps.append(inst)
	
	def needbranch(self):
		return not self.steps or not isinstance(self.steps[-1], ast.Return)

class FlowGraph(util.AttribRepr):
	
	def __init__(self):
		self.blocks = {0: Block(0, 'entry')}
		self.edges = {}
		self.yields = {}
		self.checks = {}
	
	def block(self, anno=None):
		id = len(self.blocks)
		self.blocks[id] = Block(id, anno)
		return self.blocks[id]
	
	def edge(self, src, dst, checked=None):
		self.edges.setdefault(src, []).append(dst)
		if checked:
			self.checks[src, dst] = {n.name: chk for (n, chk) in checked}

ATOMIC = ast.NoneVal, ast.Bool, ast.Int, ast.Float, ast.Name

class FlowFinder(object):
	
	def __init__(self):
		self.flow = FlowGraph()
		self.cur = self.flow.blocks[0]
		self.tmp = 0
		self.caught = None
		self.branched = None
	
	def name(self):
		self.tmp += 1
		return '$%s' % (self.tmp - 1)
	
	def visit(self, node):
		return getattr(self, node.__class__.__name__)(node)
	
	def append(self, node):
		
		node = self.visit(node)
		if node is None:
			return
		
		self.cur.push(node)
		if isinstance(node, ast.Call):
			self.redirect(node)
	
	def Suite(self, node):
		for stmt in node.stmts:
			self.append(stmt)
	
	def inter(self, node):
		
		if isinstance(node, ATOMIC):
			return node
		
		asgt = ast.Assign(None)
		asgt.left = ast.Name(self.name(), node.pos)
		asgt.right = self.visit(node)
		self.cur.push(asgt)
		
		if isinstance(asgt.right, ast.Call):
			self.redirect(asgt.right)
		
		return asgt.left
	
	def redirect(self, node):
		
		if self.caught is None:
			return
		
		next = self.flow.block('try-continue')
		node.callbr = next.id, None
		self.flow.edge(self.cur.id, next.id)
		self.caught.append((self.cur.id, node))
		self.cur = next
	
	# Expressions
	
	def NoneVal(self, node):
		return node
	
	def Bool(self, node):
		return node
	
	def Int(self, node):
		return node
	
	def Float(self, node):
		return node
	
	def String(self, node):
		return node
	
	def Name(self, node):
		return node
	
	def As(self, node):
		return node
	
	def Not(self, node):
		node.value = self.inter(node.value)
		return node
	
	def binary(self, node):
		node.left = self.inter(node.left)
		node.right = self.inter(node.right)
		return node
	
	def And(self, node):
		return self.binary(node)
	
	def Or(self, node):
		return self.binary(node)
	
	def Is(self, node):
		return self.binary(node)
	
	def EQ(self, node):
		return self.binary(node)
	
	def NE(self, node):
		return self.binary(node)
	
	def LT(self, node):
		return self.binary(node)
	
	def GT(self, node):
		return self.binary(node)
	
	def Add(self, node):
		return self.binary(node)
	
	def Sub(self, node):
		return self.binary(node)
	
	def Mod(self, node):
		return self.binary(node)
	
	def Mul(self, node):
		return self.binary(node)
	
	def Div(self, node):
		return self.binary(node)
	
	def BWAnd(self, node):
		return self.binary(node)
	
	def BWOr(self, node):
		return self.binary(node)
	
	def BWXor(self, node):
		return self.binary(node)
	
	def Attrib(self, node):
		node.obj = self.inter(node.obj)
		return node
	
	def Elem(self, node):
		node.obj = self.inter(node.obj)
		node.key = self.inter(node.key)
		return node
	
	def Call(self, node):
		for i, arg in enumerate(node.args):
			node.args[i] = self.inter(arg)
		return node
	
	def Ternary(self, node):
		
		entry = self.cur
		cond = self.inter(node.cond)
		left = self.flow.block('ternary-left')
		self.cur = left
		lvar = self.inter(node.values[0])
		
		right = self.flow.block('ternary-right')
		self.cur = right
		rvar = self.inter(node.values[1])
		
		entry.push(CondBranch(cond, left.id, right.id))
		exit = self.flow.block('ternary-exit')
		left.push(Branch(exit.id))
		right.push(Branch(exit.id))
		
		self.cur = exit
		self.flow.edge(entry.id, left.id)
		self.flow.edge(entry.id, right.id)
		self.flow.edge(left.id, exit.id)
		self.flow.edge(right.id, exit.id)
		return Phi(node.pos, (left.id, lvar), (right.id, rvar))
	
	def Tuple(self, node):
		node.values = [self.inter(v) for v in node.values]
		return node
	
	# Statements
	
	def Break(self, node):
		br = Branch(None)
		self.cur.push(br)
		self.branched.setdefault('break', []).append(br)
	
	def Continue(self, node):
		br = Branch(None)
		self.cur.push(br)
		self.branched.setdefault('continue', []).append(br)
	
	def Pass(self, node):
		self.cur.push(node)
	
	def Return(self, node):
		if node.value is not None:
			node.value = self.inter(node.value)
		self.cur.push(node)
		self.cur.returns = True
	
	def assign(self, node):
		
		node.right = self.visit(node.right)
		if isinstance(node.left, ast.Attrib):
			new = SetAttr(node.left.pos)
			new.obj = node.left.obj
			new.attrib = node.left.attrib
			node.left = new
		
		self.cur.push(node)
		if isinstance(node.right, ast.Call):
			self.redirect(node.right)
	
	def Assign(self, node):
		self.assign(node)
	
	def IAdd(self, node):
		self.assign(node)
	
	def Yield(self, node):
		
		self.cur.push(node)
		next = self.flow.block('yield-to')
		self.flow.yields[self.cur.id] = next.id
		node.target = next.id
		
		self.cur.returns = True
		self.flow.edge(self.cur.id, next.id)
		self.cur = next
	
	def Raise(self, node):
		self.cur.push(node)
		self.cur.raises = True
	
	def If(self, node):
		
		prevcond, exits, check, checked = None, [], False, []
		for i, (cond, suite) in enumerate(node.blocks):
			
			if i and cond is not None:
				
				assert isinstance(prevcond.steps[-1], CondBranch)
				tmp, self.cur = self.cur, self.flow.block('if-cond')
				prevcond.steps[-1].tg2 = self.cur.id
				
				condvar = self.inter(cond)
				if isinstance(cond, ast.Is):
					checked.append((cond.left, False))
					check = True
				
				prevcond.checks = {n.name: chk for (n, chk) in checked}
				self.flow.edge(prevcond.id, self.cur.id, checked)
				self.cur.push(CondBranch(condvar, None, None))
				self.cur, prevcond = tmp, self.cur
			
			block = self.flow.block('if-suite')
			if i and cond is not None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg1 = block.id
				self.flow.edge(prevcond.id, block.id, checked)
			
			if not i:
				
				condvar = self.inter(cond)
				if isinstance(cond, ast.Is):
					checked.append((cond.left, False))
					check = True
				
				self.cur.checks = {n.name: chk for (n, chk) in checked}
				self.flow.edge(self.cur.id, block.id, checked)
				self.cur.push(CondBranch(condvar, block.id, None))
				prevcond = self.cur
			
			elif cond is None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg2 = block.id
				prevcond.checks = {n.name: chk for (n, chk) in checked}
				self.flow.edge(prevcond.id, block.id, checked)
				prevcond = None
			
			self.cur = block
			self.visit(suite)
			if self.cur.needbranch():
				exits.append(self.cur)
			
			if checked and check:
				invert = checked[-1][0], not checked[-1][1]
				checked = checked[:-1] + [invert]
				check = False
		
		if prevcond is None and not exits:
			return
		
		self.cur = self.flow.block('if-exit')
		if prevcond:
			assert isinstance(prevcond.steps[-1], CondBranch)
			prevcond.steps[-1].tg2 = self.cur.id
			self.flow.edge(prevcond.id, self.cur.id, checked)
		
		for block in exits:
			if block.steps and isinstance(block.steps[-1], FINAL):
				continue
			block.push(Branch(self.cur.id))
			self.flow.edge(block.id, self.cur.id, checked)
	
	def While(self, node):
		
		self.branched = {}
		head = self.flow.block('while-head')
		body = self.flow.block('while-body')
		self.cur.push(Branch(head.id))
		self.flow.edge(self.cur.id, head.id)
		
		self.cur = head
		head.push(CondBranch(self.inter(node.cond), body.id, None))
		self.flow.edge(head.id, body.id)
		
		self.cur = body
		self.visit(node.suite)
		self.cur.push(Branch(head.id))
		self.flow.edge(self.cur.id, head.id)
		
		exit = self.flow.block('while-exit')
		self.cur = exit
		assert isinstance(head.steps[-1], CondBranch)
		head.steps[-1].tg2 = exit.id
		self.flow.edge(head.id, self.cur.id)
		
		for n in self.branched.get('continue', []):
			n.label = head.id
		for n in self.branched.get('break', []):
			n.label = exit.id
		self.branched = None
	
	def For(self, node):
		
		self.branched = {}
		head = self.flow.block('for-head')
		body = self.flow.block('for-body')
		
		asgt = ast.Assign(None)
		asgt.left = ast.Name(self.name(), None)
		asgt.right = LoopSetup(node)
		self.cur.push(asgt)
		self.cur.push(Branch(head.id))
		self.flow.edge(self.cur.id, head.id)
		head.push(LoopHeader(asgt.left, node.lvar, body.id, None))
		self.flow.edge(head.id, body.id)
		
		self.cur = body
		self.visit(node.suite)
		self.cur.push(Branch(head.id))
		self.flow.edge(self.cur.id, head.id)
		
		exit = self.flow.block('for-exit')
		self.cur = exit
		assert isinstance(head.steps[-1], LoopHeader)
		head.steps[-1].tg2 = exit.id
		self.flow.edge(head.id, exit.id)
		
		for n in self.branched.get('continue', []):
			n.label = head.id
		for n in self.branched.get('break', []):
			n.label = exit.id
		self.branched = None
	
	def TryBlock(self, node):
		
		self.caught = []
		self.visit(node.suite)
		if self.cur.anno == 'try-continue':
			assert not self.cur.steps
			del self.flow.blocks[self.cur.id]
			self.flow.edges[self.caught[-1][0]].remove(self.cur.id)
		
		pad = self.flow.block('landing-pad')
		for i, (bid, call) in enumerate(self.caught):
			self.flow.edge(bid, pad.id)
			if i < len(self.caught) - 1:
				call.callbr = call.callbr[0], pad.id
			else:
				last = bid, call
		
		map = {}
		self.caught = None
		for handler in node.catch:
			self.cur = self.flow.block('catch')
			self.visit(handler.suite)
			map[handler.type] = self.cur.id
			self.flow.edge(pad.id, self.cur.id)
		
		pad.push(LPad(map))
		exit = self.cur = self.flow.block('try-exit')
		last[1].callbr = exit.id, pad.id
		self.flow.edge(last[0], exit.id)
		for id in util.values(map):
			self.flow.blocks[id].push(Branch(exit.id))
			self.flow.edge(id, exit.id)
	
	def find_flow(self, node):
		
		self.visit(node.suite)
		flow = node.flow = self.flow
		
		final = flow.blocks[len(flow.blocks) - 1]
		callbr, branch = False, False
		if final.steps:
			last = final.steps[-1]
			callbr = isinstance(last, ast.Call) and last.callbr
			branch = isinstance(last, FINAL)
		
		if not final.steps or not (callbr or branch):
			auto = ast.Return(None)
			auto.value = None
			auto.pos = node.pos
			final.steps.append(auto)
			final.returns = True
		
		for src, dsts in util.items(flow.edges):
			for dst in dsts:
				flow.blocks[dst].preds.append(flow.blocks[src])

FINAL = ast.Return, ast.Raise, Branch, CondBranch, ast.Yield, LoopHeader, LPad

class Module(object):
	
	def __init__(self, name, node=None):
		self.name = name
		self.names = {}
		self.code = []
		self.defined = set()
		self.scope = {t.__name__: t() for t in types.BASE}
		if node is not None:
			self.add(node)
	
	def __repr__(self):
		contents = sorted(util.items(self.__dict__))
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	
	def __getitem__(self, key):
		return self.names[key]
	
	def __setitem__(self, key, val):
		self.names[key] = val
	
	def iteritems(self):
		return self.names.iteritems()
	
	def items(self):
		return self.names.items()
	
	def type(self, t, stubs={}):
		if t is None:
			return types.void()
		elif t == '...':
			return types.VarArgs()
		elif isinstance(t, types.base):
			return t
		elif isinstance(t, tuple):
			assert t[0] == 'tuple', t
			t = t[0], tuple(t[1])
			obj = self.scope[t] = types.build_tuple(t[1])
			return obj
		elif isinstance(t, str) and t[0] == '$':
			return types.owner(self.type(t[1:], stubs))
		elif isinstance(t, str) and t[0] == '&':
			return types.ref(self.type(t[1:], stubs))
		elif isinstance(t, str) and '[' in t:
			ext = t.partition('[')
			assert ext[2][-1] == ']'
			tpl = self.type(ext[0])
			params = (self.type(ext[2][:-1]),)
			self.scope[tpl.name, (params,)] = obj = types.apply(tpl, params)
			return obj
		elif isinstance(t, str):
			return stubs[t] if t in stubs else self.scope[t]
		elif isinstance(t, ast.Name):
			if t.name in stubs:
				return stubs[t.name]
			if t.name not in self.scope:
				raise util.Error(t, "type '%s' not found" % t.name)
			return self.scope[t.name]
		elif isinstance(t, ast.Elem):
			if isinstance(self.type(t.obj.name, stubs), types.template):
				if t.key.name in stubs:
					return self.type(t.obj.name, stubs)
			tpl = self.scope[t.obj.name]
			params = (self.type(t.key, stubs),)
			obj = self.scope[tpl.name, params] = types.apply(tpl, params)
			return obj
		elif isinstance(t, ast.Owner):
			return types.owner(self.type(t.value, stubs))
		elif isinstance(t, ast.Ref):
			return types.ref(self.type(t.value, stubs))
		elif isinstance(t, ast.Opt):
			return types.opt(self.type(t.value, stubs))
		elif isinstance(t, ast.Tuple):
			params = tuple(self.type(v) for v in t.values)
			obj = self.scope['tuple', params] = types.build_tuple(params)
			return obj
		else:
			assert False, 'no type %s' % t
	
	def merge(self, mod):
		for k, v in util.items(mod):
			self.names[k] = v
		for name, fun in mod.code:
			self.code.append((name, fun))
		self.defined |= mod.defined
	
	def add(self, node):
		
		code = []
		for n in node.suite:
			
			if isinstance(n, ast.RelImport):
				for name in n.names:
					
					if isinstance(n.base, ast.Name):
						base = n.base.name
					else:
						start = n.base
						res = []
						while isinstance(start, ast.Attrib):
							res.append(start.attrib)
							start = start.obj
						res.append(start.name)
						base = '.'.join(reversed(res))
					
					self[name.name] = base + '.' + name.name
			
			elif isinstance(n, ast.Class):
				self[n.name.name] = n
				for m in n.methods:
					code.append(((n.name.name, m.name.name), m))
			
			elif isinstance(n, ast.Function):
				code.append((n.name.name, n))
			
			elif isinstance(n, ast.Trait):
				self[n.name.name] = n
			
			elif isinstance(n, ast.Assign):
				assert isinstance(n.left, ast.Name), n.left
				self[n.left.name] = Constant(n.right)
			
			elif isinstance(n, ast.Decl):
				self[n.name.name] = n
			
			else:
				assert False, n
		
		for name, node in code:
			self.defined.add(name)
			FlowFinder().find_flow(node)
			self.code.append((name, node))
