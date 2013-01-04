import ast

class Branch(object):
	fields = ()
	def __init__(self, target):
		self.label = target
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

class CondBranch(object):
	fields = ('cond',)
	def __init__(self, cond, tg1, tg2):
		self.cond = cond
		self.tg1 = tg1
		self.tg2 = tg2
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

class Constant(object):
	def __init__(self, node):
		self.node = node

class Block(object):
	
	def __init__(self, id, anno=None):
		self.id = id
		self.anno = anno
		self.steps = []
		self.preds = []
		self.assigns = None
		self.uses = set()
		self.needs = None
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	
	def push(self, inst):
		self.steps.append(inst)
	
	def needbranch(self):
		return not isinstance(self.steps[-1], ast.Return)

class FlowGraph(object):
	
	def __init__(self):
		self.blocks = {0: Block(0, 'entry')}
		self.edges = None
		self.exits = None
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	
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
	
	def build(self, node):
		self.visit(node)
		return self.flow
	
	def visit(self, node):
		if hasattr(self, node.__class__.__name__):
			getattr(self, node.__class__.__name__)(node)
		else:
			self.cur.push(node)
	
	def Suite(self, node):
		for stmt in node.stmts:
			self.visit(stmt)
	
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
		exit = self.flow.block('while-exit')
		self.cur.push(Branch(head.id))
		head.push(CondBranch(node.cond, body.id, exit.id))
		
		self.cur = body
		self.visit(node.suite)
		self.cur.push(Branch(head.id))
		self.cur = exit
	
	def For(self, node):
		assert False

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
						res.append(start.attrib.name)
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
				cfg.blocks[dst].preds.append(src)
	
	return mod
