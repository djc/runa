import sys, ast, tokenizer

TRIPLES = {
	'darwin': 'x86_64-apple-darwin11.0.0',
	'linux2': 'x86_64-pc-linux-gnu',
}

class Type(object):
	
	class base(object):
		@property
		def name(self):
			return self.__class__.__name__
		def __repr__(self):
			return '<type: %s>' % self.__class__.__name__
		def __eq__(self, other):
			classes = self.__class__, other.__class__
			return classes[0] == classes[1] and self.__dict__ == other.__dict__
		def __ne__(self, other):
			return not self.__eq__(other)
	
	class int(base):
		ir = 'i64'
		methods = {
			'__bool__': ('@int.__bool__', 'bool', 'int'),
		}
	
	class void(base):
		ir = 'void'
	
	class str(base):
		ir = '%str'
		methods = {
			'__bool__': ('@str.__bool__', 'bool', 'str'),
		}
	
	class bool(base):
		ir = 'i1'
	
	class array(base):
		def __init__(self, over):
			self.over = over
		@property
		def ir(self):
			return self.over.ir + '*'
	
	class intiter(base):
		ir = '%intiter'
		methods = {
			'__next__': ('@intiter.__next__', 'int', 'intiter'),
		}

TYPES = {}
for t in dir(Type):
	if t[0] == '_': continue
	TYPES[t] = getattr(Type, t)

BYVAL = {'int'}

LIBRARY = {
	'print': ('void', 'str'),
	'str': ('str', 'int'),
	'range': ('intiter', 'int', 'int', 'int'),
}

class Value(object):
	def __init__(self, type, ptr=None, val=None):
		self.type = type
		self.ptr = ptr
		self.val = val
	def __repr__(self):
		s = ['<value[%s] ' % self.type.name]
		if self.ptr:
			s.append('ptr=' + self.ptr)
		if self.val:
			s.append('val=' + self.val)
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
	
	def String(self, node):
		
		id = self.id('str')
		l = len(node.value)
		type = '[%i x i8]' % l
		bits = [id + '_data', '=', 'constant']
		bits += ['%s c"%s"\n' % (type, node.value)]
		self.lines.append(' '.join(bits))
		
		data = type, id
		bits = [id, '=', 'constant', Type.str().ir]
		bits.append('{ i64 %s,' % l)
		bits.append('i8* getelementptr(%s* %s_data, i32 0, i32 0)}\n' % data)
		self.lines.append(' '.join(bits))
		return Value(Type.str(), ptr=id)
	
	def Int(self, node):
		id = self.id('num')
		bits = id, Type.int().ir, node.val
		self.lines.append('%s = constant %s %s\n' % bits)
		return Value(Type.int(), ptr=id)

