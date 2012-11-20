import ast, types, ti

ESCAPES = {'\n'}

class Value(object):
	def __init__(self, type, var):
		self.type = type
		self.var = var
	def __repr__(self):
		attrs = ['%s=%r' % p for p in self.__dict__.iteritems()]
		return '<Value(%s)>' % ', '.join(attrs)

class Frame(object):
	
	def __init__(self, parent=None):
		self.vars = 0
		self.parent = parent
		self.defined = {}
	
	def __contains__(self, key):
		return key in self.defined or (self.parent and key in self.parent)
	
	def __getitem__(self, key):
		if key not in self.defined:
			return self.parent[key]
		return self.defined[key]
	
	def __setitem__(self, key, value):
		self.defined[key] = value
	
	def get(self, key, default=None):
		return self[key] if key in self else default
	
	def varname(self):
		self.vars += 1
		return '%i' % (self.vars - 1)

class CodeGen(object):
	
	def __init__(self):
		self.buf = []
		self.level = 0
		self.start = True
		self.tlabels = 0
	
	def visit(self, node, frame):
		
		if hasattr(self, node.__class__.__name__):
			return getattr(self, node.__class__.__name__)(node, frame)
		
		for k in node.fields:
			attr = getattr(node, k)
			if isinstance(attr, list):
				for v in attr:
					self.visit(v, frame)
			else:
				self.visit(attr, frame)
	
	# Output helper methods
	
	def tabs(self):
		return '\t' * self.level
	
	def indent(self, num=1):
		self.level += num
	
	def dedent(self, num=1):
		self.level -= num
		assert self.level >= 0
	
	def newline(self):
		self.buf.append('\n')
		self.start = True
	
	def write(self, data):
		prefix = self.tabs() if self.start else ''
		self.buf.append(prefix + data)
		self.start = False
	
	def writeline(self, ln):
		if not ln: return
		self.write(ln + '\n')
		self.start = True
	
	def writelines(self, lines):
		prefix = self.tabs() if self.start else ''
		self.buf.append(prefix + ('\n' + self.tabs()).join(lines) + '\n')
		self.start = True
	
	def label(self, label, hint=None):
		self.dedent()
		if hint is None:
			self.writeline('%s:' % label)
		else:
			self.writeline('%s: ; %s' % (label, hint))
		self.indent()
	
	def coerce(self, val, dst, frame):
		
		vt = val.type, 0
		while isinstance(vt[0], types.WRAPPERS):
			vt = vt[0].over, vt[1] + 1
		
		dt = dst, 0
		while isinstance(dt[0], types.WRAPPERS):
			dt = dt[0].over, dt[1] + 1
		
		while vt[1] > dt[1]:
			res = frame.varname()
			bits = res, val.type.ir, val.var
			self.writeline('%%%s = load %s %%%s' % bits)
			val = Value(val.type.over, res)
			vt = vt[0], vt[1] - 1
		
		if vt == dt:
			return val
		
		if vt[0] in types.UINTS and dt[0] in types.UINTS:
			assert dt[0].bits > vt[0].bits
			assert not vt[1] and not dt[1]
			res = frame.varname()
			bits = res, vt[0].ir, val.var, dt[0].ir
			self.writeline('%%%s = zext %s %%%s to %s' % bits)
			return Value(dt[0], res)
		
		assert False, '%s -> %s' % (val.type, dst)
	
	# Node visitation methods
	
	def Name(self, node, frame):
		return frame.get(node.name)
	
	def Bool(self, node, frame):
		tmp = frame.varname()
		self.writeline('%%%s = alloca %s' % (tmp, node.type.ir))
		val = '1' if node.val else '0'
		bits = node.type.ir, val, types.owner(node.type).ir, tmp
		self.writeline('store %s %s, %s %%%s' % bits)
		return Value(types.owner(node.type), tmp)
	
	def Int(self, node, frame):
		tmp = frame.varname()
		self.writeline('%%%s = alloca %s' % (tmp, node.type.ir))
		bits = node.type.ir, node.val, types.owner(node.type).ir, tmp
		self.writeline('store %s %s, %s %%%s' % bits)
		return Value(types.owner(node.type), tmp)
	
	def String(self, node, frame):
		
		data = frame.varname()
		dtype = '[%i x i8]' % len(node.val.decode('string_escape'))
		self.writeline('%%%s = alloca %s' % (data, dtype))
		
		literal = node.val
		for c in ESCAPES:
			escaped = repr(c)[1:-1]
			sub = '\\0' + hex(ord(c))[2:]
			literal = literal.replace(escaped, sub)
		
		bits = dtype, literal, dtype, data
		self.writeline('store %s c"%s", %s* %%%s' % bits)
		
		full = frame.varname()
		self.writeline('%%%s = alloca %%str' % full)
		lenvar = frame.varname()
		bits = lenvar, full
		self.writeline('%%%s = getelementptr %%str* %%%s, i32 0, i32 0' % bits)
		
		lentype = node.type.attribs['len'][1].ir
		bits = lentype, len(node.val), lentype, lenvar
		self.writeline('store %s %i, %s* %%%s' % bits)
		
		cast = frame.varname()
		bits = cast, dtype, data
		self.writeline('%%%s = bitcast %s* %%%s to i8*' % bits)
		
		dataptr = frame.varname()
		bits = dataptr, full
		self.writeline('%%%s = getelementptr %%str* %%%s, i32 0, i32 1' % bits)
		self.writeline('store i8* %%%s, i8** %%%s' % (cast, dataptr))
		return Value(types.owner(node.type), full)
	
	def Init(self, node, frame):
		res = frame.varname()
		self.writeline('%%%s = alloca %s' % (res, node.type.ir))
		return Value(types.owner(node.type), res)
	
	def LT(self, node, frame):
		
		left = self.visit(node.left, frame)
		right = self.visit(node.right, frame)
		
		leftval = frame.varname()
		bits = leftval, left.type.ir, left.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		rightval = frame.varname()
		bits = rightval, right.type.ir, right.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		tmp = frame.varname()
		bits = tmp, left.type.over.ir, leftval, rightval
		self.writeline('%%%s = icmp ult %s %%%s, %%%s' % bits)
		return Value(types.ALL['bool'](), tmp)
	
	def GT(self, node, frame):
		
		left = self.visit(node.left, frame)
		right = self.visit(node.right, frame)
		
		assert isinstance(left.type, types.WRAPPERS)
		assert isinstance(right.type, types.WRAPPERS)
		assert left.type.over == right.type.over
		
		leftval = frame.varname()
		bits = leftval, left.type.ir, left.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		rightval = frame.varname()
		bits = rightval, right.type.ir, right.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		tmp = frame.varname()
		bits = tmp, left.type.over.ir, leftval, rightval
		self.writeline('%%%s = icmp ugt %s %%%s, %%%s' % bits)
		return Value(types.ALL['bool'](), tmp)
	
	def NEq(self, node, frame):
		
		left = self.visit(node.left, frame)
		leftval = frame.varname()
		bits = leftval, left.type.ir, left.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		right = self.visit(node.right, frame)
		rightval = frame.varname()
		bits = rightval, right.type.ir, right.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		res = frame.varname()
		bits = res, left.type.over.ir, leftval, rightval
		self.writeline('%%%s = icmp ne %s %%%s, %%%s' % bits)
		return Value(types.ALL['bool'](), res)
	
	def Eq(self, node, frame):
		
		left = self.visit(node.left, frame)
		leftval = frame.varname()
		bits = leftval, left.type.ir, left.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		right = self.visit(node.right, frame)
		rightval = frame.varname()
		bits = rightval, right.type.ir, right.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		res = frame.varname()
		bits = res, left.type.over.ir, leftval, rightval
		self.writeline('%%%s = icmp eq %s %%%s, %%%s' % bits)
		return Value(types.ALL['bool'](), res)
	
	def Add(self, node, frame):
		
		left = self.visit(node.left, frame)
		assert isinstance(left.type, types.WRAPPERS)
		leftval = frame.varname()
		bits = leftval, left.type.ir, left.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		right = self.visit(node.right, frame)
		assert left.type == right.type
		rightval = frame.varname()
		bits = rightval, right.type.ir, right.var
		self.writeline('%%%s = load %s %%%s' % bits)
		
		res = frame.varname()
		bits = res, left.type.over.ir, leftval, rightval
		self.writeline('%%%s = add %s %%%s, %%%s' % bits)
		return Value(left.type.over, res)
	
	def CondBranch(self, node, frame):
		cond = self.visit(node.cond, frame)
		bits = cond.var, node.tg1, node.tg2
		self.writeline('br i1 %%%s, label %%L%s, label %%L%s' % bits)
	
	def Assign(self, node, frame):
		
		val = self.visit(node.right, frame)
		if isinstance(node.left, ast.Name):
			
			if node.left.name not in frame:
				var = frame.varname()
				bits = var, node.left.type.ir, node.left.name
				self.writeline('%%%s = alloca %s ; %s' % bits)
				wrapped = types.owner(node.left.type)
				frame[node.left.name] = Value(wrapped, var)
			target = frame[node.left.name]
			
		elif isinstance(node.left, ast.Attrib):
			target = self.visit(node.left, frame)
		else:
			assert False
		
		if types.ref(val.type) == target.type:
			bits = val.type.ir, val.var, target.type.ir, target.var
			self.writeline('store %s %%%s, %s %%%s' % bits)
			return
		
		if types.owner(val.type) == target.type:
			bits = val.type.ir, val.var, target.type.ir, target.var
			self.writeline('store %s %%%s, %s %%%s' % bits)
			return
		
		w = lambda t: isinstance(t.type, types.WRAPPERS)
		if w(val) and w(target) and val.type.over == target.type.over:
			tmp = frame.varname()
			bits = tmp, val.type.ir, val.var
			self.writeline('%%%s = load %s %%%s' % bits)
			bits = val.type.over.ir, tmp, target.type.ir, target.var
			self.writeline('store %s %%%s, %s %%%s' % bits)
			return
		
		assert False
	
	def Attrib(self, node, frame):
		
		obj = self.visit(node.obj, frame)
		t = obj.type
		if isinstance(t, types.WRAPPERS):
			t = obj.type.over
		
		name = frame.varname()
		idx, type = t.attribs[node.attrib.name]
		bits = name, obj.type.ir, obj.var, idx
		self.writeline('%%%s = getelementptr %s %%%s, i32 0, i32 %s' % bits)
		return Value(types.ref(type), name)
	
	def Ternary(self, node, frame):
		
		cond = self.visit(node.cond, frame)
		llabel = 'T%s' % self.tlabels
		rlabel = 'T%s' % (self.tlabels + 1)
		jlabel = 'T%s' % (self.tlabels + 2)
		self.tlabels += 3
		
		bits = cond.var, llabel, rlabel
		self.writeline('br i1 %%%s, label %%%s, label %%%s' % bits)
		
		self.label(llabel, 'ternary-left')
		leftval = self.visit(node.values[0], frame)
		self.writeline('br label %%%s' % jlabel)
		self.label(rlabel, 'ternary-right')
		rightval = self.visit(node.values[1], frame)
		self.writeline('br label %%%s' % jlabel)
		
		self.label(jlabel, 'ternary-join')
		res = frame.varname()
		bits = res, leftval.type.ir, leftval.var, llabel, rightval.var, rlabel
		self.writeline('%%%s = phi %s [ %%%s, %%%s ], [ %%%s, %%%s ]' % bits)
		return Value(leftval.type, res)
		
	def Return(self, node, frame):
		value = self.visit(node.value, frame)
		if isinstance(value.type, types.WRAPPERS):
			if value.type.over.byval:
				tmp = frame.varname()
				bits = tmp, value.type.ir, value.var
				self.writeline('%%%s = load %s %%%s' % bits)
				value = Value(value.type.over, tmp)
		self.writeline('ret %s %%%s' % (value.type.ir, value.var))
	
	def Call(self, node, frame):
		
		args = []
		rtype, atypes = node.fun.type.over
		for i, arg in enumerate(node.args):
			val = self.visit(arg, frame)
			val = self.coerce(val, atypes[i], frame)
			args.append(val)
		
		argstr = ', '.join('%s %%%s' % (a.type.ir, a.var) for a in args)
		if rtype == types.void():
			self.writeline('call void @%s(%s)' % (node.fun.decl, argstr))
			return args[0] if isinstance(node.args[0], ti.Init) else None
		
		res = frame.varname()
		bits = res, rtype.ir, node.fun.decl, argstr
		self.writeline('%%%s = call %s @%s(%s)' % bits)
		return Value(rtype, res)
	
	def Function(self, node, frame):
		
		self.tlabels = 0
		frame = Frame(frame)
		irname = node.name.name
		if hasattr(node, 'irname'):
			irname = node.irname
		
		self.write('define %s @%s(' % (node.rtype.ir, irname))
		first = True
		for arg in node.args:
			
			if not first:
				self.write(', ')
			
			self.write(arg.type.ir + ' %' + arg.name.name)
			frame[arg.name.name] = Value(arg.type, arg.name.name)
			first = False
		
		self.write(') {')
		self.newline()
		self.indent()
		
		for i, block in sorted(node.flow.blocks.iteritems()):
			self.visit(block, frame)
		
		if node.rtype == types.void():
			self.writeline('ret void')
		
		self.dedent()
		self.writeline('}')
		self.newline()
	
	def Block(self, node, frame):
		self.label('L%s' % node.id, node.anno)
		for step in node.steps:
			self.visit(step, frame)
	
	def declare(self, ref):
		
		if isinstance(ref, ti.Function) and ref.decl.startswith('runa.'):
			return
		
		if isinstance(ref, types.Type) and isinstance(ref, types.WRAPPERS):
			return
		
		if isinstance(ref, ti.Function):
			rtype = ref.type.over[0].ir
			args = ', '.join(t.ir for t in ref.type.over[1])
			self.writeline('declare %s @%s(%s)' % (rtype, ref.decl, args))
			return
		
	def type(self, type):
		
		ignore = types.WRAPPERS + (types.template,)
		if isinstance(type, ignore):
			return
		
		fields = sorted(type.attribs.itervalues())
		s = ', '.join([i[1].ir for i in fields])
		self.writeline('%s = type { %s }\n' % (type.ir, s))
	
	def Module(self, mod):
		
		assert not mod.constants
		for k, v in mod.refs.iteritems():
			self.declare(ti.resolve(mod, v))
		
		self.newline()
		for k, v in mod.types.iteritems():
			if k in types.BASIC: continue
			self.type(v)
		
		for var in mod.variants:
			self.type(var)
		
		frame = Frame()
		for k, v in mod.code:
			self.visit(v, frame)
		
		return ''.join(self.buf)

def source(mod):
	return CodeGen().Module(mod)
