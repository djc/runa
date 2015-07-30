'''Type inferencing and type checking pass.

This pass tries to add type information to all nodes in the syntax trees.
In order to do so, it needs to reference declarations of external modules
(for example,
functions in the tiny run-time library in ``core/rt.ll`` and libc).
It also needs to resolve scoping issues.
There should generally be three scope levels:
global-level, for core types and functions that are always available,
module-level, for other stuff in the module, and function-level.
In addition,
the ``TypeChecker`` analysis currently uses per-block scope mappings
to track data.

The core of this pass is the ``TypeChecker`` tree-walking class,
which walks over a CFG,
tries to infer types and then checks if the types make sense.
Some of the complexity here is in resolving variables,
as evidenced in the ``Name()`` method.
Types are generally represented as instances of ``types.base()`` objects;
compatibility is best checked using ``types.compat()``.

Note that inferencing and checking aren't at all the same thing,
but since you have to do a lot of checking while inferencing anyway,
it felt best to do both at the same time.
Some variables, however,
are only inferred to a type of ``anyint`` or ``anyfloat``
(in case no further information is present).
This means type checking cannot always be precise in this phase,
and the specialization phase,
which transforms the any* types to specific types, should check.

It is considered imperative to provide good error messages about type errors
(whether inferencing or checking).
Error messages should try to return good location information and
provide enough context to be actionable.
'''

from . import types, ast, blocks, util
import copy

class Init(ast.Expr):
	def __init__(self, type):
		ast.Expr.__init__(self, None)
		self.type = type

class Declarations(util.AttribRepr):
	def __init__(self, name, init):
		self.name = name
		self.attribs = init

def declare(name, rtype, atypes):
	
	node = ast.Decl(None)
	node.name = ast.Name(name, None)
	node.rtype = rtype
	
	node.args = []
	for t in atypes:
		arg = ast.Argument(None)
		arg.type = t
		node.args.append(arg)
	
	return node

ROOT = Declarations('', {
	'__internal__': Declarations('__internal__', {
		'__malloc__': declare('Runa.rt.malloc', '$byte', ('uint',)),
		'__free__': declare('Runa.rt.free', 'void', ('$byte',)),
		'__memcpy__': declare('Runa.rt.memcpy', 'void', (
			'&byte', '&byte', 'uint'
		)),
		'__offset__': declare('Runa.rt.offset', '&byte', ('&byte', 'uint')),
		'__raise__': declare('Runa.rt.raise', 'void', ('$Exception',)),
		'__typeid__': declare('llvm.eh.typeid.for', 'i32', ('&byte',)),
		'__args__': declare('Runa.rt.args', '&array[Str]', ('i32', '&&byte')),
	}),
	'libc': Declarations('libc', {
		'stdlib': Declarations('libc.stdlib', {
			'getenv': declare('getenv', '&byte', ('&byte',)),
		}),
		'stdio': Declarations('libc.stdio', {
			'snprintf': declare('snprintf', 'i32', (
				'&byte', 'i32', '&byte', '...'
			)),
		}),
		'string': Declarations('libc.string', {
			'strncmp': declare('strncmp', 'i32', ('&byte', '&byte', 'uint')),
			'strlen': declare('strlen', 'uint', ('&byte',)),
		}),
		'unistd': Declarations('libc.unistd', {
			'write': declare('write', 'int', ('i32', '&byte', 'uint')),
		}),
	}),
})

