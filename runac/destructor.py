from . import ast, blocks, types, util

class Free(util.AttribRepr):
	fields = 'value',
	def __init__(self, value):
		self.value = value

def destructify(code):
	
	left = {}
	returns = {}
	for i, bl in code.flow.blocks.iteritems():
		
		# For each block that returns, find the set of transitive
		# predecessor blocks; these assignments will need freeing.
		
		if bl.returns:
			returns[i], q = set(), {i}
			while q:
				cur = q.pop()
				returns[i].add(cur)
				for p in code.flow.blocks[cur].preds:
					if p.id in returns[i] or p.id in q:
						continue
					q.add(p.id)
		
		# Find assignments to owner variables; the last assignment
		# will be freed before return, earlier ones before next assign.
		
		for var, steps in bl.assigns.iteritems():
			for sid in steps:

				step = bl.steps[sid]
				if isinstance(step, blocks.LoopHeader):
					type = step.lvar.type
				else:
					type = step.right.type
				
				if not isinstance(type, types.owner):
					continue
				
				assert var not in left, var
				left[var] = i, sid, type
		
		# Remove assignments from Phi nodes; these would result in
		# double freeing (objects are freed through original var).
		
		for sid, step in enumerate(bl.steps):
			
			if not isinstance(step, ast.Assign):
				continue
			
			if isinstance(step.right, blocks.Phi):
				if isinstance(step.right.left[1].type, types.owner):
					left.pop(step.right.left[1].name, None)
				if isinstance(step.right.right[1].type, types.owner):
					left.pop(step.right.right[1].name, None)
		
		for var, loc in bl.escapes.iteritems():
			del left[var]
	
	if code.irname == 'main' and code.args:
		left['args'] = None, None, types.get('$array[str]')
	
	for name, (bl, s, type) in left.iteritems():
		for rbli, reachable in returns.iteritems():
			
			rbl = code.flow.blocks[rbli]
			if bl not in reachable:
				continue
			
			node = ast.Name(name, None)
			node.type = type
			rbl.steps.insert(-1, Free(node))

def destruct(mod):
	for name, code in mod.code:
		destructify(code)
