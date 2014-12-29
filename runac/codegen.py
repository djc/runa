from . import ast, types, blocks, typer, util
import os, sys, copy, platform

ESCAPES = {'\\n': '\\0a', '\\0': '\\00'}

class Value(util.AttribRepr):
	def __init__(self, type, var):
		self.type = type
		self.var = var

class Frame(object):
	
	def __init__(self, parent=None):
		self.parent = parent
		self.defined = {}
	
	def __repr__(self):
		return '<Frame(%i, %r)>' % (id(self.parent), self.defined)
	
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

class CodeGen(object):
	
	def __init__(self, word):
		self.word = word
		self.level = 0
		self.start = True
		self.main = None
		self.vars = 0
		self.labels = {}
		self.typedecls = None
		self.intercept = None
		self.buf = []
	
	def visit(self, node, frame):
		return getattr(self, node.__class__.__name__)(node, frame)
	
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
	
	def varname(self):
		self.vars += 1
		return '%%%i' % (self.vars - 1)
	
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
	
	def alloca(self, t):
		res = self.varname()
		assert isinstance(t, (types.base, types.trait))
		self.writeline('%s = alloca %s' % (res, t.ir))
		return Value(types.ref(t), res)
	
	def load(self, val):
		assert isinstance(val, Value)
		bits = self.varname(), val.type.ir, val.var
		self.writeline('%s = load %s %s' % bits)
		return Value(val.type.over, bits[0])
	
	def store(self, val, dst, comment=None):
		comment = ' ; ' + comment if comment else ''
		if isinstance(val, Value):
			bits = val.type.ir, val.var, val.type.ir, dst, comment
		elif isinstance(val, tuple) and isinstance(val[0], types.base):
			bits = val[0].ir, val[1], val[0].ir, dst, comment
		elif isinstance(val, tuple):
			bits = val[0], val[1], val[0], dst, comment
		else:
			assert False, val
		self.writeline('store %s %s, %s* %s%s' % bits)
	
	def gep(self, val, *args):
		
		indexes = []
		for a in args:
			if isinstance(a, int):
				indexes.append('i32 %i' % a)
			else:
				indexes.append('%s %s' % (a.type.ir, a.var))
		
		res = self.varname()
		if isinstance(val, Value):
			bits = res, val.type.ir, val.var, ', '.join(indexes)
		elif isinstance(val, tuple):
			bits = (res,) + val + (', '.join(indexes),)
		else:
			assert False, val
		
		self.writeline('%s = getelementptr %s %s, %s' % bits)
		return res
	
	# Some type system helper methods
	
	def coerce(self, val, dst):
		
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
					val = self.load(val)
				return val
			
			if not vt[1]:
				tmp = self.alloca(vt[0])
				self.store(val, tmp.var)
				val = tmp
			
			irname = vt[0].methods['__bool__'][0].decl
			bits = self.varname(), irname, val.type.ir, val.var
			self.writeline('%s = call i1 @%s(%s %s)' % bits)
			return Value(boolt, bits[0])
		
		while vt[1] > dt[1]:
			val = self.load(val)
			vt = vt[0], vt[1] - 1
		
		if vt == dt:
			return val
		
		if vt[0] in types.UINTS and dt[0] in types.UINTS:
			assert dt[0].bits > vt[0].bits, (dt[0], vt[0])
			assert not vt[1] and not dt[1]
			res = self.varname()
			bits = res, vt[0].ir, val.var, dt[0].ir
			self.writeline('%s = zext %s %s to %s' % bits)
			return Value(dt[0], res)
		
		if isinstance(dt[0], types.trait) and types.compat(vt[0], dt[0]):
			return self.traitwrap(val, dst)
		
		if isinstance(dst, types.VarArgs):
			return val
		
		assert False, '%s -> %s' % (val.type, dst)
	
	def traitwrap(self, val, trait):
		
		if not isinstance(val.type, types.WRAPPERS):
			tmp = self.alloca(val.type)
			self.store(val, tmp.var)
			val = tmp
		
		assert isinstance(val.type, types.WRAPPERS)
		assert isinstance(trait, types.WRAPPERS)
		
		ptrt = types.get('&byte')
		wrap = self.alloca(types.unwrap(trait))
		vtt = '%' + trait.over.name + '.vt'
		vt = self.varname()
		self.writeline('%s = alloca %s' % (vt, vtt))
		
		t = types.unwrap(trait)
		for i, (k, tmalts) in enumerate(sorted(t.methods.iteritems())):
			
			# trait methods overloading TODO
			assert len(tmalts) == 1
			tfun = tmalts[0]
			
			cmalts = types.unwrap(val.type).methods[k]
			assert len(cmalts) == 1
			cfun = cmalts[0]
			
			tft = copy.copy(tfun.type)
			tft.over = tft.over[0], list(tft.over[1])
			tft.over[1][0] = ptrt
			
			cast = self.varname()
			bits = cast, cfun.type.ir, cfun.decl, tft.ir
			self.writeline('%s = bitcast %s @%s to %s' % bits)
			slot = self.gep((vtt + '*', vt), 0, i)
			self.store((tft, cast), slot)
		
		vtslot = self.gep(wrap, 0, 0)
		self.store((vtt + '*', vt), vtslot)
		
		cast = self.varname()
		bits = cast, val.type.ir, val.var, ptrt.ir
		self.writeline('%s = bitcast %s %s to %s' % bits)
		objslot = self.gep(wrap, 0, 1)
		self.store((ptrt, cast), objslot)
		return wrap
	
	def free(self, val):
		bits = self.varname(), val.type.ir, val.var
		self.writeline('%s = bitcast %s %s to i8*' % bits)
		self.writeline('call void @runa.free(i8* %s)' % bits[0])
	
	# Node visitation methods
	
	def Name(self, node, frame):
		
		if self.intercept is None:
			var = frame[node.name]
			return var if node.name.startswith('$') else self.load(var)
		
		attr = types.unwrap(self.intercept.type).attribs[node.name]
		addr = self.gep(self.intercept, 0, attr[0])
		return self.load(Value(types.ref(attr[1]), addr))
	
	def Tuple(self, node, frame):
		val = self.alloca(node.type)
		for i, e in enumerate(node.values):
			slot = self.gep(val, 0, i)
			src = self.visit(e, frame)
			self.store((e.type, src.var), slot)
		return val
	
	def NoneVal(self, node, frame):
		assert isinstance(node.type, types.opt)
		assert isinstance(node.type.over, types.WRAPPERS)
		return Value(types.get('NoType'), 'null')
	
	def Bool(self, node, frame):
		return Value(node.type, 'true' if node.val else 'false')
	
	def Int(self, node, frame):
		return Value(node.type, node.val)
	
	def Float(self, node, frame):
		return Value(node.type, node.val)
	
	def String(self, node, frame):
		
		t = types.unwrap(node.type)
		literal = node.val
		for c, sub in sorted(ESCAPES.iteritems()):
			literal = literal.replace(c, sub)
		
		length = len(node.val.decode('string_escape'))
		dtype = '[%i x i8]' % length
		if not node.escapes:
			
			tmp = self.varname()
			self.writeline('%s = alloca %s' % (tmp, dtype))
			
			data = self.varname()
			self.store((dtype, 'c"%s"' % literal), tmp)
			
			bits = data, dtype, tmp
			self.writeline('%s = bitcast %s* %s to i8*' % bits)
			full = self.alloca(t)
			
		else:
			
			size = self.load(Value(types.get('&uint'), '@str.size'))
			tmp = self.varname()
			bits = tmp, self.word, size.var
			self.writeline('%s = call i8* @runa.malloc(%s %s)' % bits)
			
			full = self.varname()
			self.writeline('%s = bitcast i8* %s to %%str*' % (full, tmp))
			full = Value(types.owner(t), full)
			
			data = self.varname()
			bits = data, self.word, length
			self.writeline('%s = call i8* @runa.malloc(%s %s)' % bits)
			
			tmp = self.varname()
			bits = tmp, data, dtype
			self.writeline('%s = bitcast i8* %s to %s*' % bits)
			self.store((dtype, 'c"%s"' % literal), tmp)
		
		lenvar = self.gep(full, 0, 0)
		self.store((t.attribs['len'][1], len(node.val)), lenvar)
		self.store(('i8*', data), self.gep(full, 0, 1))
		return full
	
	def Init(self, node, frame):
		
		if not node.escapes and node.type.byval:
			return self.alloca(node.type)
		elif not node.escapes:
			return self.alloca(node.type.over)
		
		assert isinstance(node.type, types.owner), 'escaping %s' % node.type
		sizevar = '@%s.size' % node.type.over.ir[1:]
		size = self.load(Value(types.get('&int'), sizevar))
		
		bits = self.varname(), self.word, size.var
		self.writeline('%s = call i8* @runa.malloc(%s %s)' % bits)
		
		res = self.varname()
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
		
		bool = left.var
		if t != types.get('bool'):
			bool = self.varname()
			fun = t.methods['__bool__'][0]
			arg = self.coerce(left, fun.type.over[1][0])
			argstr = '%s %s' % (arg.type.ir, arg.var)
			bits = bool, fun.type.over[0].ir, fun.decl, argstr
			self.writeline('%s = call %s @%s(%s)' % bits)
		
		res = self.varname()
		if op == 'and':
			bits = res, bool, right.type.ir, right.var, left.type.ir, left.var
		elif op == 'or':
			bits = res, bool, left.type.ir, left.var, right.type.ir, right.var
		
		self.writeline('%s = select i1 %s, %s %s, %s %s' % bits)
		return Value(left.type, res)
	
	def Not(self, node, frame):
		
		val = self.visit(node.value, frame)
		if types.unwrap(val.type) != types.get('bool'):
			val = self.coerce(val, types.get('bool'))
		
		bits = self.varname(), val.var
		self.writeline('%s = select i1 %s, i1 false, i1 true' % bits)
		return Value(types.get('bool'), bits[0])
	
	def And(self, node, frame):
		return self.boolean('and', node, frame)
	
	def Or(self, node, frame):
		return self.boolean('or', node, frame)
	
	# Comparison operators
	
	def Is(self, node, frame):
		left = self.visit(node.left, frame)
		tmp = self.varname()
		bits = tmp, left.type.ir, left.var
		self.writeline('%s = icmp eq %s %s, null' % bits)
		return Value(types.get('bool'), tmp)
	
	def compare(self, op, node, frame):
		
		left = self.visit(node.left, frame)
		right = self.visit(node.right, frame)
		
		vtypes = {types.get('bool')} | types.INTS | types.FLOATS
		if types.unwrap(left.type) in vtypes:
			
			if isinstance(left.type, types.WRAPPERS):
				left = self.load(left)
			if isinstance(right.type, types.WRAPPERS):
				right = self.load(right)
			
			assert left.type == right.type, (left.type, right.type)
			if left.type in types.FLOATS:
				op = 'o' + op
			elif op not in {'eq', 'ne'}:
				op = {False: 'u', True: 's'}[left.type.signed] + op
			
			inst = 'fcmp' if left.type in types.FLOATS else 'icmp'
			tmp = self.varname()
			bits = tmp, inst, op, left.type.ir, left.var, right.var
			self.writeline('%s = %s %s %s %s, %s' % bits)
			return Value(types.get('bool'), tmp)
		
		assert left.type == right.type, (left.type, right.type)
		inv = False
		if op in {'eq', 'ne'} and '__%s__' % op not in left.type.over.methods:
			op = {'eq': 'ne', 'ne': 'eq'}[op]
			inv = True
		
		t = types.unwrap(left.type)
		fun = t.select(left, '__%s__' % op, (left.type, right.type))
		args = ['%s %s' % (a.type.ir, a.var) for a in (left, right)]
		bits = self.varname(), fun.type.over[0].ir, fun.decl, ', '.join(args)
		self.writeline('%s = call %s @%s(%s)' % bits)
		
		val = Value(types.get('bool'), bits[0])
		if not inv:
			return val
		
		bits = self.varname(), val.var
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
				left = self.load(left)
			if isinstance(right.type, types.WRAPPERS):
				right = self.load(right)
			
			assert left.type == right.type, (left.type, right.type)
			op = {'div': 'sdiv', 'mod': 'srem'}.get(op, op)
			res = self.varname()
			bits = res, op, left.type.ir, left.var, right.var
			self.writeline('%s = %s %s %s, %s' % bits)
			return Value(left.type, res)
		
		assert isinstance(left.type, types.WRAPPERS)
		assert isinstance(right.type, types.WRAPPERS)
		
		t = types.unwrap(left.type)
		fun = t.select(left, '__%s__' % op, (left.type, right.type))
		args = ['%s %s' % (a.type.ir, a.var) for a in (left, right)]
		bits = self.varname(), fun.type.over[0].ir, fun.decl, ', '.join(args)
		self.writeline('%s = call %s @%s(%s)' % bits)
		return Value(fun.type.over[0], bits[0])
	
	def Add(self, node, frame):
		return self.arith('add', node, frame)
	
	def Sub(self, node, frame):
		return self.arith('sub', node, frame)
	
	def Mod(self, node, frame):
		return self.arith('mod', node, frame)
	
	def Mul(self, node, frame):
		return self.arith('mul', node, frame)
	
	def Div(self, node, frame):
		return self.arith('div', node, frame)
	
	# Bitwise operators
	
	def BWAnd(self, node, frame):
		return self.arith('and', node, frame)
	
	def BWOr(self, node, frame):
		return self.arith('or', node, frame)
	
	def BWXor(self, node, frame):
		return self.arith('xor', node, frame)
	
	# Iteration
	
	def Yield(self, node, frame):
		
		ctxt = types.unwrap(self.intercept.type)
		jump = 'blockaddress(@%s, %%L%s)' % (ctxt.function.decl, node.target)
		slot = self.gep(self.intercept, 0, 0)
		self.store(('i8*', jump), slot)
		
		rt = ctxt.function.type.over[0]
		bits = self.varname(), rt.ir, 'undef', 'i1 1'
		self.writeline('%s = insertvalue %s %s, %s, 0' % bits)
		
		val = self.visit(node.value, frame)
		bits = self.varname(), rt.ir, bits[0], val.type.ir, val.var
		self.writeline('%s = insertvalue %s %s, %s %s, 1' % bits)
		self.writeline('ret %s %s' % (rt.ir, bits[0]))
	
	def LoopSetup(self, node, frame):
		
		ctx = self.alloca(node.type)
		labelslot = self.gep(ctx, 0, 0)
		labeladdr = 'blockaddress(@%s, %s)' % (ctx.type.name[1:-4], '%L0')
		self.store(('i8*', labeladdr), labelslot)
		
		ctxt = types.unwrap(ctx.type)
		for i, name in enumerate(node.loop.source.fun.type.args):
			idx = ctxt.attribs[name][0]
			var = self.visit(node.loop.source.args[i], frame)
			slot = self.gep(ctx, 0, idx)
			self.store(var, slot)
		
		return ctx
	
	def LoopHeader(self, node, frame):
		
		ctx = frame[node.ctx.name]
		ctxt = types.unwrap(ctx.type)
		
		res = self.varname()
		rt = ctxt.function.type.over[0].ir
		bits = res, rt, ctxt.function.decl, ctx.type.ir, ctx.var
		self.writeline('%s = call %s @%s(%s %s)' % bits)
		
		more, iterval = self.varname(), self.varname()
		self.writeline('%s = extractvalue %s %s, 0' % (more, rt, res))
		self.writeline('%s = extractvalue %s %s, 1' % (iterval, rt, res))
		
		itervar = self.alloca(node.lvar.type)
		self.store((node.lvar.type, iterval), itervar.var)
		frame[node.lvar.name] = itervar
		
		bits = more, node.tg1, node.tg2
		self.writeline('br i1 %s, label %%L%s, label %%L%s' % bits)
	
	# Miscellaneous
	
	def As(self, node, frame):
		
		left = self.visit(node.left, frame)
		if left.type.ir == node.type.ir:
			return Value(node.type, left.var)
		
		if left.type in types.INTS and node.type in types.INTS:
			assert left.type.bits <= node.type.bits
			assert left.type in types.SINTS and node.type in types.UINTS
			bits = self.varname(), left.type.ir, left.var, node.type.ir
			self.writeline('%s = zext %s %s to %s' % bits)
			return Value(node.type, bits[0])
		
		assert False, (left.type, node.type)
	
	def CondBranch(self, node, frame):
		
		cond = self.visit(node.cond, frame)
		if cond.type != types.get('bool'):
			cond = self.coerce(cond, types.get('bool'))
		
		bits = cond.var, node.tg1, node.tg2
		self.writeline('br i1 %s, label %%L%s, label %%L%s' % bits)
	
	def Branch(self, node, frame):
		self.writeline('br label %%L%s' % node.label)
	
	def Phi(self, node, frame):
		
		left = self.visit(node.left[1], frame)
		right = self.visit(node.right[1], frame)
		sides = left.var, node.left[0], right.var, node.right[0]
		
		tmp = self.varname()
		bits = (tmp, left.type.ir) + sides
		self.writeline('%s = phi %s [ %s, %%L%s ], [ %s, %%L%s ]' % bits)
		return Value(left.type, tmp)
	
	def Assign(self, node, frame):
		
		if isinstance(node.right, blocks.LoopSetup):
			frame[node.left.name] = self.visit(node.right, frame)
			return
		
		val = self.visit(node.right, frame)
		if isinstance(node.right, ast.Attrib):
			val = self.load(val)
		
		if isinstance(node.left, ast.Name):
			
			if self.intercept:
				ctxt = types.unwrap(self.intercept.type)
				attr = ctxt.attribs[node.left.name]
				slot = self.gep(self.intercept, 0, attr[0])
				wrap = Value(types.ref(attr[1]), slot)
			elif node.left.name in frame:
				wrap = frame[node.left.name]
			elif node.left.name.startswith('$'):
				frame[node.left.name] = val
				return
			else:
				wrap = self.alloca(val.type)
			
			self.store(val, wrap.var, "to variable '%s'" % node.left.name)
			frame[node.left.name] = wrap
			return
		
		elif isinstance(node.left, ast.Tuple):
			for i, e in enumerate(node.left.values):
				src = self.gep(val, 0, i)
				loaded = self.load(Value(types.ref(e.type), src))
				assert e.name not in frame
				assert not e.name.startswith('$')
				assert not self.intercept
				wrap = self.alloca(e.type)
				self.store(loaded, wrap.var)
				frame[e.name] = wrap
			return
		
		elif isinstance(node.left, blocks.SetAttr):
			target = self.visit(node.left, frame)
		else:
			assert False, node.left.type
		
		if types.ref(val.type) == target.type:
			self.store(val, target.var)
			return
		
		if types.owner(val.type) == target.type:
			self.store(val, target.var)
			return
		
		w = lambda t: isinstance(t.type, types.WRAPPERS)
		if w(val) and w(target) and val.type.over == target.type.over:
			self.store(self.load(val), target.var)
			return
		
		assert False
	
	def IAdd(self, node, frame):
		
		assert isinstance(node.left, ast.Name), node.left
		assert not self.intercept
		
		wrap = frame[node.left.name]
		res = self.arith('add', node, frame)
		self.store(res, wrap.var, "to variable '%s'" % node.left.name)
		frame[node.left.name] = wrap
	
	def Attrib(self, node, frame):
		obj = self.visit(node.obj, frame)
		t = types.unwrap(obj.type)
		idx, type = t.attribs[node.attrib]
		name = self.gep(obj, 0, idx)
		return Value(types.ref(type), name)
	
	def SetAttr(self, node, frame):
		return self.Attrib(node, frame)
	
	def Elem(self, node, frame):
		
		obj = self.visit(node.obj, frame)
		t = types.unwrap(obj.type)
		assert t.name.startswith('array[')
		et = t.attribs['data'][1].over
		
		key = self.visit(node.key, frame)
		assert key.type == types.get('int'), (key.type, node)
		
		data = self.gep(obj, 0, 1)
		obj = '[0 x %s]*' % et.ir, data
		elm = self.gep(obj, 0, key)
		return Value(types.ref(et), elm)
	
	def Ternary(self, node, frame):
		
		cond = self.visit(node.cond, frame)
		if cond.type != types.get('bool'):
			cond = self.coerce(cond, types.get('bool'))
		
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
		res = self.varname()
		bits = res, leftval.type.ir, leftval.var, llabel, rightval.var, rlabel
		self.writeline('%s = phi %s [ %s, %%%s ], [ %s, %%%s ]' % bits)
		return Value(leftval.type, res)
	
	def Raise(self, node, frame):
		val = self.visit(node.value, frame)
		bits = val.type.ir, val.var
		self.writeline('call void @runa.raise(%s %s) noreturn' % bits)
		self.writeline('unreachable')
	
	def LPad(self, node, frame):
		pass
	
	def Pass(self, node, frame):
		pass
	
	def Return(self, node, frame):
		
		if self.main is not None and self.main.args:
			self.free(self.load(frame['args']))
		
		if node.value is None:
			if self.main is not None and self.main.rtype.ir == 'void':
				self.writeline('ret i32 0')
				return
			if self.intercept is None:
				self.writeline('ret void')
				return
		
		if node.value is not None and node.value.type.name.startswith('tuple['):
			value = self.visit(node.value, frame)
			for i, t in enumerate(node.value.type.params):
				src = self.gep(value, 0, i)
				dst = self.gep((value.type.ir, '%$R'), 0, i)
				loaded = self.load(Value(types.ref(t), src))
				self.store(loaded, dst)
			self.writeline('ret void')
			return
		
		if self.intercept is not None:
			ctxt = types.unwrap(self.intercept.type)
			rt = ctxt.function.type.over[0]
			assert rt.params[0].name in types.INTEGERS
			bits = rt.ir, rt.params[0].ir
			self.writeline('ret %s { i1 0, %s 0 }' % bits)
			return
		
		value = self.visit(node.value, frame)
		if isinstance(value.type, types.WRAPPERS):
			if value.type.over.byval:
				value = self.load(value)
		self.writeline('ret %s %s' % (value.type.ir, value.var))
	
	def Free(self, node, frame):
		
		val = self.visit(node.value, frame)
		if not isinstance(val.type, types.owner):
			return
		
		t = types.unwrap(val.type)
		for name, (idx, atype) in t.attribs.iteritems():
			
			if not isinstance(atype, types.owner):
				continue
			
			if t.name.startswith('array[') and idx == 1:
				continue
			
			slot = Value(types.ref(atype), self.gep(val, 0, idx))
			self.free(self.load(slot))
		
		self.free(val)
	
	def Call(self, node, frame):
		
		rvar, args = None, []
		rtype, atypes = node.fun.type.over
		if rtype.name.startswith('tuple['):
			rvar = self.alloca(rtype)
			args.append(rvar)
		
		wrapped = None
		for i, arg in enumerate(node.args):
			
			if not node.virtual or i:
				val = self.visit(arg, frame)
				args.append(self.coerce(val, atypes[i]))
				continue
			
			val = wrapped = self.visit(arg, frame)
			vtp = self.gep(val, 0, 1)
			args.append(self.load(Value(types.get('&&byte'), vtp)))
		
		type, name = rtype, '@' + node.fun.decl
		if atypes and atypes[-1] == types.VarArgs():
			type = node.fun.type
		elif node.virtual:
			
			t = types.unwrap(node.fun.type.over[1][0])
			vtp = self.gep(wrapped, 0, 0)
			vtt = '%%%s.vt*' % t.name
			vt = self.varname()
			self.writeline('%s = load %s* %s' % (vt, vtt, vtp))
			fp = self.gep((vtt, vt), 0, 0)
			
			ft = copy.copy(node.fun.type)
			ft.over = ft.over[0], (types.get('&byte'),) + ft.over[1][1:]
			fun = self.load(Value(types.ref(ft), fp))
			type, name = fun.type, fun.var
		
		argstr = ', '.join('%s %s' % (a.type.ir, a.var) for a in args)
		if rtype == types.void():
			self.writeline('call %s %s(%s)' % (type.ir, name, argstr))
			if node.args and isinstance(node.args[0], typer.Init):
				return args[0]
			else:
				return None
		
		if rvar is not None:
			self.writeline('call void %s(%s)' % (name, argstr))
			return rvar
		
		res = self.varname()
		bits = res, type.ir, name, argstr
		self.writeline('%s = call %s %s(%s)' % bits)
		return Value(rtype, res)
	
	def Function(self, node, frame):
		
		self.vars = 0
		self.labels.clear()
		irname = node.name.name
		if hasattr(node, 'irname'):
			irname = node.irname
		
		ctxt, self.intercept = None, None
		if node.flow.yields:
			ctxt = types.ALL[irname + '$ctx']
			self.intercept = Value(types.ref(ctxt), '%ctx')
		
		rt = node.rtype.ir
		if irname == 'main' and rt == 'void':
			rt = 'i32'
		
		args = ['%s %%%s' % (a.type.ir, a.name.name) for a in node.args]
		if irname == 'main' and node.args:
			args = ['i32 %argc', 'i8** %argv']
		elif ctxt is not None:
			args = ['%s %%ctx' % (types.ref(ctxt).ir)]
		
		if rt.startswith('%tuple$'):
			args.insert(0, '%s* %%$R' % rt)
			rt = 'void'
		
		bits = rt, irname, ', '.join(args)
		self.writeline('define %s @%s(%s) uwtable {' % bits)
		self.indent()
		
		frame = Frame(frame)
		if self.intercept is not None:
			
			self.label('Prologue')
			slot = self.gep(self.intercept, 0, 0)
			addr = self.load(Value(types.get('&&byte'), slot))
			
			targets = [0] + node.flow.yields.values()
			labels = ', '.join('label %%L%s' % v for v in targets)
			bits = addr.type.ir, addr.var, labels
			self.writeline('indirectbr %s %s, [ %s ]' % bits)
		
		self.label('L0', 'entry')
		if irname == 'main' and node.args:
			
			strt = types.get('&str')
			addrp = self.gep(('i8**', '%argv'), 0)
			addr = self.load(Value(types.get('&&byte'), addrp))
			name = self.alloca(strt.over)
			
			wrapfun = '@str.__init__$Rstr.Obyte'
			bits = wrapfun, strt.ir, name.var, addr.var
			self.writeline('call void %s(%s %s, i8* %s)' % bits)
			frame['name'] = name
			
			args = self.alloca(types.get('$array[str]'))
			direct = self.varname()
			call = '%s = call %%array$str* @args(i32 %%argc, i8** %%argv)'
			self.writeline(call % direct)
			self.store(('%array$str*', direct), args.var)
			frame['args'] = args
		
		elif node.args and ctxt is None:
			for arg in node.args:
				addr = self.alloca(arg.type)
				frame[arg.name.name] = addr
				self.store((arg.type, '%' + arg.name.name), addr.var)
		
		self.main = node if irname == 'main' else None
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
		cast = 'i8* bitcast (%s* @%s.data to i8*)' % (dtype, name)
		bits = name, self.word, slen, cast
		self.writeline('@%s = constant %%str { %s %s, %s }' % bits)
		frame[name] = Value(val.type, '@%s' % name)
	
	def declare(self, ref):
		
		if ref.decl.startswith('runa.'):
			return
		
		rtype = ref.type.over[0].ir
		args = ', '.join(t.ir for t in ref.type.over[1])
		self.writeline('declare %s @%s(%s)' % (rtype, ref.decl, args))
		
	def type(self, type):
		
		if isinstance(type, types.WRAPPERS):
			return
		if isinstance(type, types.opt):
			return
		
		if type.name == 'array[str]':
			# predefined for args creation function
			return
		
		if type.name.startswith('array['):
			s = self.word + ', [0 x %s]' % type.attribs['data'][1].over.ir
			self.writeline('%s = type { %s }' % (type.ir, s))
			return
		
		if type.name.startswith('iter['):
			bits = type.ir, type.params[0].ir
			self.writeline('%s = type { i1, %s }' % bits)
			return
		
		if type.name.startswith('tuple['):
			name, ttypes = type.ir, [t.ir for t in type.params]
			self.writeline('%s = type { %s }' % (name, ', '.join(ttypes)))
			return
		
		fields = sorted(type.attribs.itervalues())
		s = ', '.join([i[1].ir for i in fields])
		self.writeline('%s = type { %s }' % (type.ir, s))
		
		t = type.ir
		gep = '%s* getelementptr (%s* null, i32 1)' % (t, t)
		cast = 'constant %s ptrtoint (%s to %s)' % (self.word, gep, self.word)
		self.writeline('@%s.size = %s' % (t[1:], cast))
		self.newline()
	
	def trait(self, t):
		
		mtypes = []
		for name, malts in sorted(t.methods.iteritems()):
			for fun in malts:
				
				args = []
				for an, at in zip(fun.type.args, fun.type.over[1]):
					args.append(types.get('&byte') if an == 'self' else at)
				
				mtypes.append(types.function(fun.type.over[0], args).ir)
		
		self.writeline('%%%s.vt = type { %s }' % (t.name, ', '.join(mtypes)))
		self.writeline('%%%s.wrap = type { %%%s.vt*, i8* }' % (t.name, t.name))
		self.newline()
	
	def ctx(self, mod, t):
		
		name = t.name[:-4].split('.')
		key = name[0] if len(name) == 1 else tuple(name)
		fun = None
		for k, v in mod.code:
			if k == key:
				fun = v
				break
		
		assert fun is not None
		vars = {}
		for i, bl in fun.flow.blocks.iteritems():
			for step in bl.steps:
				nodes = [step]
				node = nodes.pop(0)
				while node:
					
					if isinstance(node, ast.Name):
						vars[node.name] = node.type
					
					if not node.fields:
						node = None if not nodes else nodes.pop(0)
						continue
					
					fields = list(node.fields)
					nodes += [getattr(node, k) for k in fields]
					node = None if not nodes else nodes.pop(0)
		
		t.attribs['$label'] = 0, types.get('&byte')
		for i, (name, type) in enumerate(vars.iteritems()):
			t.attribs[name] = i + 1, type
		
		self.type(t)
	
	def Module(self, mod):
		
		for k, v in mod.names.iteritems():
			if isinstance(v, types.FunctionDef):
				self.declare(v)
		
		self.newline()
		deps = {}
		for k, v in mod.names.iteritems():
			if k in types.BASIC:
				deps[k] = None
			elif isinstance(v, types.base):
				atypes = {a[1] for a in v.attribs.itervalues()}
				tdeps = {types.unwrap(t) for t in atypes}
				deps[k] = v, {t for t in tdeps if t.name not in types.BASIC}
		
		remains = {k for (k, v) in deps.iteritems() if v is not None}
		while remains:
			
			done = set()
			for k in remains:
				if not deps[k][1]:
					self.type(deps[k][0])
					done.add(deps[k][0])
			
			assert done
			for k in remains:
				for t in done:
					if t in deps[k][1]:
						deps[k][1].remove(t)
			
			remains -= {t.name for t in done}
		
		for k, v in mod.names.iteritems():
			if isinstance(v, types.trait):
				self.trait(v)
		
		for var in mod.variants:
			if var.name.endswith('$ctx'):
				self.ctx(mod, var)
			else:
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
	('64bit', 'darwin'): 'x86_64-apple-macosx10.10.0',
	('64bit', 'linux2'): 'x86_64-pc-linux-gnu',
	('32bit', 'linux2'): 'i386-pc-linux-gnu',
}

def generate(mod):
	
	arch, os_key = platform.architecture()[0], sys.platform
	word = 'i' + arch[:2]
	gen = CodeGen(word)
	gen.Module(mod)
	
	code = ['target triple = "%s"\n\n' % TRIPLES[arch, os_key]]
	code += gen.typedecls
	
	with open(os.path.join(util.CORE_DIR, 'rt.ll')) as f:
		src = f.read().replace('{{ WORD }}', word)
		src = src.replace('{{ BYTES }}', str(int(arch[:2]) / 8))
		code.append(src)
	
	code += gen.buf
	return ''.join(code)
