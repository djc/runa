import ast, blocks, types, util

class Free(util.AttribRepr):
	fields = 'value',
	def __init__(self, value):
		self.value = value

def destructify(code):
	
	left = {}
	returns = set()
	for i, bl in code.flow.blocks.iteritems():
		
		if bl.returns:
			returns.add(i)
		
		for var, steps in bl.assigns.iteritems():
			
			assert len(steps) == 1
			sid = steps.pop()
			step = bl.steps[sid]
			
			if isinstance(step, blocks.LoopHeader):
				type = step.lvar.type
			else:
				type = step.right.type
			
			if not isinstance(type, types.owner):
				continue
			
			left[var] = i, sid, type
		
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
		for rbli in returns:
			rbl = code.flow.blocks[rbli]
			node = ast.Name(name, None)
			node.type = type
			rbl.steps.insert(-1, Free(node))

def destruct(mod):
	for name, code in mod.code:
		destructify(code)