class TypeChecker(object):
	
	def __init__(self, mod, fun, scope):
		self.mod = mod
		self.fun = fun
		self.flow = fun.flow
		self.scope = scope
		self.cur = None, None
		self.checked = {}
	
	def check(self):
		for i, b in sorted(util.items(self.flow.blocks)):
			for sid, step in enumerate(b.steps):
				self.cur = b, sid
				self.visit(step)
	
	def visit(self, node):
		getattr(self, node.__class__.__name__)(node)
	
	def checkopt(self, posnode, val):
		if self.checked.get((self.cur[0].id, val.name)):
			val.type = val.type.over
			return
		if isinstance(val.type, types.opt):
			msg = "opt type '%s' not allowed here"
			raise util.Error(posnode, msg % val.type.name)
	
	def settype(self, name, type):
		bid, sid = self.cur[0].id, self.cur[1]
		sets = self.flow.vars[name]['sets']
		assert sid in sets.get(bid, {}), name
		sets[bid][sid] = type
	
	# Constants
	
	def Name(self, node, strict=True):
		
		defined, blocks = [], []
		origins = self.flow.origins(node.name, (self.cur[0].id, self.cur[1]))
		if not origins and node.name in self.scope:
			node.type = self.scope[node.name].type
			return
		
		for id in origins:
			
			if self.cur[0].id < id:
				continue
			
			sets = self.flow.vars[node.name]['sets'][id]
			if id == self.cur[0].id:
				if self.cur[1] <= min(sets):
					continue
				sets = {s: t for (s, t) in util.items(sets) if s < self.cur[1]}
			
			blocks.append(id)
			defined.append(sets[max(sets)])
		
		if not strict:
			defined = [i for i in defined if i is not None]
		if not defined or not all(defined):
			raise util.Error(node, "undefined name '%s'" % node.name)
		
		first = defined[0]
		for n in defined:
			if not types.compat(n, first):
				msg = "unmatched types '%s', '%s' on incoming branches"
				raise util.Error(node, msg % (n.name, first.name))
		
		# Deopt for all incoming edges where check is True
		
		opts = [isinstance(n, types.opt) for n in defined]
		if any(opts):
			for (i, opt) in enumerate(opts):
				
				if not opt:
					continue
				
				bid = blocks[i]
				if bid == self.cur[0].id:
					continue
				
				checks = self.flow.checks.get((bid, self.cur[0].id), {})
				if checks.get(node.name):
					opts[i] = False
			
			if not any(opts):
				first = first.over
		
		if node.type is not None and node.type != first:
			assert False, (node, first)
		
		node.type = first
	
	def NoneVal(self, node):
		node.type = self.mod.type('NoType')
	
	def Bool(self, node):
		node.type = self.mod.type('bool')
	
	def Int(self, node):
		node.type = types.anyint()
	
	def Float(self, node):
		node.type = types.anyfloat()
	
	def String(self, node):
		node.type = types.owner(self.mod.type('Str'))
	
	def Tuple(self, node):
		for v in node.values:
			self.visit(v)
		node.type = self.mod.type(('tuple', (v.type for v in node.values)))
	
	def NamedArg(self, node):
		self.visit(node.val)
		node.type = node.val.type
	
	# Boolean operators
	
	def Not(self, node):
		self.visit(node.value)
		node.type = self.mod.type('bool')
	
	def boolean(self, op, node):
		self.visit(node.left)
		self.visit(node.right)
		if node.left.type == node.right.type:
			node.type = node.left.type
		else:
			node.type = self.mod.type('bool')
	
	def And(self, node):
		self.boolean('and', node)
	
	def Or(self, node):
		self.boolean('or', node)
	
	# Comparison operators
	
	def Is(self, node):
		
		self.visit(node.left)
		self.visit(node.right)
		assert isinstance(node.right, ast.NoneVal), node.right
		
		if not isinstance(node.left.type, types.opt):
			assert isinstance(node.left.type, types.WRAPPERS), node.left
		
		node.type = self.mod.type('bool')
	
	def compare(self, op, node):
		
		self.visit(node.left)
		self.visit(node.right)
		
		lt, rt = types.unwrap(node.left.type), types.unwrap(node.right.type)
		if node.left.type == node.right.type:
			node.type = self.mod.type('bool')
		elif lt in types.INTS and rt not in types.INTS:
			msg = "value of type '%s' may only be compared to integer type"
			raise util.Error(node, msg % node.left.type.name)
		elif lt in types.FLOATS and rt not in types.FLOATS:
			msg = "value of type '%s' may only be compared to float type"
			raise util.Error(node, msg % node.left.type.name)
		elif lt not in types.INTS and lt not in types.FLOATS:
			msg = "types '%s' and '%s' cannot be compared"
			raise util.Error(node, msg % (lt.name, rt.name))
		
		node.type = self.mod.type('bool')
	
	def EQ(self, node):
		self.compare('eq', node)
	
	def NE(self, node):
		self.compare('ne', node)
	
	def LT(self, node):
		self.compare('lt', node)
	
	def GT(self, node):
		self.compare('gt', node)
	
	# Arithmetic operators
	
	def arith(self, op, node):
		
		self.visit(node.left)
		self.visit(node.right)
		
		lt, rt = types.unwrap(node.left.type), types.unwrap(node.right.type)
		if node.left.type == node.right.type:
			node.type = node.left.type
		elif lt in types.INTS:
			assert rt in types.INTS
			node.type = node.left.type
		else:
			assert False, op + ' sides different types'
	
	def Add(self, node):
		self.arith('add', node)
	
	def Sub(self, node):
		self.arith('sub', node)
	
	def Mod(self, node):
		self.arith('mod', node)
	
	def Mul(self, node):
		self.arith('mul', node)
	
	def Div(self, node):
		self.arith('div', node)
	
	# Bitwise operators
	
	def bitwise(self, op, node):
		
		self.visit(node.left)
		self.visit(node.right)
		
		lt, rt = types.unwrap(node.left.type), types.unwrap(node.right.type)
		if node.left.type == node.right.type:
			node.type = node.left.type
		elif lt in types.INTS:
			assert rt in types.INTS
			node.type = node.left.type
		else:
			msg = "bitwise operations do not apply to '%s', '%s'"
			raise util.Error(node, msg % (lt.name, rt.name))
		
		node.type = node.left.type
	
	def BWAnd(self, node):
		self.bitwise('and', node)
	
	def BWOr(self, node):
		self.bitwise('or', node)
	
	def BWXor(self, node):
		self.bitwise('xor', node)
	
	# Iteration-related nodes
	
	def Yield(self, node):
		self.visit(node.value)
		if not types.compat(node.value.type, self.fun.rtype.params[0]):
			msg = 'yield value type does not match declared type\n'
			msg += "    '%s' vs '%s'"
			bits = node.value.type.name, self.fun.rtype.params[0].name
			raise util.Error(node.value, msg % bits)

	def LoopSetup(self, node):
		
		self.visit(node.loop.source)
		t = types.unwrap(node.loop.source.type)
		if not t.name.startswith('iter['):
			call = ast.Call(None)
			call.name = ast.Attrib(None)
			call.name.obj = node.loop.source
			call.name.attrib = '__iter__'
			call.args = []
			call.fun = None
			call.virtual = None
			self.visit(call)
			node.loop.source = call
		
		name = node.loop.source.fun.name + '$ctx'
		node.type = self.mod.type(name)
	
	def LoopHeader(self, node):
		
		name = node.lvar.name
		vart = node.ctx.type.yields
		origins = self.flow.origins(name, (self.cur[0].id, self.cur[1]))
		if origins:
			assert False, 'reassignment of loop variable'
		
		self.settype(name, vart)
		node.lvar.type = vart
	
	# Miscellaneous
	
	def As(self, node):
		self.visit(node.left)
		node.type = self.mod.type(node.right)
		# TODO: check if the conversion makes sense
	
	def Raise(self, node):
		self.visit(node.value)
		assert node.value is not None
	
	def Attrib(self, node):
		
		self.visit(node.obj)
		self.checkopt(node, node.obj)
		
		t = node.obj.type
		if isinstance(t, types.WRAPPERS):
			t = t.over
		
		node.type = t.attribs[node.attrib][1]
		assert node.type is not None, 'FAIL'
		if isinstance(node.type, types.owner):
			node.type = types.ref(node.type.over)
	
	def SetAttr(self, node):
		
		self.visit(node.obj)
		self.checkopt(node, node.obj)
		
		t = node.obj.type
		if isinstance(t, types.WRAPPERS):
			t = t.over
		
		node.type = t.attribs[node.attrib][1]
		assert node.type is not None, 'FAIL'
	
	def Elem(self, node):
		
		self.visit(node.key)
		self.visit(node.obj)
		self.checkopt(node, node.obj)
		
		objt = types.unwrap(node.obj.type)
		if not objt.name.startswith('array['):
			msg = 'incorrect type for element protocol: %s'
			raise util.Error(node, msg % objt.name)
		
		node.type = objt.attribs['data'][1].over
	
	def args(self, args):
		
		positional, named = [], {}
		for a in args:
			if isinstance(a, ast.NamedArg):
				named[a.name] = a.val.type
			elif named:
				msg = 'positional arguments must come before named arguments'
				raise util.Error(a, msg)
			else:
				positional.append(a.type)
		
		return positional, named
	
	def Call(self, node):
		
		# Make sure to visit all arguments so that types are available
		
		for arg in node.args:
			self.visit(arg)
		
		# Figuring out what function to call, there are three cases...
		
		positional, named = self.args(node.args)
		if isinstance(node.name, ast.Attrib):
			
			# 1. Calling a method: figure out the type of the object, then find
			# the appropriate method to call for the given arguments.
			
			if node.name.obj.type is None:
				self.visit(node.name.obj)
			
			assert isinstance(node.name.obj.type, types.base), node.name.obj
			t = types.unwrap(node.name.obj.type)
			if isinstance(t, types.trait):
				node.virtual = True
			
			node.args.insert(0, node.name.obj)
			positional, named = self.args(node.args)
			node.fun = t.select(node, node.name.attrib, positional, named)
			node.type = node.fun.type.over[0]
		
		else:
			
			self.visit(node.name)
			allowed = types.function, types.Type
			if not isinstance(node.name.type, allowed):
				msg = 'object is not a function'
				raise util.Error(node.name, msg)
			
			# 2. Calling a normal function, this is the simple case.
			
			obj = self.scope[node.name.name]
			if not isinstance(obj, types.base):
				node.fun = obj
				node.type = node.fun.type.over[0]
			else:
				# 3. Calling a type constructor.
				node.fun = obj.select(node, '__init__', positional, named)
				node.name.name = node.fun.decl
				node.type = types.owner(obj)
				if '__init__' in node.fun.decl:
					node.args.insert(0, Init(types.owner(obj)))
					positional, named = self.args(node.args)
			
			if isinstance(obj, types.FunctionDecl):
				node.name.name = obj.name
		
		# Rebuild arguments by putting named arguments in correct order
		
		if named:
			
			new, names = [], {}
			for arg in node.args:
				if not isinstance(arg, ast.NamedArg):
					new.append(arg)
				else:
					names[arg.name] = arg.val
			
			for aname in node.fun.type.args[len(new):]:
				new.append(names[aname])
			
			node.args = new
		
		# Check that the actual types match the function's formal types
		
		actual = [a.type for a in node.args]
		if not types.compat(actual, node.fun.type.over[1]):
			astr = ', '.join(t.name for t in actual)
			fstr = ', '.join(t.name for t in node.fun.type.over[1])
			msg = 'arguments (%s) cannot be passed as (%s)'
			raise util.Error(node, msg % (astr, fstr))
		
		# If any arguments were of the owner type, render them inaccessible
		
		for i, (a, f) in enumerate(zip(actual, node.fun.type.over[1])):
			if isinstance(f, types.owner):
				
				if not isinstance(node.args[i], ast.Name):
					continue
				
				var_data = self.flow.vars[node.args[i].name]
				clear = var_data.setdefault('clear', {})
				clear.setdefault(self.cur[0].id, set()).add(self.cur[1])
	
	def CondBranch(self, node):
		self.visit(node.cond)
	
	def Assign(self, node):
		
		self.visit(node.right)
		if isinstance(node.left, ast.Tuple):
			
			ttypes, pos = [], (self.cur[0].id, self.cur[1])
			assert node.right.type.name.startswith('tuple[')
			for i, dst in enumerate(node.left.values):
				
				assert isinstance(dst, ast.Name)
				t = node.right.type.params[i]
				origins = self.flow.origins(dst.name, pos)
				if origins:
					assert False, 'reassignment in tuple assignment'
				
				assert t is not None
				self.settype(dst.name, t)
				dst.type = t
				ttypes.append(t)
			
			node.left.type = self.mod.type(('tuple', ttypes))
			return
		
		new, var = False, isinstance(node.left, ast.Name)
		try:
			self.visit(node.left)
		except util.Error as e:
			if not e.msg.startswith('undefined name'):
				raise
			new = True
		
		assert node.right.type is not None
		if not new and not types.compat(node.right.type, node.left.type):
			if not var:
				bits = node.right.type.name, node.left.type.name
				msg = 'incorrect assignment of %s to %s'
			else:
				bits = node.left.type.name, node.right.type.name
				msg = "reassignment with different type ('%s' vs '%s')"
			raise util.Error(node, msg % bits)
		
		if var:
			self.settype(node.left.name, node.right.type)
		node.left.type = node.right.type
	
	def IAdd(self, node):
		self.visit(node.left)
		self.visit(node.right)
		if not types.compat(node.right.type, node.left.type):
			bits = node.right.type.name, node.left.type.name
			raise util.Error(node, "cannot add '%s' to '%s'" % bits)
	
	def Phi(self, node):
		
		if isinstance(node.left[1], ast.Name):
			self.Name(node.left[1], strict=False)
		else:
			self.visit(node.left[1])
		
		if isinstance(node.right[1], ast.Name):
			self.Name(node.right[1], strict=False)
		else:
			self.visit(node.right[1])
		
		if node.left[1].type == node.right[1].type:
			node.type = node.left[1].type
			return
		
		no_type = self.mod.type('NoType').__class__
		if isinstance(node.left[1].type, no_type):
			node.type = types.opt(node.right[1].type)
			return
		elif isinstance(node.right[1].type, no_type):
			node.type = types.opt(node.left[1].type)
			return
		
		bits = tuple(i.type.name for i in (node.left[1], node.right[1]))
		raise util.Error(node, "unmatched types '%s', '%s'" % bits)
	
	def LPad(self, node):
		for type in node.map:
			t = self.mod.type(type)
			assert t.name == 'Exception'
	
	def Resume(self, node):
		pass
	
	def Branch(self, node):
		return
	
	def Pass(self, node):
		return
	
	def Return(self, node):
		
		if self.flow.yields:
			assert node.value is None
			return
		
		if node.value is None and self.fun.rtype != types.void():
			msg = "function may not return value of type 'void'"
			raise util.Error(node, msg)
		elif node.value is not None and self.fun.rtype == types.void():
			msg = "function must return type 'void' ('%s' not allowed)"
			self.visit(node.value)
			raise util.Error(node.value, msg % (node.value.type.name))
		elif node.value is None:
			return
		
		self.visit(node.value)
		if not types.compat(node.value.type, self.fun.rtype):
			msg = "return value type does not match declared return type\n"
			msg += "    '%s' vs '%s'"
			bits = node.value.type.name, self.fun.rtype.name
			raise util.Error(node.value, msg % bits)

