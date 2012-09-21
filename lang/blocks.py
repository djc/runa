from util import Error
import ast, types

class Branch(object):
	def __init__(self, target):
		self.label = target
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

class CondBranch(object):
	def __init__(self, cond, tg1, tg2):
		self.cond = cond
		self.tg1 = tg1
		self.tg2 = tg2
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

class Block(object):
	
	def __init__(self, anno=None):
		self.anno = anno
		self.steps = []
	
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
		self.blocks = {0: Block('entry')}
		self.edges = None
	
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%s' % (k, v) for (k, v) in contents)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))
	
	def block(self, anno=None):
		id = len(self.blocks)
		self.blocks[id] = Block(anno)
		return id, self.blocks[id]

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
				prevcond.steps[-1].tg2 = condblock[0]
				condblock[1].push(CondBranch(cond, None, None))
				prevcond = condblock[1]
			
			id, block = self.flow.block('if-suite')
			if i and cond is not None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg1 = id
			
			if not i:
				self.cur.push(CondBranch(cond, id, None))
				prevcond = self.cur
			elif cond is None:
				assert isinstance(prevcond.steps[-1], CondBranch)
				prevcond.steps[-1].tg2 = id
				prevcond = None
			
			self.cur = block
			self.visit(suite)
			if self.cur.needbranch():
				exits.append(self.cur)
		
		exit = self.flow.block('if-exit')
		if prevcond:
			assert isinstance(prevcond.steps[-1], CondBranch)
			prevcond.steps[-1].tg2 = exit[0]
		
		self.cur = exit[1]
		for block in exits:
			block.push(Branch(exit[0]))
	
	def While(self, node):
		
		assert False, 'obsolete'
		start = self.cur
		cond = self.boolean(self.visit(node.cond))
		header = self.block([self.idx])
		body = self.block([header.id])
		self.visit(node.suite)
		exit = self.block([header.id, body.id])
		
		start.push(Branch(None, header.id))
		header.push(Branch(cond, body.id, exit.id))
		body.push(Branch(None, header.id))
	
	def For(self, node):
		
		assert False, 'obsolete'
		start = self.cur
		source = self.visit(node.source)
		self.cur.push(Assign('loop.source', source))
		header = self.block([self.idx])
		start.push(Branch(None, header.id))
		
		meta = source.type.methods['__next__']
		iter = Reference(source.type, 'loop.source')
		atypes = [iter] + [types.get(a) for a in meta[2]]
		val = Call(meta[0], types.get(meta[1]), atypes)
		header.named[node.lvar.name] = val
		header.push(Assign(self.visit(node.lvar), val))
		
		body = self.block([header.id])
		self.visit(node.suite)
		exit = self.block([header.id, body.id])
		body.push(Branch(None, header.id))
		header.push(Branch(node.lvar, body.id, exit.id))

class Module(object):
	
	def __init__(self, node):
		self.refs = {}
		self.constants = {}
		self.types = {}
		self.code = {}
		self.build(node)
	
	def build(self, node):
		
		bodies = {}
		for n in node.suite:
			
			if isinstance(n, ast.RelImport):
				for name in n.names:
					self.refs[name.name] = n.base.name + '.' + name.name
			
			elif isinstance(n, ast.Class):
				self.types[n.name.name] = n
				for m in n.methods:
					self.code[(n.name.name, m.name.name)] = m
		
		for k, v in sorted(self.code.iteritems()):
			
			cfg = self.code[k].flow = FlowFinder().build(v.suite)
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
			
			reachable = {0}
			for src, dst in cfg.edges.iteritems():
				reachable |= set(dst)
			
			for i in set(cfg.blocks) - reachable:
				del cfg.blocks[i]
