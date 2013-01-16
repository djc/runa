import ast, types, blocks, typer
import sys, copy

ESCAPES = {'\\n': '\\0a', '\\0': '\\00'}

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
		return '%%%i' % (self.vars - 1)

class CodeGen(object):
	
	def __init__(self):
		self.level = 0
		self.start = True
		self.main = False
		self.labels = {}
		self.typedecls = None
		self.buf = []
	
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
	
	def label(self, label, hint=None):
		self.dedent()
		if hint is None:
			self.writeline('%s:' % label)
		else:
			self.writeline('%s: ; %s' % (label, hint))
		self.indent()
	
	def getlabel(self, prefix):
		new = self.labels.get(prefix, 0)
		self.labels[prefix] = new + 1
		return '%s%i' % (prefix, new)
	
	# Some IR writing helpers
	
	def alloca(self, frame, t):
		res = frame.varname()
		t = t.ir if isinstance(t, (types.base, types.trait)) else t
		self.writeline('%s = alloca %s' % (res, t))
		return res
	
	def load(self, frame, val):
		assert isinstance(val, Value)
		bits = frame.varname(), val.type.ir, val.var
		self.writeline('%s = load %s %s' % bits)
		return Value(val.type.over, bits[0])
	
	def store(self, val, dst):
		if isinstance(val, Value):
			bits = val.type.ir, val.var, val.type.ir, dst
		elif isinstance(val, tuple) and isinstance(val[0], types.base):
			bits = val[0].ir, val[1], val[0].ir, dst
		elif isinstance(val, tuple):
			bits = val[0], val[1], val[0], dst
		else:
			assert False
		self.writeline('store %s %s, %s* %s' % bits)
	
	def gep(self, frame, val, *args):
		
		res = frame.varname()
		idx = ', '.join('i32 %i' % a for a in args)
		if isinstance(val, Value):
			bits = res, val.type.ir, val.var, idx
		elif isinstance(val, tuple):
			bits = (res,) + val + (idx,)
		else:
			assert False, val
		
		self.writeline('%s = getelementptr %s %s, %s' % bits)
		return res
	
	# Some type system helper methods
	
	def coerce(self, val, dst, frame):
		
		vt = val.type, 0
		while isinstance(vt[0], types.WRAPPERS):
			vt = vt[0].over, vt[1] + 1
		
		dt = dst, 0
		while isinstance(dt[0], types.WRAPPERS):
			dt = dt[0].over, dt[1] + 1
		
		boolt = types.get('bool')
		if dst == boolt:
			
			if vt[0] == boolt:
				while val.type != boolt:
					val = self.load(frame, val)
				return val
			
			if not vt[1]:
				tmp = self.alloca(frame, vt[0])
				self.store(val, tmp)
				val = Value(types.ref(vt[0]), tmp)
			
			irname = vt[0].methods['__bool__'][1][0][0]
			bits = frame.varname(), irname, val.type.ir, val.var
			self.writeline('%s = call i1 @%s(%s %s)' % bits)
			return Value(boolt, bits[0])
		
		while vt[1] > dt[1]:
			val = self.load(frame, val)
			vt = vt[0], vt[1] - 1
		
		if vt == dt:
			return val
		
		if vt[0] in types.UINTS and dt[0] in types.UINTS:
			assert dt[0].bits > vt[0].bits
			assert not vt[1] and not dt[1]
			res = frame.varname()
			bits = res, vt[0].ir, val.var, dt[0].ir
			self.writeline('%s = zext %s %s to %s' % bits)
			return Value(dt[0], res)
		
		if isinstance(dt[0], types.trait) and types.compat(vt[0], dt[0]):
			return self.traitwrap(val, dst, frame)
		
		if isinstance(dst, types.VarArgs):
			return val
		
		assert False, '%s -> %s' % (val.type, dst)
	
	def traitwrap(self, val, trait, frame):
		
		if not isinstance(val.type, types.WRAPPERS):
			tmp = self.alloca(frame, val.type)
			self.store(val, tmp)
			val = Value(types.ref(val.type), tmp)
		
		assert isinstance(val.type, types.WRAPPERS)
		assert isinstance(trait, types.WRAPPERS)
		
		ptrt = types.get('&byte')
		wrap = self.alloca(frame, types.unwrap(trait))
		vtt = '%' + trait.over.name + '.vt'
		vt = self.alloca(frame, vtt)
		
		t = types.unwrap(trait)
		for i, (k, (rt, tmalts)) in enumerate(sorted(t.methods.iteritems())):
			
			# trait methods overloading TODO
			assert len(tmalts) == 1
			tmeth = tmalts[0][0], rt, tmalts[0][1]
			cmrt, cmalts = types.unwrap(val.type).methods[k]
			assert len(cmalts) == 1
			cmeth = cmalts[0][0], cmrt, cmalts[0][1]
			
			cmt = types.function(cmeth[1], [a[1] for a in cmeth[2]])
			tmt = types.function(tmeth[1], [a[1] for a in tmeth[2]])
			tmt.over[1][0] = ptrt
			
			cast = frame.varname()
			bits = cast, cmt.ir, cmeth[0], tmt.ir
			self.writeline('%s = bitcast %s @%s to %s' % bits)
			slot = self.gep(frame, (vtt + '*', vt), 0, i)
			self.store((tmt, cast), slot)
		
		vtslot = self.gep(frame, (trait.over.ir + '*', wrap), 0, 0)
		self.store((vtt + '*', vt), vtslot)
		
		cast = frame.varname()
		bits = cast, val.type.ir, val.var, ptrt.ir
		self.writeline('%s = bitcast %s %s to %s' % bits)
		objslot = self.gep(frame, (trait.over.ir + '*', wrap), 0, 1)
		self.store((ptrt, cast), objslot)
		return Value(trait, wrap)
	
	# Node visitation methods
	
	def Name(self, node, frame):
		return self.load(frame, frame[node.name])
	
	def Bool(self, node, frame):
		return Value(node.type, 'true' if node.val else 'false')
	
	def Int(self, node, frame):
		return Value(node.type, node.val)
	
	def Float(self, node, frame):
		return Value(node.type, node.val)
	
	def String(self, node, frame):
		
		dtype = '[%i x i8]' % len(node.val.decode('string_escape'))
		data = self.alloca(frame, dtype)
		
		literal = node.val
		for c, sub in sorted(ESCAPES.iteritems()):
			literal = literal.replace(c, sub)
		
		self.store((dtype, 'c"%s"' % literal), data)
		t = types.unwrap(node.type)
		full = self.alloca(frame, t)
		lenvar = self.gep(frame, ('%str*', full), 0, 0)
		self.store((t.attribs['len'][1], len(node.val)), lenvar)
		
		cast = frame.varname()
		bits = cast, dtype, data
		self.writeline('%s = bitcast %s* %s to i8*' % bits)
		self.store(('i8*', cast), self.gep(frame, ('%str*', full), 0, 1))
		return Value(node.type, full)
	
	def Init(self, node, frame):
		
		if not node.escapes and node.type.byval:
			return Value(types.ref(node.type), self.alloca(frame, node.type))
		elif not node.escapes:
			return Value(node.type, self.alloca(frame, node.type.over))
		
		assert isinstance(node.type, types.owner), 'escaping %s' % node.type
		sizevar = '@%s.size' % node.type.over.ir[1:]
		size = self.load(frame, Value(types.get('&int'), sizevar))
		
		bits = frame.varname(), size.var
		self.writeline('%s = call i8* @runa.malloc(i64 %s)' % bits)
		
		res = frame.varname()
		bits = res, bits[0], node.type.ir
		self.writeline('%s = bitcast i8* %s to %s' % bits)
		return Value(node.type, res)
	
	# Boolean operators
	
	def boolean(self, op, node, frame):
		
		left = self.visit(node.left, frame)
		right = self.visit(node.right, frame)
		assert left.type == right.type
		
		t = left.type
		if isinstance(t, types.WRAPPERS):
			t = left.type.over
		
		bool = frame.varname()
		rt, malts = t.methods['__bool__']
		method = malts[0][0], rt, malts[0][1]
		
		arg = self.coerce(left, method[2][0][1], frame)
		argstr = '%s %s' % (arg.type.ir, arg.var)
		bits = bool, method[1].ir, method[0], argstr
		self.writeline('%s = call %s @%s(%s)' % bits)
		
		res = frame.varname()
		if op == 'and':
			bits = res, bool, right.type.ir, right.var, left.type.ir, left.var
		elif op == 'or':
			bits = res, bool, left.type.ir, left.var, right.type.ir, right.var
		
		self.writeline('%s = select i1 %s, %s %s, %s %s' % bits)
		return Value(left.type, res)
	
	def Not(self, node, frame):
		
		val = self.visit(node.value, frame)
		if types.unwrap(val.type) != types.get('bool'):
			val = self.coerce(val, types.get('bool'), frame)
		
		bits = frame.varname(), val.var
		self.writeline('%s = select i1 %s, i1 false, i1 true' % bits)
		return Value(types.get('bool'), bits[0])
	
	def And(self, node, frame):
		return self.boolean('and', node, frame)
	
	def Or(self, node, frame):
		return self.boolean('or', node, frame)
	
	# Comparison operators
	
	def compare(self, op, node, frame):
		
		left = self.visit(node.left, frame)
		right = self.visit(node.right, frame)
		
		vtypes = {types.get('bool')} | types.INTS | types.FLOATS
		if types.unwrap(left.type) in vtypes:
			
			if isinstance(left.type, types.WRAPPERS):
				left = self.load(frame, left)
			if isinstance(right.type, types.WRAPPERS):
				right = self.load(frame, right)
			
			assert left.type == right.type, (left.type, right.type)
			if op not in {'eq', 'ne'}:
				op = {False: 'u', True: 's'}[left.type.signed] + op
			
			inst = 'fcmp' if left.type in types.FLOATS else 'icmp'
			tmp = frame.varname()
			bits = tmp, inst, op, left.type.ir, left.var, right.var
			self.writeline('%s = %s %s %s %s, %s' % bits)
			return Value(types.get('bool'), tmp)
		
		assert left.type == right.type
		inv = False
		if op in {'eq', 'ne'} and '__%s__' % op not in left.type.over.methods:
			op = {'eq': 'ne', 'ne': 'eq'}[op]
			inv = True
		
		t = types.unwrap(left.type)
		irname, mt = t.select('__%s__' % op, (left.type, right.type))
		args = ['%s %s' % (a.type.ir, a.var) for a in (left, right)]
		bits = frame.varname(), mt.over[0].ir, irname, ', '.join(args)
		self.writeline('%s = call %s @%s(%s)' % bits)
		
		val = Value(types.get('bool'), bits[0])
		if not inv:
			return val
		
		bits = frame.varname(), val.var
		self.writeline('%s = select i1 %s, i1 false, i1 true' % bits)
		return Value(types.get('bool'), bits[0])
	
	def EQ(self, node, frame):
		return self.compare('eq', node, frame)
	
	def NE(self, node, frame):
		return self.compare('ne', node, frame)
	
	def LT(self, node, frame):
		return self.compare('lt', node, frame)
	
	def GT(self, node, frame):
		return self.compare('gt', node, frame)
	
	# Arithmetic operators
	
	def arith(self, op, node, frame):
		
		left = self.visit(node.left, frame)
		right = self.visit(node.right, frame)
		if types.unwrap(left.type) in types.INTS:
			
			if isinstance(left.type, types.WRAPPERS):
				left = self.load(frame, left)
			if isinstance(right.type, types.WRAPPERS):
				right = self.load(frame, right)
			
			assert left.type == right.type
			op = {'div': 'sdiv'}.get(op, op)
			res = frame.varname()
			bits = res, op, left.type.ir, left.var, right.var
			self.writeline('%s = %s %s %s, %s' % bits)
			return Value(left.type, res)
		
		assert isinstance(left.type, types.WRAPPERS)
		assert isinstance(right.type, types.WRAPPERS)
		
		t = types.unwrap(left.type)
		irname, mt = t.select('__%s__' % op, (left.type, right.type))
		args = ['%s %s' % (a.type.ir, a.var) for a in (left, right)]
		bits = frame.varname(), mt.over[0].ir, irname, ', '.join(args)
		self.writeline('%s = call %s @%s(%s)' % bits)
		return Value(mt.over[0], bits[0])
	
	def Add(self, node, frame):
		return self.arith('add', node, frame)
	
	def Sub(self, node, frame):
		return self.arith('sub', node, frame)
	
	def Mul(self, node, frame):
		return self.arith('mul', node, frame)
	
	def Div(self, node, frame):
		return self.arith('div', node, frame)
	
	# Miscellaneous
	
	def As(self, node, frame):
		left = self.visit(node.left, frame)
		assert left.type in types.INTS and node.type in types.INTS
		assert left.type.bits <= node.type.bits
		assert left.type in types.SINTS and node.type in types.UINTS
		return Value(node.type, left.var)
		
	def CondBranch(self, node, frame):
		
		cond = self.visit(node.cond, frame)
		if cond.type != types.get('bool'):
			cond = self.coerce(cond, types.get('bool'), frame)
		
		bits = cond.var, node.tg1, node.tg2
		self.writeline('br i1 %s, label %%L%s, label %%L%s' % bits)
	
	def Branch(self, node, frame):
		self.writeline('br label %%L%s' % node.label)
	
	def Assign(self, node, frame):
		
		val = self.visit(node.right, frame)
		if isinstance(node.left, ast.Name):
			
			if node.left.name not in frame:
				addr = self.alloca(frame, val.type)
			else:
				addr = frame[node.left.name].var
			
			self.store(val, addr)
			frame[node.left.name] = Value(types.ref(val.type), addr)
			return
			
		elif isinstance(node.left, ast.Attrib):
			target = self.visit(node.left, frame)
		else:
			assert False
		
		if types.ref(val.type) == target.type:
			self.store(val, target.var)
			return
		
		if types.owner(val.type) == target.type:
			self.store(val, target.var)
			return
		
		w = lambda t: isinstance(t.type, types.WRAPPERS)
		if w(val) and w(target) and val.type.over == target.type.over:
			self.store(self.load(frame, val), target.var)
			return
		
		assert False
	
	def Attrib(self, node, frame):
		obj = self.visit(node.obj, frame)
		t = types.unwrap(obj.type)
		idx, type = t.attribs[node.attrib.name]
		name = self.gep(frame, obj, 0, idx)
		return Value(types.ref(type), name)
	
	def Elem(self, node, frame):
		
		obj = self.visit(node.obj, frame)
		t = types.unwrap(obj.type)
		assert t.name.startswith('array[')
		et = t.attribs['data'][1].over
		
		data = self.gep(frame, obj, 0, 1)
		obj = '[0 x %s]*' % et.ir, data
		elm = self.gep(frame, obj, 0, int(node.key.val))
		return Value(types.ref(et), elm)
	
	def Ternary(self, node, frame):
		
		cond = self.visit(node.cond, frame)
		if cond.type != types.get('bool'):
			cond = self.coerce(cond, types.get('bool'), frame)
		
		llabel = self.getlabel('T')
		rlabel = self.getlabel('T')
		jlabel = self.getlabel('T')
		bits = cond.var, llabel, rlabel
		self.writeline('br i1 %s, label %%%s, label %%%s' % bits)
		
		self.label(llabel, 'ternary-left')
		leftval = self.visit(node.values[0], frame)
		self.writeline('br label %%%s' % jlabel)
		self.label(rlabel, 'ternary-right')
		rightval = self.visit(node.values[1], frame)
		self.writeline('br label %%%s' % jlabel)
		
		self.label(jlabel, 'ternary-join')
		res = frame.varname()
		bits = res, leftval.type.ir, leftval.var, llabel, rightval.var, rlabel
		self.writeline('%s = phi %s [ %s, %%%s ], [ %s, %%%s ]' % bits)
		return Value(leftval.type, res)
		
	def Return(self, node, frame):
		
		if node.value is None and self.main:
			self.writeline('ret i32 0')
			return
		if node.value is None:
			self.writeline('ret void')
			return
		
		value = self.visit(node.value, frame)
		if isinstance(value.type, types.WRAPPERS):
			if value.type.over.byval:
				value = self.load(frame, value)
		self.writeline('ret %s %s' % (value.type.ir, value.var))
	
	def Call(self, node, frame):
		
		args = []
		rtype, atypes = node.fun.type.over
		wrapped = None
		for i, arg in enumerate(node.args):
			
			if not node.virtual or i:
				val = self.visit(arg, frame)
				args.append(self.coerce(val, atypes[i], frame))
				continue
			
			val = wrapped = self.visit(arg, frame)
			vtp = self.gep(frame, val, 0, 1)
			args.append(self.load(frame, Value(types.get('&&byte'), vtp)))
		
		type, name = rtype, '@' + node.fun.decl
		if atypes[-1] == types.VarArgs():
			type = node.fun.type
		elif node.virtual:
			
			mname = node.fun.decl.split('.', 1)[1]
			t = types.unwrap(node.fun.type.over[1][0])
			idx = sorted(t.methods).index(mname)
			
			vtp = self.gep(frame, wrapped, 0, 0)
			vtt = '%%%s.vt*' % t.name
			vt = frame.varname()
			self.writeline('%s = load %s* %s' % (vt, vtt, vtp))
			fp = self.gep(frame, (vtt, vt), 0, 0)
			
			ft = copy.copy(node.fun.type)
			ft.over = ft.over[0], [types.get('&byte')] + ft.over[1][1:]
			fun = self.load(frame, Value(types.ref(ft), fp))
			type, name = fun.type, fun.var
		
		argstr = ', '.join('%s %s' % (a.type.ir, a.var) for a in args)
		if rtype == types.void():
			self.writeline('call %s %s(%s)' % (type.ir, name, argstr))
			return args[0] if isinstance(node.args[0], typer.Init) else None
		
		res = frame.varname()
		bits = res, type.ir, name, argstr
		self.writeline('%s = call %s %s(%s)' % bits)
		return Value(rtype, res)
	
	def Function(self, node, frame):
		
		self.labels.clear()
		frame = Frame(frame)
		irname = node.name.name
		if hasattr(node, 'irname'):
			irname = node.irname
		
		rt = node.rtype.ir
		if irname == 'main' and rt == 'void':
			rt = 'i32'
		
		args = ['%s %%%s' % (a.type.ir, a.name.name) for a in node.args]
		if irname == 'main' and node.args:
			args = ['i32 %argc', 'i8** %argv']
		self.writeline('define %s @%s(%s) {' % (rt, irname, ', '.join(args)))
		self.indent()
		
		self.label('L0', 'entry')
		if irname == 'main' and node.args:
			
			strt = types.get('&str')
			addrp = self.gep(frame, ('i8**', '%argv'), 0)
			addr = self.load(frame, Value(types.get('&&byte'), addrp))
			namevar = self.alloca(frame, strt.over)
			
			wrapfun = '@str.__init__$Rstr.Obyte'
			bits = wrapfun, strt.ir, namevar, addr.var
			self.writeline('call void %s(%s %s, i8* %s)' % bits)
			frame['name'] = Value(strt, namevar)
			
			argsvar = self.alloca(frame, types.get('&array[str]'))
			args = Value(types.get('&$array[str]'), argsvar)
			direct = frame.varname()
			call = '%s = call %%array$str* @args(i32 %%argc, i8** %%argv)'
			self.writeline(call % direct)
			self.store(('%array$str*', direct), args.var)
			frame['args'] = args
			
		elif node.args:
			for arg in node.args:
				addr = self.alloca(frame, arg.type)
				frame[arg.name.name] = Value(types.ref(arg.type), addr)
				self.store((arg.type, '%' + arg.name.name), addr)
		
		self.main = irname == 'main' and node.rtype.ir == 'void'
		for i, block in sorted(node.flow.blocks.iteritems()):
			self.visit(block, frame)
		
		self.dedent()
		self.writeline('}')
		self.newline()
	
	def Block(self, node, frame):
		if node.id:
			self.label('L%s' % node.id, node.anno)
		for step in node.steps:
			self.visit(step, frame)
	
	def const(self, name, val, frame):
		
		if types.unwrap(val.type) != types.get('str'):
			bits = name, types.unwrap(val.type).ir, val.val
			self.writeline('@%s = constant %s %s' % bits)
			frame[name] = Value(val.type, '@%s' % name)
			return
		
		slen = len(val.val.decode('string_escape'))
		dtype = '[%i x i8]' % slen
		literal = val.val
		for c, sub in sorted(ESCAPES.iteritems()):
			literal = literal.replace(c, sub)
			
		bits = name, dtype, literal
		self.writeline('@%s.data = constant %s c"%s"' % bits)
		bits = name, slen, 'i8* bitcast (%s* @%s.data to i8*)' % (dtype, name)
		self.writeline('@%s = constant %%str { i64 %s, %s }' % bits)
		frame[name] = Value(val.type, '@%s' % name)
	
	def declare(self, ref):
		
		if isinstance(ref, typer.Function) and ref.decl.startswith('runa.'):
			return
		
		if isinstance(ref, typer.Function) and isinstance(ref, types.WRAPPERS):
			return
		
		if isinstance(ref, typer.Function):
			rtype = ref.type.over[0].ir
			args = ', '.join(t.ir for t in ref.type.over[1])
			self.writeline('declare %s @%s(%s)' % (rtype, ref.decl, args))
			return
		
	def type(self, type):
		
		ignore = types.WRAPPERS + (types.template,)
		if isinstance(type, ignore):
			return
		
		if type.name == 'array[str]':
			# predefined for args creation function
			return
		
		if type.name.startswith('array['):
			s = 'i64, [0 x %s]' % type.attribs['data'][1].over.ir
			self.writeline('%s = type { %s }' % (type.ir, s))
			return
		
		fields = sorted(type.attribs.itervalues())
		s = ', '.join([i[1].ir for i in fields])
		self.writeline('%s = type { %s }' % (type.ir, s))
		
		t = type.ir
		gep = '%s* getelementptr (%s* null, i32 1)' % (t, t)
		cast = 'constant i64 ptrtoint (%s to i64)' % gep
		self.writeline('@%s.size = %s' % (t[1:], cast))
		self.newline()
	
	def trait(self, t):
		
		mtypes = []
		for name, (rt, malts) in sorted(t.methods.iteritems()):
			for irname, formal in malts:
				
				args = []
				for an, at in formal:
					args.append(types.get('&byte') if an == 'self' else at)
				
				mtypes.append(types.function(rt, args).ir)
		
		self.writeline('%%%s.vt = type { %s }' % (t.name, ', '.join(mtypes)))
		self.writeline('%%%s.wrap = type { %%%s.vt*, i8* }' % (t.name, t.name))
		self.newline()
	
	def Module(self, mod):
		
		for k, v in mod.names.iteritems():
			if isinstance(v, typer.Function):
				self.declare(v)
		
		self.newline()
		for k, v in mod.names.iteritems():
			if k in types.BASIC:
				continue
			elif isinstance(v, types.trait):
				self.trait(v)
			elif isinstance(v, types.base):
				self.type(v)
		
		for var in mod.variants:
			self.type(var)
		
		frame = Frame()
		for k, v in mod.names.iteritems():
			if isinstance(v, blocks.Constant):
				self.const(k, v.node, frame)
		
		self.typedecls = self.buf
		self.buf = []
		
		self.newline()
		for k, v in mod.code:
			self.visit(v, frame)

TRIPLES = {
	'darwin': 'x86_64-apple-darwin11.0.0',
	'linux2': 'x86_64-pc-linux-gnu',
}

def generate(mod):
	
	gen = CodeGen()
	gen.Module(mod)
	
	code = ['target triple = "%s"\n\n' % TRIPLES[sys.platform]]
	code += gen.typedecls
	
	with open('core/rt.ll') as f:
		code.append(f.read())
	
	code += gen.buf
	return ''.join(code)
