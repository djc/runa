import sys, ast, tokenizer

TRIPLES = {
	'darwin': 'x86_64-apple-darwin11.0.0',
	'linux2': 'x86_64-pc-linux-gnu',
}

class Type(object):
	
	class base(object):
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
		ir = '%str*'
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

TYPES = {}
for t in dir(Type):
	if t[0] == '_': continue
	TYPES[t] = getattr(Type, t)

LIBRARY = {
	'print': ('void', 'str'),
	'str': ('str', 'int'),
}

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
		bits = [id, '=', 'constant', Type.str().ir[:-1]]
		bits.append('{ i64 %s,' % l)
		bits.append('i8* getelementptr(%s* %s_data, i32 0, i32 0)}\n' % data)
		self.lines.append(' '.join(bits))
		return Type.str(), id
	
	def Int(self, node):
		id = self.id('num')
		bits = id, Type.int().ir, node.val
		self.lines.append('%s = constant %s %s\n' % bits)
		return Type.int(), id

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
	
	def label(self, label):
		self.dedent()
		self.writeline('%s:' % label)
		self.indent()
	
	# Other helper methods
	
	def args(self, nodes, frame):
		return [self.visit(i, frame) for i in nodes]
	
	def binop(self, node, frame, op):
		
		args = self.args((node.left, node.right), frame)
		if op == 'div':
			op = 'sdiv'
		
		rtype = args[0][0]
		store = frame.varname()
		bits = store, op, rtype.ir, args[0][1], args[1][1]
		self.writeline('%s = %s %s %s, %s' % bits)
		return rtype, store
	
	def boolean(self, val, frame):
		
		if val[0] == Type.bool():
			return val
		
		assert '__bool__' in val[0].methods
		boolean = frame.varname()
		method = val[0].methods['__bool__']
		self.write(boolean + ' = call i1 ' + method[0] + '(')
		self.write(val[0].ir + ' ' + val[1] + ')')
		self.newline()
		return Type.bool(), boolean
	
	# Node visitation methods
	
	def String(self, node, frame):
		return self.const.String(node)
	
	def Int(self, node, frame):
		const = self.const.Int(node)
		bits = frame.varname(), const[0].ir, const[1]
		self.writeline('%s = load %s* %s' % bits)
		return Type.int(), bits[0]
	
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
		if isinstance(node.right, ast.Int):
			const = self.const.Int(node.right)
			bits = node.left.name, const[0].ir, const[1]
			self.writeline('%%%s = load %s* %s' % bits)
			frame[node.left.name] = Type.int(), '%' + node.left.name
		else:
			res = self.visit(node.right, frame)
			frame[node.left.name] = res
	
	def Elem(self, node, frame):
		
		obj = self.visit(node.obj, frame)
		key = self.visit(node.key, frame)
		res = frame.varname()
		
		bits = obj[0].ir, obj[1], key[0].ir, key[1]
		self.writeline('%%tmp.ptr = getelementptr %s %s, %s %s' % bits)
		self.writeline('%s = load %%str** %%tmp.ptr' % res)
		return obj[0].over, res
	
	def Not(self, node, frame):
		val = self.boolean(self.visit(node.value, frame), frame)
		res = frame.varname()
		self.writeline(res + ' = select i1 %s, i1 false, i1 true' % val[1])
		return Type.bool(), res
	
	def Ternary(self, node, frame):
		
		cond = self.boolean(self.visit(node.cond, frame), frame)
		lif, lelse = frame.labelname(), frame.labelname()
		lfin = frame.labelname()
		
		self.newline()
		self.write('br i1 ' + cond[1] + ', ')
		self.write('label %%%s, label %%%s' % (lif, lelse))
		self.newline()
		
		self.label(lif)
		left = self.visit(node.values[0], frame)
		self.writeline('br label %%%s' % lfin)
		self.label(lelse)
		right = self.visit(node.values[1], frame)
		self.writeline('br label %%%s' % lfin)
		assert left[0] == right[0]
		
		self.label(lfin)
		finvar = frame.varname()
		self.write('%s = phi ' % finvar)
		self.write(left[0].ir)
		self.write(' [ %s, %%%s ], ' % (left[1], lif))
		self.write('[ %s, %%%s ]' % (right[1], lelse))
		self.newline()
		self.newline()
		
		return left[0], finvar
	
	def And(self, node, frame):
		
		lif, lelse, lfin = [frame.labelname() for i in range(3)]
		self.newline()
		left = self.visit(node.left, frame)
		lbool = self.boolean(left, frame)
		self.write('br i1 ' + lbool[1] + ', ')
		self.write('label %%%s, label %%%s' % (lif, lelse))
		self.newline()
		
		self.label(lif)
		right = self.visit(node.right, frame)
		rbool = self.boolean(right, frame)
		typed = left[0] == right[0]
		self.writeline('br label %%%s' % lfin)
		
		self.label(lelse)
		self.writeline('br label %%%s' % lfin)
		
		self.label(lfin)
		finvar = frame.varname()
		self.write('%s = phi ' % finvar)
		if typed:
			self.write(left[0].ir)
			self.write(' [ %s, %%%s ],' % (right[1], lif))
			self.write(' [ %s, %%%s ]' % (left[1], lelse))
		else:
			self.write('i1')
			self.write(' [ %s, %%%s ],' % (rbool[1], lif))
			self.write(' [ %s, %%%s ]' % (lbool[1], lelse))
		
		self.newline()
		self.newline()
		return (left[0] if typed else lbool[0]), finvar
	
	def Or(self, node, frame):
		
		lif, lelse, lfin = [frame.labelname() for i in range(3)]
		self.newline()
		left = self.visit(node.left, frame)
		lbool = self.boolean(left, frame)
		self.write('br i1 ' + lbool[1] + ', ')
		self.write('label %%%s, label %%%s' % (lif, lelse))
		self.newline()
		
		self.label(lif)
		self.writeline('br label %%%s' % lfin)
		
		self.label(lelse)
		right = self.visit(node.right, frame)
		rbool = self.boolean(right, frame)
		typed = left[0] == right[0]
		self.writeline('br label %%%s' % lfin)
		
		self.label(lfin)
		finvar = frame.varname()
		self.write('%s = phi ' % finvar)
		if typed:
			self.write(left[0].ir)
			self.write(' [ %s, %%%s ],' % (left[1], lif))
			self.write(' [ %s, %%%s ]' % (right[1], lelse))
		else:
			self.write('i1')
			self.write(' [ %s, %%%s ],' % (lbool[1], lif))
			self.write(' [ %s, %%%s ]' % (rbool[1], lelse))
		
		self.newline()
		self.newline()
		return (left[0] if typed else lbool[0]), finvar
	
	def Call(self, node, frame):
		
		# set up args before reserving variable
		args = self.args(node.args, frame)
		irt = [(a[0].ir, a[1]) for a in args]
		args = ', '.join('%s %s' % a for a in irt)
		
		store, start = None, 'call'
		void = LIBRARY[node.name.name][0] == 'void'
		if not void:
			store = frame.varname()
			start = '%s = call' % store
		
		call = '@' + node.name.name + '(' + args + ')'
		rtype = TYPES[LIBRARY[node.name.name][0]]()
		self.writeline(' '.join((start, rtype.ir, call)))
		return rtype, store
	
	def Return(self, node, frame):
		value = self.visit(node.value, frame)
		self.writeline('ret %s %s' % (value[0].ir, value[1]))
	
	def Suite(self, node, frame):
		for stmt in node.stmts:
			self.visit(stmt, frame)
	
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
		
		frame['name'] = Type.str(), '%name'
		frame['args'] = Type.array(Type.str()), '%args'
		self.visit(node.suite, frame)
		
		self.writeline('ret i32 0')
		self.dedent()
		self.writeline('}')
	
	def Function(self, node, frame):
		
		frame = Frame(frame)
		if node.name.name == '__main__':
			return self.main(node, frame)
		
		self.write('define ')
		self.write(TYPES[node.rtype.name].ir)
		self.write(' @')
		self.write(node.name.name)
		self.write('(')
		
		first = True
		for arg in node.args:
			if not first: self.write(', ')
			self.write(TYPES[arg.type.name].ir)
			self.write(' ')
			self.write('%' + arg.name.name)
			bits = TYPES[arg.type.name](), '%' + arg.name.name
			frame[arg.name.name] = bits
			first = False
		
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
		
		lines = self.const.lines + ['\n', '\n'] + self.buf
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

def source(mod):
	lines = prologue(mod) + ['']
	lines += include()
	lines += CodeGen().Module(mod)
	return '\n'.join(lines)

if __name__ == '__main__':
	print source(ast.fromfile(sys.argv[1]))
