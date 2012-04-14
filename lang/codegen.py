from util import Error
import ast, types, flow

MAIN_SETUP = [
	'; convert argc/argv to argument array',
	'%args = alloca %array.str',
	'call void @argv(i32 %argc, i8** %argv, %array.str* %args)',
	'%a.data = getelementptr %array.str* %args, i32 0, i32 1',
	'%name = load %str** %a.data, align 8',
	'%a1.p = getelementptr inbounds %str* %name, i64 1',
	'%a.len.ptr = getelementptr %array.str* %args, i32 0, i32 0',
	'%a.len = load i64* %a.len.ptr',
	'%newlen = sub i64 %a.len, 1',
	'store i64 %newlen, i64* %a.len.ptr',
	'store %str* %a1.p, %str** %a.data',
]

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
	
	def bool(self, node, name=None):
		id = self.id('bool') if name is None else ('@' + name)
		value = '1' if node.value else '0'
		self.lines.append('%s = constant i1 %s\n' % (id, value))
		return Value(types.bool(), ptr=id, const=True)
	
	def int(self, node, name=None):
		id = self.id('int') if name is None else ('@' + name)
		bits = id, types.int().ir, node.value
		self.lines.append('%s = constant %s %s\n' % bits)
		return Value(types.int(), ptr=id, const=True)
	
	def float(self, node, name=None):
		id = self.id('flt') if name is None else ('@' + name)
		bits = id, types.float().ir, node.value
		self.lines.append('%s = constant %s %s\n' % bits)
		return Value(types.float(), ptr=id, const=True)
	
	def str(self, node, name=None):
		
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
	
	def add(self, value, name=None):
		return getattr(self, value.type.name)(value, name)

