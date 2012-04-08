import ast, types

LIBRARY = {
	'print': ('@print', 'void', 'str'),
	'str': ('@str', 'str', 'int'),
	'range': ('@range', 'intiter', 'int', 'int', 'int'),
	'open': ('@fopen', 'file', 'str'),
	'strtoi': ('@strtoi', 'int', 'str'),
}

PROTOCOL = {
	'bool': '__bool__',
	'str': '__str__',
}

class Value(object):
	def __init__(self, type, ptr=None, val=None, var=False, const=False):
		self.type = type
		self.ptr = ptr
		self.val = val
		self.var = var
		self.const = const
		self.code = []
	def __repr__(self):
		s = ['<value[%s]' % self.type.name]
		if self.ptr:
			s.append(' ptr=' + self.ptr)
		if self.val:
			s.append(' val=' + self.val)
		s.append('>')
		return ''.join(s)

class Constants(object):
	
	def __init__(self):
		self.next = 0
		self.lines = []
	
	def id(self, type):
		s = '@%s%s' % (type, self.next)
		self.next += 1
		return s
	
	def Bool(self, node, name=None):
		id = self.id('bool') if name is None else ('@' + name)
		val = '1' if node.val else '0'
		self.lines.append('%s = constant i1 %s\n' % (id, val))
		return Value(types.bool(), ptr=id, const=True)
	
	def Int(self, node, name=None):
		id = self.id('int') if name is None else ('@' + name)
		bits = id, types.int().ir, node.val
		self.lines.append('%s = constant %s %s\n' % bits)
		return Value(types.int(), ptr=id, const=True)
	
	def Float(self, node, name=None):
		id = self.id('flt') if name is None else ('@' + name)
		bits = id, types.float().ir, node.val
		self.lines.append('%s = constant %s %s\n' % bits)
		return Value(types.float(), ptr=id, const=True)
	
	def String(self, node, name=None):
		
		id = self.id('str') if name is None else ('@' + name)
		l = len(node.value)
		type = '[%i x i8]' % l
		bits = [id + '_data', '=', 'constant']
		bits += ['%s c"%s"\n' % (type, node.value)]
		self.lines.append(' '.join(bits))
		
		data = type, id
		bits = [id, '=', 'constant', types.str().ir]
		bits.append('{ i1 0, i64 %s,' % l)
		bits.append('i8* getelementptr(%s* %s_data, i32 0, i32 0)}\n' % data)
		self.lines.append(' '.join(bits))
		return Value(types.str(), ptr=id, const=True)

class Frame(object):
	
	def __init__(self, parent=None):
		self.vars = 1
		self.labels = 1
		self.parent = parent
		self.defined = {}
		self.allocated = []
	
	def __contains__(self, key):
		return key in self.defined or (self.parent and key in self.parent)
	
	def __getitem__(self, key):
		if key not in self.defined:
			return self.parent[key]
		return self.defined[key]
	
	def __setitem__(self, key, value):
		self.defined[key] = value
	
	def varname(self):
		self.vars += 1
		return '%%%i' % (self.vars - 1)
	
	def labelname(self):
		self.labels += 1
		return 'L%i' % (self.labels - 1)