VOID = {'__init__', '__del__'}

def process(mod, base, fun, cls):
	
	# Some methods must have return type 'void'
	
	if fun.name.name in VOID and fun.rtype is not None:
		msg = "method '%s' must return type 'void'"
		raise util.Error(fun.rtype, msg % fun.name.name)
	
	# If this is a method on a template class, figure out type substitutions
	
	stubs = {}
	if cls is not None and isinstance(cls, types.template):
		stubs = {k: types.Stub(k) for k in cls.params}
	
	# Set the type object for the return type
	
	if fun.rtype is None:
		fun.rtype = types.void()
	elif not isinstance(fun.rtype, types.base):
		fun.rtype = mod.type(fun.rtype, stubs)
	
	# Add arguments
	
	for arg in fun.args:
		
		if not isinstance(arg.type, types.base):
			arg.type = mod.type(arg.type, stubs)
		
		var_data = fun.flow.vars.setdefault(arg.name.name, {})
		assert -1 in var_data.get('sets', {})[None]
		var_data.setdefault('sets', {})[None] = {-1: arg.type}
	
	# If this is a generator, prepare a context class to hold state
	# across invocations. This will contain all the live variables.
	
	if fun.flow.yields:
		
		if cls is not None:
			defn = cls.methods[fun.name.name][0]
		else:
			defn = base[fun.name.name]
		
		name = fun.irname + '$ctx'
		mod.scope[name] = type(name, (types.concrete,), {
			'name': name,
			'ir': '%' + name,
			'yields': fun.rtype.params[0],
			'function': defn,
			'attribs': {}
		})()
	
	# Run the type inferencing & type checking process
	
	TypeChecker(mod, fun, base).check()

