import ast, util

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
	
	def push(self, inst):
		self.steps.append(inst)
	
	def needbranch(self):
		return not self.steps or not isinstance(self.steps[-1], ast.Return)

class FlowGraph(util.AttribRepr):
	
	def __init__(self):
		self.blocks = {0: Block(0, 'entry')}
		self.edges = {}
		self.exits = None
		self.yields = {}
	
	def block(self, anno=None):
		id = len(self.blocks)
		self.blocks[id] = Block(id, anno)
		return self.blocks[id]
	
	def edge(self, src, dst):
		self.edges.setdefault(src, []).append(dst)
	
	def walk(self, path):
		
		last = path[-1]
		next = self.edges.get(last, [])
		if last in path[:-1]:
			x = [path[i + 1] for (i, b) in enumerate(path[:-1]) if b == last]
			next = sorted(set(next) - set(x))
		
		if not next:
			yield path + (None,)
			return
		
		for n in next:
			for res in self.walk(path + (n,)):
				yield res

ATOMIC = ast.NoneVal, ast.Bool, ast.Int, ast.Float, ast.Name

class FlowFinder(object):
	
	def __init__(self):
		self.flow = FlowGraph()
		self.cur = self.flow.blocks[0]
		self.tmp = 0
		self.caught = None
	
	def name(self):
		self.tmp += 1
		return '$%s' % (self.tmp - 1)
	
	def build(self, node):
		self.visit(node)
		return self.flow
	
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
		asgt.left = ast.Name(self.name(), None)
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
	
	def Pass(self, node):
		self.cur.push(node)
	
	def Return(self, node):
		if node.value is not None:
			node.value = self.inter(node.value)
		self.cur.push(node)
		self.cur.returns = True
	
	def Assign(self, node):
		
		node.right = self.visit(node.right)
		if isinstance(node.left, ast.Attrib):
			new = SetAttr(node.left.pos)
			new.obj = node.left.obj
			new.attrib = node.left.attrib
			node.left = new
		
		self.cur.push(node)
		if isinstance(node.right, ast.Call):
			self.redirect(node.right)
	
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
		
		prevcond, exits = None, []
		for i, (cond, suite) in enumerate(node.blocks):
			
			if i and cond is not None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				tmp, self.cur = self.cur, self.flow.block('if-cond')
				prevcond.steps[-1].tg2 = self.cur.id
				self.flow.edge(prevcond.id, self.cur.id)
				self.cur.push(CondBranch(self.inter(cond), None, None))
				self.cur, prevcond = tmp, self.cur
			
			block = self.flow.block('if-suite')
			if i and cond is not None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg1 = block.id
				self.flow.edge(prevcond.id, block.id)
			
			if not i:
				self.flow.edge(self.cur.id, block.id)
				self.cur.push(CondBranch(self.inter(cond), block.id, None))
				prevcond = self.cur
			elif cond is None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg2 = block.id
				self.flow.edge(prevcond.id, block.id)
				prevcond = None
			
			self.cur = block
			self.visit(suite)
			if self.cur.needbranch():
				exits.append(self.cur)
		
		exit = self.flow.block('if-exit')
		if prevcond:
			assert isinstance(prevcond.steps[-1], CondBranch)
			prevcond.steps[-1].tg2 = exit.id
			self.flow.edge(prevcond.id, exit.id)
		
		self.cur = exit
		for block in exits:
			block.push(Branch(exit.id))
			self.flow.edge(block.id, exit.id)
	
	def While(self, node):
		
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
	
	def For(self, node):
		
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
		for id in map.itervalues():
			self.flow.blocks[id].push(Branch(exit.id))
			self.flow.edge(id, exit.id)

class Module(object):
	
	def __init__(self):
		self.names = {}
		self.code = []
		self.variants = set() # populated by type inferencing pass
		self.scope = None # populated by type inferencing pass
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	
	def merge(self, mod):
		for k, v in mod.names.iteritems():
			assert k not in self.names, k
			self.names[k] = v
		self.code += mod.code

FINAL = ast.Return, ast.Raise, Branch, CondBranch, ast.Yield, LoopHeader, LPad

def module(node):
	
	mod = Module()
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
				
				mod.names[name.name] = base + '.' + name.name
		
		elif isinstance(n, ast.Class):
			mod.names[n.name.name] = n
			for m in n.methods:
				mod.code.append(((n.name.name, m.name.name), m))
		
		elif isinstance(n, ast.Function):
			mod.code.append((n.name.name, n))
		
		elif isinstance(n, ast.Trait):
			mod.names[n.name.name] = n
		
		elif isinstance(n, ast.Assign):
			assert isinstance(n.left, ast.Name), n.left
			mod.names[n.left.name] = Constant(n.right)
		
		elif isinstance(n, ast.Decl):
			mod.names[n.name.name] = n
		
		else:
			assert False, n
	
	for k, v in mod.code:
		
		cfg = v.flow = FlowFinder().build(v.suite)
		for i, bl in cfg.blocks.iteritems():
			
			if not bl.steps:
				auto = ast.Return(None)
				auto.value = None
				bl.steps.append(auto)
				continue
			
			last = bl.steps[-1]
			if isinstance(last, ast.Call) and last.callbr:
				continue
			elif isinstance(last, FINAL):
				continue
			
			auto = ast.Return(None)
			auto.value = None
			auto.pos = v.pos
			bl.steps.append(auto)
			bl.returns = True
		
		cfg.exits = set()
		reachable = set()
		for p in cfg.walk((0,)):
			reachable |= set(p[:-1])
			cfg.exits.add(p[-2])
		
		for i in set(cfg.blocks) - reachable:
			del cfg.blocks[i]
		
		for src, dsts in cfg.edges.iteritems():
			for dst in dsts:
				cfg.blocks[dst].preds.append(cfg.blocks[src])
	
	return mod