class Frame(object):
	
	def __init__(self, parent=None):
		self.vars = 1
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
	
	def value(self, val, frame):
		if not val.val:
			res = frame.varname()
			bits = (res, val.type.ir + '*', val.ptr)
			self.writeline('%s = load %s %s' % bits)
			if not val.var:
				val.val = res
		return val.type.ir + ' ' + (val.val if val.val else res)
	
	def ptr(self, val, frame):
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
			lines.append('call void @%s(%s)' % (method[0], ir))
		return lines
	
	def iwrap(self, atype, val, frame):
		
		self.writeline('; wrap %s in %s' % (val.type.name, atype.name))
		wobj = frame.varname()
		bits = wobj, atype.ir
		self.writeline('%s = alloca %s' % bits)
		
		vtptr = frame.varname()
		bits = vtptr, atype.ir, wobj
		self.writeline('%s = getelementptr %s* %s, i32 0, i32 0' % bits)
		
		bits = atype.vttype, atype.impl, val.type.name, atype.vttype, vtptr
		self.writeline('store %s* %s.%s, %s** %s' % bits)
		
		argptr = frame.varname()
		bits = argptr, atype.ir, wobj
		self.writeline('%s = getelementptr %s* %s, i32 0, i32 1' % bits)
		
		cast = frame.varname()
		bits = cast, self.ptr(val, frame)
		self.writeline('%s = bitcast %s to i8*' % bits)
		
		bits = cast, argptr
		self.writeline('store i8* %s, i8** %s' % bits)
		
		return Value(atype, ptr=wobj)
	
	def call(self, name, args, frame):
		
		if '.' not in name:
			meta = flow.LIBRARY[name]
			name, rtype, atypes = meta[0], meta[1], meta[2]
		else:
			tname, method = name.split('.', 1)
			type = types.get(tname)
			meta = type.methods[method]
			name, rtype, atypes = meta[0], meta[1], meta[2]
			atypes = [('self', type.name)] + atypes
		
		avals, seq = [], []
		for i, n in enumerate(args):
			
			arg = n
			if not isinstance(n, Value):
				arg = self.visit(n, frame)
			
			avals.append(arg)
			atype = types.get(atypes[i][1])
			if atype.iface:
				arg = self.iwrap(atype, arg, frame)
			
			seq.append(self.ptr(arg, frame))
		
		rval = Value(types.get(rtype))
		if rval.type != types.void():
			rval.ptr = frame.varname()
			self.writeline('%s = alloca %s' % (rval.ptr, rval.type.ir))
			seq.append(self.ptr(rval, frame))
		
		if '__next__' in name:
			call = '%loopvar = call i1 @' + name + '(' + ', '.join(seq) + ')'
		else:
			call = 'call void @' + name + '(' + ', '.join(seq) + ')'
		
		lines = [call] + self.cleanups(*avals)
		self.writelines(lines)
		
		return rval
	
	# Node visitation methods
	
	def Reference(self, node, frame):
		return frame[node.name]
	
	def Constant(self, node, frame):
		return self.const.add(node)
	
	def Call(self, node, frame):
		return self.call(node.name, node.args, frame)
	
	def Init(self, node, frame):
		var = frame.varname()
		self.writeline('%s = alloca %s' % (var, node.type.ir))
		val = Value(node.type, ptr=var)
		args = [val] + node.args
		self.call('%s.__init__' % node.type.name, args, frame)
		return val
	
	def Select(self, node, frame):
		
		cond = self.visit(node.cond, frame)
		selector = self.value(cond, frame)
		left = self.visit(node.left, frame)
		right = self.visit(node.right, frame)
		
		res = frame.varname()
		bits = res, selector, self.ptr(left, frame), self.ptr(right, frame)
		self.writeline('%s = select %s, %s, %s' % bits)
		return Value(node.type, ptr=res)
	
	def Math(self, node, frame):
		meta = node.type.methods['__' + node.op + '__']
		name = '%s.__%s__' % (node.type.name, node.op)
		return self.call(name, node.operands, frame)
	
	def Compare(self, node, frame):
		
		op = node.op if node.op != 'ne' else 'eq'
		meta = node.operands[0].type.methods['__' + op + '__']
		name = '%s.__%s__' % (node.operands[0].type.name, op)
		
		val = self.call(name, node.operands, frame)
		if node.op != 'ne':
			return val
		
		value = frame.varname()
		self.writeline('%s = load %s' % (value, self.ptr(val, frame)))
		inv = frame.varname()
		self.writeline('%s = select i1 %s, i1 false, i1 true' % (inv, value))
		res = frame.varname()
		self.writeline('%s = alloca i1' % res)
		self.writeline('store i1 %s, i1* %s' % (inv, res))
		return Value(types.bool(), ptr=res)
	
	def Assign(self, node, frame, const=False):
		
		val = self.visit(node.value, frame)
		type = val.type
		
		if isinstance(node.name, basestring):
			name = node.name
		else:
			name = node.name.name
		
		name = '%' + name
		if name[1:] not in frame:
			self.writeline('%s = alloca %s' % (name, type.ir))
		
		val = self.value(val, frame)
		self.writeline('store %s, %s* %s' % (val, type.ir, name))
		frame[name[1:]] = Value(type, ptr=name, var=True)
	
	def Manipulate(self, node, frame):
		
		obj = self.visit(node.obj, frame)
		attrib = obj.type.attribs[node.key]
		
		var = frame.varname()
		bits = var, self.ptr(obj, frame), attrib[0]
		self.writeline('%s = getelementptr %s, i32 0, i32 %i' % bits)
		
		val = self.visit(node.value, frame)
		tmp = frame.varname()
		self.writeline('%s = load %s' % (tmp, self.ptr(val, frame)))
		
		bits = val.type.ir, tmp, val.type.ir, var
		self.writeline('store %s %s, %s* %s' % bits)
	
	def Access(self, node, frame):
		
		if node.model == 'attr':
			obj = self.visit(node.obj, frame)
			idx, atype = obj.type.attribs[node.key]
			var = frame.varname()
			rval = Value(atype, ptr=var, var=True)
			bits = var, self.ptr(obj, frame), idx
			self.writeline('%s = getelementptr %s, i32 0, i32 %s' % bits)
			return rval
		
		obj = self.visit(node.obj, frame)
		key = self.visit(node.key, frame)
		
		bits = frame.varname(), obj.type.ir, obj.ptr
		self.writeline('%s = getelementptr %s* %s, i32 0, i32 1' % bits)
		bits = frame.varname(), bits[0]
		self.writeline('%s = load %%str** %s' % bits)
		
		keyval = self.value(key, frame)
		bits = frame.varname(), '%%str* %s' % bits[0], keyval
		self.writeline('%s = getelementptr %s, %s' % bits)
		return Value(obj.type.over, ptr=bits[0])
	
	def Return(self, node, frame):
		value = self.visit(node.value, frame)
		tmp = frame.varname()
		self.writeline('%s = load %s' % (tmp, self.ptr(value, frame)))
		bits = value.type.ir, tmp, value.type.ir
		self.writeline('store %s %s, %s* %%lang.res' % bits)
		self.writeline('ret void')
	
	def Suite(self, node, frame):
		for stmt in node.stmts:
			self.visit(stmt, frame)
	
	def Branch(self, node, frame):
		
		if isinstance(node.cond, ast.Name):
			bits = 'i1 %loopvar', node.left, node.right
			self.writeline('br %s, label %%L%s, label %%L%s' % bits)
			return
		
		if node.cond is None:
			self.writeline('br label %%L%s' % node.left)
			return
		
		cond = self.visit(node.cond, frame)
		cond = self.value(cond, frame)
		bits = cond, node.left, node.right
		self.writeline('br %s, label %%L%s, label %%L%s' % bits)
	
	def Function(self, node, frame):
		
		frame = Frame(frame)
		name = '@' + node.name
		self.write('define void %s(' % name)
		
		first = True
		names = {v: k for (k, v) in node.anames.iteritems()}
		for i, atype in enumerate(node.args):
			
			if not first:
				self.write(', ')
			
			self.write(atype.ir + '* %' + names[i])
			frame[names[i]] = Value(atype, ptr='%' + names[i])
			first = False
		
		if node.rtype != types.void():
			self.write(', ')
			self.write(node.rtype.ir + '*')
			self.write(' %lang.res')
		
		self.write(') {')
		self.newline()
		self.indent()
		
		for block in node.graph:
			self.visit(block, frame)
		
		if node.rtype == types.void():
			self.writeline('ret void')
		
		self.dedent()
		self.writeline('}')
		self.newline()
		
		args = [(names[i], t) for (i, t) in enumerate(node.args)]
		flow.LIBRARY[node.name] = node.name, node.rtype.name, args
	
	def Block(self, node, frame):
		if node.id:
			self.label('L%s' % node.id)
		for step in node.steps:
			self.visit(step, frame)
	
	def main(self, node, frame):
		
		decl = 'define i32 @main(i32 %argc, i8** %argv) nounwind ssp {'
		self.writeline(decl)
		self.indent()
		
		frame = Frame(frame)
		self.newline()
		for ln in MAIN_SETUP:
			self.writeline(ln)
		self.newline()
		
		frame['name'] = Value(types.str(), ptr='%name', var=True)
		frame['args'] = Value(types.array(types.str()), ptr='%args', var=True)
		for block in node.graph:
			self.visit(block, frame)
		
		self.writeline('ret i32 0')
		self.newline()
		self.dedent()
		self.writeline('}')
	
	def declare(self, type):
		fields = sorted(type.attribs.itervalues())
		s = ', '.join([i[1].ir for i in fields])
		self.writeline('%%%s = type { %s }\n' % (type.name, s))
	
	def Module(self, mod):
		
		frame = Frame()
		for type, name in mod.order:
			if type == 'fun':
				fun = mod.functions[name]
				process = self.main if name == 'main' else self.visit
				process(fun, frame)
			elif type == 'const':
				frame[name] = self.const.add(mod.const[name], name)
			elif type == 'class':
				self.declare(mod.types[name])
			else:
				assert False
		
		lines = self.const.lines + ['\n'] + self.buf
		return ''.join(lines)

def source(mod):
	return CodeGen().Module(mod)
