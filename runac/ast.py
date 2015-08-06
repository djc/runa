'''Contains classes for all the syntax tree node types used in the parser.

All classes have a `pos` field containing location information. It can be
None in nodes that have been inserted by the compiler. Classes should have
a `fields` attribute containing a sequence of properties that either contain
another AST node or a list of AST nodes, so we can walk the tree somehow.

Some node types are defined in other modules:

- blocks: SetAttr, Branch, CondBranch, Phi, Constant, LoopSetup, LoopHeader,
          LPad
- typer: Init
- destructor: Free

For files containing source code, a File node is at the root of the tree.
'''

from . import util

# Base class

IGNORE = {'pos'}

class Registry(type):
	types = []
	def __init__(cls, name, bases, dict):
		Registry.types.append(cls)

class Node(util.AttribRepr):
	__metaclass__ = Registry
	def __init__(self, pos):
		self.pos = pos
	def __hash__(self):
		values = tuple(sorted((k, v) for (k, v) in util.items(self.__dict__)))
		return hash((self.__class__.__name__,) + values)

class Expr(Node):
	fields = ()
	def __init__(self, pos):
		Node.__init__(self, pos)
		self.type = None
		self.escapes = False

class NoneVal(Expr):
	pass

class Bool(Expr):
	def __init__(self, val, pos):
		Expr.__init__(self, pos)
		self.val = True if val == 'True' else False

class Int(Expr):
	def __init__(self, num, pos):
		Expr.__init__(self, pos)
		self.val = num

class Float(Expr):
	def __init__(self, num, pos):
		Expr.__init__(self, pos)
		self.val = num

class String(Expr):
	def __init__(self, value, pos):
		Expr.__init__(self, pos)
		self.val = value

class Name(Expr):
	def __init__(self, name, pos):
		Expr.__init__(self, pos)
		self.name = name

# Expression-level

class Attrib(Expr):
	fields = 'obj',

class Elem(Expr):
	fields = 'obj', 'key'

class Add(Expr):
	fields = 'left', 'right'

class Sub(Expr):
	fields = 'left', 'right'

class Mul(Expr):
	fields = 'left', 'right'

class Div(Expr):
	fields = 'left', 'right'

class Mod(Expr):
	fields = 'left', 'right'

class BWAnd(Expr):
	fields = 'left', 'right'

class BWOr(Expr):
	fields = 'left', 'right'

class BWXor(Expr):
	fields = 'left', 'right'

class Not(Expr):
	fields = 'value',

class Owner(Expr):
	fields = 'value'

class Ref(Expr):
	fields = 'value'

class Opt(Expr):
	fields = 'value'

class Mut(Expr):
	fields = 'value'

class In(Expr):
	fields = 'left', 'right'

class And(Expr):
	fields = 'left', 'right'

class Or(Expr):
	fields = 'left', 'right'

class Is(Expr):
	fields = 'left', 'right'

class EQ(Expr):
	fields = 'left', 'right'

class NE(Expr):
	fields = 'left', 'right'

class LT(Expr):
	fields = 'left', 'right'

class GT(Expr):
	fields = 'left', 'right'

class As(Expr):
	fields = 'left',

class Tuple(Expr):
	fields = 'values',

class Call(Expr):
	fields = 'args',

class NamedArg(Expr):
	fields = 'val', # plus non-field 'name'

# Statement-level

class Assign(Node):
	fields = 'left', 'right'

class IAdd(Node):
	fields = 'left', 'right'

class Raise(Node):
	fields = 'value',

class Yield(Node):
	fields = 'value',

class Except(Node):
	fields = 'type', 'suite'

class Suite(Node):
	fields = 'stmts',

class Argument(Node):
	fields = 'name',
	def __init__(self, pos):
		Node.__init__(self, pos)
		self.type = None

class Decl(Node):
	fields = 'decor', 'name', 'args', 'rtype'

class TryBlock(Node):
	fields = 'suite', 'catch'

class Function(Node):
	fields = 'decor', 'name', 'args', 'rtype', 'suite'

class Break(Node):
	fields = ()

class Continue(Node):
	fields = ()

class Pass(Node):
	fields = ()

class Return(Node):
	fields = 'value',

class Ternary(Expr):
	fields = 'cond', 'values'

class If(Node):
	fields = 'blocks',

class Import(Node):
	fields = 'names',

class RelImport(Node):
	fields = 'base', 'names'

class For(Node):
	fields = 'lvar', 'source', 'suite'

class While(Node):
	fields = 'cond', 'suite'

class Class(Node):
	fields = 'decor', 'name', 'params', 'attribs', 'methods'

class Trait(Node):
	fields = 'decor', 'name', 'params', 'methods'

class File(Node):
	fields = 'suite',
	def __init__(self):
		self.suite = []