def typer(mod):
	
	# Start by adding types to type dictionary
	
	for k, v in util.items(mod):
		if isinstance(v, (ast.Class, ast.Trait)):
			mod.scope[k] = types.create(v)
	
	# Next, set up module scope and imported redirections
	
	for name, obj in util.items(mod):
		
		if not isinstance(obj, str):
			continue
		
		ns = ROOT
		path = obj.split('.')
		while len(path) > 1:
			ns = ns.attribs[path.pop(0)]
		
		val = ns.attribs[path[0]]
		assert isinstance(val, ast.Decl)
		mod[name] = val
	
	# Add constants to module scope
	
	for k, v in util.items(mod):
		if not isinstance(v, blocks.Constant):
			continue
		if isinstance(v.node, ast.String):
			v.type = v.node.type = mod.type('&Str')
		elif isinstance(v.node, ast.Int):
			v.type = v.node.type = mod.type('&int')
		else:
			assert False, v.node
		mod.scope[k] = v
	
	# Build types for classes and traits
	
	for k, v in util.items(mod):
		if isinstance(v, (ast.Class, ast.Trait)):
			types.fill(mod, v)
	
	# Build function definitions from declarations
	
	if mod.name == 'Runa.core':
		for k in ('__free__', '__raise__', '__typeid__', '__args__'):
			decl = ROOT.attribs['__internal__'].attribs[k]
			mod.scope[k] = types.FunctionDecl.from_decl(mod, decl)
	
	for k, v in util.items(mod):
		if isinstance(v, ast.Decl):
			mod.scope[k] = types.FunctionDecl.from_decl(mod, v)
	
	for k, fun in mod.code:
		
		# Build FunctionDecl objects and set IR name for module-level functions
		# (for methods, this has already been done during type filling)
		
		if not isinstance(k, tuple):
			mod.scope[fun.name.name] = types.FunctionDecl.from_ast(mod, fun)
			fun.irname = mod.scope[fun.name.name].decl
		
		# Check function signature invariants for main() and methods
		
		if k == 'main':
			
			rtype, atypes = mod.scope[fun.name.name].type.over
			if fun.args and atypes[0] != types.ref(mod.scope['Str']):
				msg = '1st argument to main() must be of type &Str'
				raise util.Error(fun.args[0].type, msg)
			
			compare = mod.type('&array[Str]')
			if fun.args and atypes[1] != compare:
				msg = '2nd argument to main() must be of type &array[Str]'
				raise util.Error(fun.args[1].type, msg)
			
			if rtype not in {types.void(), mod.scope['i32']}:
				raise util.Error(fun, 'main() return type must be i32')
	
		if isinstance(k, tuple) and k[1] != '__new__':
			if not fun.args:
				raise util.Error(fun, "missing 'self' argument")
			elif fun.args[0].name.name != 'self':
				msg = "first method argument must be called 'self'"
				raise util.Error(fun.args[0], msg)
			elif fun.args[0].type is not None:
				if fun.args[0].type.name != k[0]:
					msg = "first method argument must be of type '%s'"
					raise util.Error(fun.args[0].type, msg % k[0])
		
		if fun.args and fun.args[0].type is None:
			if fun.name.name == '__del__':
				fun.args[0].type = types.owner(mod.scope[k[0]])
			else:
				fun.args[0].type = types.ref(mod.scope[k[0]])
	
	# Handle type checking and inferencing of actual function code
	# (needs to be done after add function declarations for each function)
	
	for k, fun in mod.code:
		cls = mod.type(k[0]) if isinstance(k, tuple) else None
		process(mod, mod.scope, fun, cls)
