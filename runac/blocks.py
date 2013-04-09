import ast, util

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

class Block(util.AttribRepr):
	
	def __init__(self, id, anno=None):
		self.id = id
		self.anno = anno
		self.steps = []
		self.preds = []
		self.assigns = None
		self.uses = None
	
	def push(self, inst):
		self.steps.append(inst)
	
	def needbranch(self):
		return not isinstance(self.steps[-1], ast.Return)

class FlowGraph(util.AttribRepr):
	
	def __init__(self):
		self.blocks = {0: Block(0, 'entry')}
		self.edges = None
		self.exits = None
		self.yields = {}
	
	def block(self, anno=None):
		id = len(self.blocks)
		self.blocks[id] = Block(id, anno)
		return self.blocks[id]
	
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

class FlowFinder(object):
	
	def __init__(self):
		self.flow = FlowGraph()
		self.cur = self.flow.blocks[0]
		self.tmp = 0
	
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
		if node is not None:
			self.cur.push(node)
	
	def Suite(self, node):
		for stmt in node.stmts:
			self.append(stmt)
	
	def inter(self, node):
		if isinstance(node, ast.Name):
			return node
		asgt = ast.Assign(None)
		asgt.left = ast.Name(self.name(), None)
		asgt.right = self.visit(node)
		self.cur.push(asgt)
		return asgt.left
	
	# Expressions
	
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
		node.left = self.inter(node.left)
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
	
	def Mul(self, node):
		return self.binary(node)
	
	def Div(self, node):
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
		return Phi(node.pos, (left.id, lvar), (right.id, rvar))
	
	# Statements
	
	def Pass(self, node):
		self.cur.push(node)
	
	def Return(self, node):
		if node.value is not None:
			node.value = self.inter(node.value)
		self.cur.push(node)
	
	def Assign(self, node):
		node.right = self.visit(node.right)
		self.cur.push(node)
	
	def Yield(self, node):
		self.cur.push(node)
		next = self.flow.block('yield-to')
		self.flow.yields[self.cur.id] = next.id
		node.target = next.id
		self.cur = next
	
	def If(self, node):
		
		prevcond, exits = None, []
		for i, (cond, suite) in enumerate(node.blocks):
			
			if i and cond is not None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				condblock = self.flow.block('if-cond')
				prevcond.steps[-1].tg2 = condblock.id
				condblock.push(CondBranch(cond, None, None))
				prevcond = condblock
			
			block = self.flow.block('if-suite')
			if i and cond is not None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg1 = block.id
			
			if not i:
				self.cur.push(CondBranch(cond, block.id, None))
				prevcond = self.cur
			elif cond is None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg2 = block.id
				prevcond = None
			
			self.cur = block
			self.visit(suite)
			if self.cur.needbranch():
				exits.append(self.cur)
		
		exit = self.flow.block('if-exit')
		if prevcond:
			assert isinstance(prevcond.steps[-1], CondBranch)
			prevcond.steps[-1].tg2 = exit.id
		
		self.cur = exit
		for block in exits:
			block.push(Branch(exit.id))
	
	def While(self, node):
		
		head = self.flow.block('while-head')
		body = self.flow.block('while-body')
		self.cur.push(Branch(head.id))
		head.push(CondBranch(node.cond, body.id, None))
		
		self.cur = body
		self.visit(node.suite)
		self.cur.push(Branch(head.id))
		
		exit = self.flow.block('while-exit')
		self.cur = exit
		assert isinstance(head.steps[-1], CondBranch)
		head.steps[-1].tg2 = exit.id
	
	def For(self, node):
		
		head = self.flow.block('for-head')
		body = self.flow.block('for-body')
		
		asgt = ast.Assign(None)
		asgt.left = ast.Name(self.name(), None)
		asgt.right = LoopSetup(node)
		self.cur.push(asgt)
		self.cur.push(Branch(head.id))
		head.push(LoopHeader(asgt.left, node.lvar, body.id, None))
		
		self.cur = body
		self.visit(node.suite)
		self.cur.push(Branch(head.id))
		
		exit = self.flow.block('for-exit')
		self.cur = exit
		assert isinstance(head.steps[-1], LoopHeader)
		head.steps[-1].tg2 = exit.id

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
		
		else:
			assert False, n
	
	for k, v in mod.code:
		
		cfg = v.flow = FlowFinder().build(v.suite)
		cfg.edges = {}
		
		for i, bl in cfg.blocks.iteritems():
			
			if not bl.steps:
				auto = ast.Return(None)
				auto.value = None
				bl.steps.append(auto)
				continue
			
			if isinstance(bl.steps[-1], Branch):
				cfg.edges.setdefault(i, []).append(bl.steps[-1].label)
			elif isinstance(bl.steps[-1], CondBranch):
				cfg.edges.setdefault(i, []).append(bl.steps[-1].tg1)
				cfg.edges.setdefault(i, []).append(bl.steps[-1].tg2)
			elif isinstance(bl.steps[-1], ast.Yield):
				cfg.edges.setdefault(i, []).append(bl.steps[-1].target)
			elif isinstance(bl.steps[-1], LoopHeader):
				cfg.edges.setdefault(i, []).append(bl.steps[-1].tg1)
				cfg.edges.setdefault(i, []).append(bl.steps[-1].tg2)
			elif not isinstance(bl.steps[-1], ast.Return):
				auto = ast.Return(None)
				auto.value = None
				auto.pos = v.pos
				bl.steps.append(auto)
		
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