class Frame(object):
	
	def __init__(self, parent=None):
		self.vars = 1
		self.labels = 1
		self.parent = parent
		self.defined = {}
	
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
		self.write(ln + '\n')
		self.start = True
	
	def writelines(self, lines):
		self.buf.append(('\n' + self.tabs()).join(lines))
	
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
		if op == 'div':
			op = 'sdiv'
		
		left = self.value(args[0], frame)
		right = self.value(args[1], frame)
		
		rtype = args[0].type
		store = frame.varname()
		bits = store, op, rtype.ir, left.split()[1], right.split()[1]
		self.writeline('%s = %s %s %s, %s' % bits)
		return Value(args[0].type, val=store)
	
	def boolean(self, val, frame):
		
		if val.type == Type.bool():
			return val
		
		assert '__bool__' in val.type.methods
		if val.type.name in BYVAL:
			arg = self.value(val, frame)
		else:
			arg = self.ptr(val, frame)
		
		boolean = frame.varname()
		method = val.type.methods['__bool__']
		self.write(boolean + ' = call i1 ' + method[0] + '(' + arg + ')')
		self.newline()
		return Value(Type.bool(), val=boolean)

	def value(self, val, frame):
		if not val.val:
			val.val = frame.varname()
			bits = (val.val, val.type.ir + '*', val.ptr)
			self.writeline('%s = load %s %s' % bits)
		return val.type.ir + ' ' + val.val
	
	def ptr(self, val, frame):
		if not val.ptr:
			val.ptr = frame.varname()
			self.writeline('%s = alloca %s' % (val.ptr, val.type.ir))
			val.val = None
		return val.type.ir + '* ' + val.ptr
	
	# Node visitation methods
	
	def String(self, node, frame):
		return self.const.String(node)
	
	def Int(self, node, frame):
		return self.const.Int(node)
	
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
	
	def Assign(self, node, frame):
		frame[node.left.name] = self.visit(node.right, frame)
	
	def Elem(self, node, frame):
		
		obj = self.visit(node.obj, frame)
		key = self.visit(node.key, frame)
		bits = self.ptr(obj, frame), self.value(key, frame)
		self.writeline('%%tmp.ptr = getelementptr %s, %s' % bits)
		
		res = frame.varname()
		self.writeline('%s = load %%str** %%tmp.ptr' % res)
		return Value(obj.type.over, ptr=res)
	
	def Not(self, node, frame):
		val = self.boolean(self.visit(node.value, frame), frame)
		arg = self.value(val, frame)
		res = frame.varname()
		self.writeline(res + ' = select %s, i1 false, i1 true' % arg)
		return Value(Type.bool(), val=res)
	
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
		return Value(left.type if typed else Type.bool(), ptr=finvar)
	
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
		return Value(left.type if typed else Type.bool(), ptr=finvar)
	
	def Call(self, node, frame):
		
		# set up args before reserving variable
		seq = []
		args = self.args(node.args, frame)
		for val in args:
			if val.type.name in BYVAL:
				seq.append(self.value(val, frame))
			else:
				seq.append(self.ptr(val, frame))
		
		rtype = TYPES[LIBRARY[node.name.name][0]]()
		rval = Value(rtype)
		if rtype != Type.void():
			store = frame.varname()
			self.writeline('%s = alloca %s' % (store, rtype.ir))
			rval = Value(rtype, ptr=store)
			seq.append(self.ptr(rval, frame))
		
		call = '@' + node.name.name + '(' + ', '.join(seq) + ')'
		self.writeline(' '.join(('call void', call)))
		return rval
	
	def Return(self, node, frame):
		value = self.visit(node.value, frame)
		bits = self.value(value, frame), value.type.ir + '*', '%lang.res'
		self.writeline('store %s, %s %s' % bits)
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
		self.newline()
		
		next = source.type.methods['__next__']
		lval = Value(TYPES[next[1]](), ptr='%' + node.lvar.name)
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
		
		
	
	def main(self, node, frame):
		
		decl = 'define i32 @main(i32 %argc, i8** %argv) nounwind ssp {'
		self.writeline(decl)
		self.indent()
		
		frame = Frame()
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
		
		frame['name'] = Value(Type.str(), ptr='%a0.p')
		frame['args'] = Value(Type.array(Type.str()), ptr='%args')
		self.visit(node.suite, frame)
		
		self.writeline('ret i32 0')
		self.dedent()
		self.writeline('}')
	
	def Function(self, node, frame):
		
		frame = Frame(frame)
		if node.name.name == '__main__':
			return self.main(node, frame)
		
		self.write('define void @')
		self.write(node.name.name)
		self.write('(')
		
		first = True
		for arg in node.args:
			if not first: self.write(', ')
			atype = TYPES[arg.type.name]()
			self.write(atype.ir)
			self.write(' ')
			self.write('%' + arg.name.name)
			if atype.name in BYVAL:
				val = Value(atype, val='%' + arg.name.name)
			else:
				val = Value(atype, ptr='%' + arg.name.name)
			frame[arg.name.name] = val
			first = False
		
		self.write(', ')
		self.write(TYPES[node.rtype.name].ir + '*')
		self.write(' %lang.res')
		
		self.write(') {')
		self.newline()
		self.indent()
		
		self.visit(node.suite, frame)
		
		self.dedent()
		self.writeline('}')
		self.newline()
	
	def Module(self, node, frame=None):
		
		defined = {}
		for n in node.suite:
			if isinstance(n, ast.Function):
				defined[n.name.name] = n
				if n.name.name == '__main__': continue
				atypes = tuple(a.type.name for a in n.args)
				LIBRARY[n.name.name] = (n.rtype.name,) + atypes
		
		frame = Frame()
		for name, n in defined.iteritems():
			self.visit(n, frame)
		
		lines = self.const.lines + ['\n'] + self.buf
		return ''.join(lines).split('\n')

def layout(data):
	bits = []
	for decl in data:
		bits.append(':'.join(str(i) for i in decl))
	return '-'.join(bits)

def prologue(mod):
	return ['target triple = "%s"' % TRIPLES[sys.platform]]

def include():
	return open('include.ll').read().splitlines() + ['']

def stdlib():
	return open('std.ll').read().splitlines()[2:] + ['']

def source(mod):
	lines = prologue(mod) + ['']
	lines += include()
	lines += CodeGen().Module(mod)
	return '\n'.join(lines)

if __name__ == '__main__':
	print source(ast.fromfile(sys.argv[1]))