class CodeGen(object):
	
	def __init__(self):
		self.buf = []
		self.level = 0
		self.start = True
		self.const = Constants()
	
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
	
	# Other helper methods
	
	def args(self, nodes, frame):
		return [self.visit(i, frame) for i in nodes]
	
	def binop(self, node, frame, op):
		args = self.args((node.left, node.right), frame)
		mdata = args[0].type.methods['__' + op + '__']
		assert args[1].type == types.ALL[mdata[2]]()
		return self.call((args[0].type, '__' + op + '__'), args, frame)
	
	def boolean(self, val, frame):
		if val.type == types.bool():
			return val
		return self.call(('bool',), [val], frame)
	
	def materialize(self, val, name, alloc=True):
		if alloc and not val.var:
			self.writeline('%s = alloca %s' % (name, val.type.ir))
		for ln in val.code:
			self.writeline(ln.replace('%RET', name))
		return Value(val.type, ptr=name)
	
	def value(self, val, frame):
		if val.code:
			val = self.materialize(val, frame.varname())
		if not val.val:
			res = frame.varname()
			bits = (res, val.type.ir + '*', val.ptr)
			self.writeline('%s = load %s %s' % bits)
			if not val.var:
				val.val = res
		return val.type.ir + ' ' + (val.val if val.val else res)
	
	def ptr(self, val, frame):
		if val.code:
			val = self.materialize(val, frame.varname())
		assert val.ptr
		return val.type.ir + '* ' + val.ptr
	
	def cleanups(self, *args):
		lines = []
		for val in args:
			if not val.ptr: continue
			if val.var or val.const: continue
			if '__del__' not in val.type.methods: continue
			method = val.type.methods['__del__']
			ir = '%s* %s' % (val.type.ir, val.ptr)
			lines.append('call void %s(%s)' % (method[0], ir))
		return lines
	
	def call(self, fun, args, frame):
		
		seq = []
		for i, val in enumerate(args):
			if val.code:
				val = args[i] = self.materialize(val, frame.varname())
			if val.type.byval:
				seq.append(self.value(val, frame))
			else:
				seq.append(self.ptr(val, frame))
		
		if fun[0] in PROTOCOL:
			objtype = args[0].type
			name, rtype = objtype.methods[PROTOCOL[fun[0]]][:2]
		elif fun[0] in LIBRARY:
			name, rtype = LIBRARY[fun[0]][:2]
		elif isinstance(fun[0], types.base):
			name, rtype = fun[0].methods[fun[1]][:2]
		elif fun[0] in types.ALL:
			type = types.ALL[fun[0]]()
			rval = Value(type, ptr='%RET')
			if '__init__' not in type.methods:
				rval.code = ['']
			else:
				name = type.methods['__init__'][0]
				seq.insert(0, '%s* %%RET' % type.ir)
				call = 'call void ' + name + '(' + ', '.join(seq) + ')'
				rval.code = [call]
			return rval
		else:
			assert False, 'unknown function %s' % fun
		
		rtype = types.ALL[rtype]()
		rval = Value(rtype)
		if rtype != types.void():
			rval = Value(rtype, ptr='%RET')
			seq.append(self.ptr(rval, frame))
		
		call = 'call void ' + name + '(' + ', '.join(seq) + ')'
		lines = [call] + self.cleanups(*args)
		if rtype == types.void():
			self.writelines(lines)
		else:
			rval.code = lines
		
		return rval
	
	# Node visitation methods
	
	def Bool(self, node, frame):
		return self.const.Bool(node)
	
	def Int(self, node, frame):
		return self.const.Int(node)
	
	def Float(self, node, frame):
		return self.const.Float(node)
	
	def String(self, node, frame):
		return self.const.String(node)
	
	def Name(self, node, frame):
		return frame[node.name]
	
	def Add(self, node, frame):
		return self.binop(node, frame, 'add')
	
	def Sub(self, node, frame):
		return self.binop(node, frame, 'sub')
	
	def Mul(self, node, frame):
		return self.binop(node, frame, 'mul')
	
	def Div(self, node, frame):
		return self.binop(node, frame, 'div')
	
	def Eq(self, node, frame):
		return self.binop(node, frame, 'eq')
	
	def NEq(self, node, frame):
		arg = self.value(self.binop(node, frame, 'eq'), frame)
		res = frame.varname()
		self.writeline(res + ' = select %s, i1 false, i1 true' % arg)
		return Value(types.bool(), val=res)
	
	def LT(self, node, frame):
		return self.binop(node, frame, 'lt')
	
	def Assign(self, node, frame, const=False):
		
		if const:
			assert isinstance(node.left, ast.Name)
			ctype = node.right.__class__.__name__
			assert hasattr(self.const, ctype)
			fun = getattr(self.const, ctype)
			frame[node.left.name] = fun(node.right, node.left.name)
			return
		
		val = self.visit(node.right, frame)
		type = val.type
		
		if isinstance(node.left, ast.Name):
			name = '%' + node.left.name
			if name[1:] not in frame:
				self.writeline('%s = alloca %s' % (name, type.ir))
			target = Value(type, ptr=name, var=True)
		else:
			target = self.visit(node.left, frame)
			if target.code:
				name = frame.varname()
				target = self.materialize(target, name, alloc=False)
		
		if val.code:
			val = self.materialize(val, name, False)
		else:
			val = self.value(val, frame)
			self.writeline('store %s, %s* %s' % (val, type.ir, name))
		
		frame[name[1:]] = Value(type, ptr=name, var=True)
	
	def Elem(self, node, frame):
		
		obj = self.visit(node.obj, frame)
		key = self.visit(node.key, frame)
		bits = self.ptr(obj, frame), self.value(key, frame)
		self.writeline('%%tmp.ptr = getelementptr %s, %s' % bits)
		
		res = frame.varname()
		self.writeline('%s = load %%str** %%tmp.ptr' % res)
		return Value(obj.type.over, ptr=res)
	
	def Attrib(self, node, frame):
		
		obj = self.visit(node.obj, frame)
		idx, atype = obj.type.attribs[node.attrib.name]
		
		rval = Value(atype(), ptr='%RET', var=True)
		bits = self.ptr(obj, frame), idx
		rval.code = ['%%RET = getelementptr %s, i32 0, i32 %s' % bits]
		return rval
	
	def Not(self, node, frame):
		val = self.boolean(self.visit(node.value, frame), frame)
		arg = self.value(val, frame)
		res = frame.varname()
		self.writeline(res + ' = select %s, i1 false, i1 true' % arg)
		return Value(types.bool(), val=res)
	
	def Ternary(self, node, frame):
		
		cond = self.boolean(self.visit(node.cond, frame), frame)
		lif, lelse = frame.labelname(), frame.labelname()
		lfin = frame.labelname()
		
		self.newline()
		cval = self.value(cond, frame)
		self.write('br ' + cval + ', ')
		self.write('label %%%s, label %%%s' % (lif, lelse))
		self.newline()
		
		self.label(lif, 'ternary-if')
		left = self.visit(node.values[0], frame)
		self.writeline('br label %%%s' % lfin)
		self.label(lelse, 'ternary-else')
		right = self.visit(node.values[1], frame)
		self.writeline('br label %%%s' % lfin)
		assert left.type == right.type
		
		self.label(lfin, 'ternary-fin')
		finvar = frame.varname()
		self.write('%s = phi ' % finvar)
		self.write(left.type.ir + '*')
		self.write(' [ %s, %%%s ], ' % (left.ptr, lif))
		self.write('[ %s, %%%s ]' % (right.ptr, lelse))
		self.newline()
		self.newline()
		
		return Value(left.type, ptr=finvar)
	
	def And(self, node, frame):
		
		lif, lelse, lfin = [frame.labelname() for i in range(3)]
		self.newline()
		left = self.visit(node.left, frame)
		lbool = self.value(self.boolean(left, frame), frame)
		self.write('br ' + lbool + ', ')
		self.write('label %%%s, label %%%s' % (lif, lelse))
		self.newline()
		
		self.label(lif, 'and-true')
		right = self.visit(node.right, frame)
		self.writeline('br label %%%s' % lfin)
		
		self.label(lelse, 'and-false')
		self.writeline('br label %%%s' % lfin)
		
		self.label(lfin, 'and-fin')
		finvar = frame.varname()
		typed = left.type == right.type
		if typed:
			self.write('%s = phi ' % finvar)
			self.write(left.type.ir + '*')
			self.write(' [ %s, %%%s ],' % (right.ptr, lif))
			self.write(' [ %s, %%%s ]' % (left.ptr, lelse))
		else:
			rbool = self.value(self.boolean(right, frame), frame)
			self.write('%s = phi i1' % finvar)
			self.write(' [ %s, %%%s ],' % (rbool.split()[1], lif))
			self.write(' [ %s, %%%s ]' % (lbool.split()[1], lelse))
		
		self.newline()
		self.newline()
		return Value(left.type if typed else types.bool(), ptr=finvar)
	
	def Or(self, node, frame):
		
		lif, lelse, lfin = [frame.labelname() for i in range(3)]
		self.newline()
		left = self.visit(node.left, frame)
		lbool = self.value(self.boolean(left, frame), frame)
		self.write('br ' + lbool + ', ')
		self.write('label %%%s, label %%%s' % (lif, lelse))
		self.newline()
		
		self.label(lif, 'or-true')
		self.writeline('br label %%%s' % lfin)
		self.label(lelse, 'or-false')
		right = self.visit(node.right, frame)
		self.writeline('br label %%%s' % lfin)
		
		self.label(lfin, 'or-fin')
		finvar = frame.varname()
		typed = left.type == right.type
		if typed:
			self.write('%s = phi ' % finvar)
			self.write(left.type.ir + '*')
			self.write(' [ %s, %%%s ],' % (left.ptr, lif))
			self.write(' [ %s, %%%s ]' % (right.ptr, lelse))
		else:
			rbool = self.value(self.boolean(right, frame), frame)
			self.write('%s = phi i1' % finvar)
			self.write(' [ %s, %%%s ],' % (lbool.split()[1], lif))
			self.write(' [ %s, %%%s ]' % (rbool.split()[1], lelse))
		
		self.newline()
		self.newline()
		return Value(left.type if typed else types.bool(), ptr=finvar)
	
	def Call(self, node, frame):
		
		args = self.args(node.args, frame)
		if isinstance(node.name, ast.Name):
			return self.call((node.name.name,), args, frame)
		
		if isinstance(node.name, ast.Attrib):
			obj = self.visit(node.name.obj, frame)
			fun = obj.type, node.name.attrib.name
			return self.call(fun, [obj] + args, frame)
		
		else:
			assert False, "don't know how to call %s" % node.name
	
	def Return(self, node, frame):
		value = self.visit(node.value, frame)
		self.materialize(value, '%lang.res', False)
		self.writeline('ret void')
	
	def Suite(self, node, frame):
		for stmt in node.stmts:
			self.visit(stmt, frame)
	
	def If(self, node, frame):
		
		lnext = frame.labelname()
		lfin = frame.labelname()
		for i, (cond, suite) in enumerate(node.blocks):
			
			lbranch = lnext
			if len(node.blocks) > i + 1:
				lnext = frame.labelname()
			else:
				lnext = lfin
			
			if cond is not None:
				if i:
					self.label(lbranch, 'if-cond-%s' % i)
					lbranch = frame.labelname()
				condvar = self.boolean(self.visit(cond, frame), frame)
				condval = self.value(condvar, frame)
				self.write('br ' + condval + ', ')
				self.write('label %%%s, label %%%s' % (lbranch, lnext))
				self.newline()
			
			self.label(lbranch, 'if-suite-%s' % i)
			self.visit(suite, frame)
			self.writeline('br label %%%s' % lfin)
		
		self.label(lfin, 'if-fin')
	
	def For(self, node, frame):
		
		source = self.visit(node.source, frame)
		if source.code:
			source = self.materialize(source, frame.varname())
		
		self.newline()
		next = source.type.methods['__next__']
		lval = Value(types.ALL[next[1]](), ptr='%' + node.lvar.name)
		frame.defined[node.lvar.name] = lval
		self.writeline('%s = alloca %s' % (lval.ptr, lval.type.ir))
		
		lhead, lbody, lend = [frame.labelname() for i in range(3)]
		self.writeline('br label %%%s' % lhead)
		
		self.label(lhead, 'for-head')
		cont = frame.varname()
		bits = cont, next[0], self.ptr(source, frame), self.ptr(lval, frame)
		self.writeline('%s = call i1 %s(%s, %s)' % bits)
		bits = cont, lbody, lend
		self.writeline('br i1 %s, label %%%s, label %%%s' % bits)
		
		self.label(lbody, 'for-body')
		self.visit(node.suite, frame)
		self.writeline('br label %%%s' % lhead)
		self.label(lend, 'for-end')
	
	def While(self, node, frame):
		
		self.newline()
		lhead, lbody, lend = [frame.labelname() for i in range(3)]
		self.writeline('br label %%%s' % lhead)
		
		self.label(lhead, 'while-head')
		cond = self.visit(node.cond, frame)
		check = self.value(self.boolean(cond, frame), frame)
		bits = check, lbody, lend
		self.writeline('br %s, label %%%s, label %%%s' % bits)
		
		self.label(lbody, 'while-body')
		self.visit(node.suite, frame)
		self.writeline('br label %%%s' % lhead)
		self.label(lend, 'while-end')
	
	def main(self, node, frame):
		
		decl = 'define i32 @main(i32 %argc, i8** %argv) nounwind ssp {'
		self.writeline(decl)
		self.indent()
		
		frame = Frame(frame)
		self.writeline('%args$ = alloca %str*')
		args = 'i32 %argc', 'i8** %argv', '%str** %args$'
		self.writeline('call void @argv(%s)' % ', '.join(args))
		
		lines = [
			'%a0.p = load %str** %args$, align 8',
			'%name = getelementptr inbounds %str* %a0.p, i64 0',
			'%a1.p = getelementptr inbounds %str* %a0.p, i64 1',
			'%args = alloca %str*',
			'store %str* %a1.p, %str** %args',
		]
		
		for ln in lines:
			self.writeline(ln)
		
		frame['name'] = Value(types.str(), ptr='%a0.p', var=True)
		frame['args'] = Value(types.array(types.str()), ptr='%args', var=True)
		self.visit(node.suite, frame)
		
		self.writeline('ret i32 0')
		self.dedent()
		self.writeline('}')
	
	def Class(self, node, frame):
		pass
	
	def Function(self, node, frame):
		
		frame = Frame(frame)
		if node.name.name == 'main':
			return self.main(node, frame)
		
		name = '@' + node.name.name
		if hasattr(node, 'irname'):
			name = node.irname
		self.write('define void %s(' % name)
		
		first = True
		for arg in node.args:
			
			if not first:
				self.write(', ')
			
			atype = types.ALL[arg.type.name]()
			self.write(atype.ir)
			if not atype.byval: self.write('*')
			self.write(' ')
			self.write('%' + arg.name.name)
			
			if atype.byval:
				val = Value(atype, val='%' + arg.name.name)
			else:
				val = Value(atype, ptr='%' + arg.name.name)
			
			frame[arg.name.name] = val
			first = False
		
		if node.rtype:
			self.write(', ')
			self.write(types.ALL[node.rtype.name].ir + '*')
			self.write(' %lang.res')
		
		self.write(') {')
		self.newline()
		self.indent()
		
		self.visit(node.suite, frame)
		if not node.rtype:
			self.writeline('ret void')
		
		self.dedent()
		self.writeline('}')
		self.newline()
	
	def declare(self, type):
		fields = sorted(type.attribs.itervalues())
		s = ', '.join([i[1].ir for i in fields])
		self.writeline('%%%s = type { %s }' % (type.name, s))
	
	def Module(self, node, frame=None):
		
		defined = {}
		frame = Frame()
		
		typedefs = False
		for n in node.suite:
			
			if isinstance(n, ast.Class):
				
				typedefs = True
				self.declare(types.add(n))
				for method in n.methods:
					defined[method.irname] = method
			
			elif isinstance(n, ast.Function):
				
				defined[n.name.name] = n
				if n.name.name == 'main': continue
				atypes = tuple(a.type.name for a in n.args)
				data = ('@' + n.name.name, n.rtype.name) + atypes
				LIBRARY[n.name.name] = data
				
			elif isinstance(n, ast.Assign):
				self.Assign(n, frame, const=True)
		
		if typedefs: self.newline()
		for name, n in defined.iteritems():
			self.visit(n, frame)
		
		lines = self.const.lines + ['\n'] + self.buf
		return ''.join(lines).split('\n')

def source(mod):
	return '\n'.join(CodeGen().Module(mod))
