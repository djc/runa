from . import ast, util
import rply

NAME_LIKE = {
	'and', 'as', 'break', 'class', 'continue', 'def', 'elif', 'else',
	'except', 'for', 'from', 'if', 'import', 'in', 'is', 'not', 'or',
	'pass', 'raise', 'return', 'trait', 'try', 'while', 'yield',
}

def lexer():
	lg = rply.LexerGenerator()
	lg.add('ARROW', '->')
	lg.add('IADD', '\+=')
	lg.add('EQ', '==')
	lg.add('NE', '!=')
	lg.add('GE', '>=')
	lg.add('LE', '<=')
	lg.add('LBRA', '\[')
	lg.add('RBRA', '\]')
	lg.add('PLUS', '\+')
	lg.add('MINUS', '-')
	lg.add('MUL', '\*')
	lg.add('DIV', '/')
	lg.add('LACC', '{')
	lg.add('RACC', '}')
	lg.add('LT', '<')
	lg.add('GT', '>')
	lg.add('DOT', '\.')
	lg.add('AMP', '&')
	lg.add('DOLLAR', '\$')
	lg.add('PIPE', '\|')
	lg.add('CARET', '\^')
	lg.add('TILDE', '~')
	lg.add('MOD', '%')
	lg.add('LPAR', '\(')
	lg.add('RPAR', '\)')
	lg.add('ASGT', '=')
	lg.add('COMMA', ',')
	lg.add('COLON', ':')
	lg.add('QM', '\?')
	lg.add('STR', r"'(.*?)'")
	lg.add('STR', r'"(.*?)"')
	lg.add('BOOL', 'True|False')
	lg.add('NONE', 'None')
	lg.add('NAME', r'[a-zA-Z_][a-zA-Z0-9_]*')
	lg.add('NUM', r'[-+?[0-9]*\.?[0-9]+')
	lg.add('NL', r'\n')
	lg.add('COM', r'#(.*)')
	lg.add('TABS', r'\t+')
	lg.ignore(r' +')
	return lg.build()

LEXER = lexer()

def lex(src):
	'''Takes a string containing source code and returns a generator over
	tokens, represented by a three-element tuple:
	
	- Token type (from the list in lexer(), above)
	- The literal token contents
	- Position, as a tuple of line and column (both 1-based)
	
	This is mostly a wrapper around the rply lexer, but it reprocesses
	TABS tokens (which should only appear at the start of a line) into
	INDENT and DEDENT tokens, which only appear if the indentation
	level increases or decreases.
	
	Comment tokens do not appear in the output generator.'''
	level = 0
	hold = []
	for t in LEXER.lex(src):
		
		if t.name == 'COM':
			continue
		elif t.name == 'NL' and hold:
			hold = [t]
			continue
		elif t.name == 'NL' or (hold and t.name == 'TABS'):
			hold.append(t)
			continue
		
		if hold:
			yield hold[0]
			cur = len(hold[1].value) if len(hold) > 1 else 0
			pos = hold[1 if len(hold) > 1 else 0].source_pos
			for i in range(abs(cur - level)):
				type = 'INDENT' if cur > level else 'DEDENT'
				yield rply.Token(type, '', pos)
				level = cur
			hold = []
		
		if t.name == 'NAME' and t.value in NAME_LIKE:
			t.name = t.value.upper()
		
		yield t

	for t in hold:
		yield t

	while level > 0:
		yield rply.Token('DEDENT', '', t.source_pos)
		level -= 1

pg = rply.ParserGenerator([
		'AMP', 'AND', 'ARROW', 'AS', 'ASGT',
		'BOOL', 'BREAK',
		'CARET', 'CLASS', 'COLON', 'COMMA', 'CONTINUE',
		'DEDENT', 'DEF', 'DIV', 'DOLLAR', 'DOT',
		'ELIF', 'ELSE', 'EQ', 'EXCEPT',
		'FOR', 'FROM',
		'GE', 'GT',
		'IADD', 'IF', 'IMPORT', 'IN', 'INDENT', 'IS',
		'LBRA', 'LE', 'LPAR', 'LT',
		'MINUS', 'MUL', 'MOD',
		'NAME', 'NE', 'NL', 'NONE', 'NOT', 'NUM',
		'OR',
		'PASS', 'PIPE', 'PLUS',
		'QM',
		'RAISE', 'RBRA', 'RETURN', 'RPAR',
		'STR',
		'TILDE', 'TRAIT', 'TRY',
		'WHILE',
		'YIELD',
	], precedence=[
		('left', ['COMMA']),
		('left', ['IF']),
		('left', ['OR']),
		('left', ['AND']),
		('right', ['NOT']),
		('left', ['LT', 'LE', 'GT', 'GE', 'NE', 'EQ', 'IS']),
		('left', ['PIPE']),
		('left', ['CARET']),
		('left', ['AMP']),
		('left', ['PLUS', 'MINUS']),
		('left', ['MUL', 'DIV', 'MOD']),
		('left', ['AS']),
		('right', ['LBRA']),
		('left', ['DOT']),
	]
)

@pg.production('module : module-elems')
def module(s, p):
	res = ast.File()
	res.suite = p[0]
	return res

@pg.production('module : NL module-elems')
def module_after_line(s, p):
	res = ast.File()
	res.suite = p[1]
	return res

@pg.production('module-elems : module-elems module-elem')
def module_elems(s, p):
	p[0].append(p[1])
	return p[0]

@pg.production('module-elems : module-elem')
def module_elems_single(s, p):
	return [p[0]]

@pg.production('module-elem : function')
def function_module_elem(s, p):
	return p[0]

@pg.production('module-elem : function-decl')
def decl_module_elem(s, p):
	return p[0]

@pg.production('module-elem : class')
def class_module_elem(s, p):
	return p[0]

@pg.production('module-elem : asgt')
def asgt_module_elem(s, p):
	return p[0]

@pg.production('module-elem : trait')
def trait_module_elem(s, p):
	return p[0]

@pg.production('module-elem : FROM dotted IMPORT names NL')
def from_import(s, p):
	res = ast.RelImport(s.pos(p[0]))
	res.base = p[1]
	res.names = p[3]
	return res

@pg.production('dotted : var DOT NAME')
def dotted_attr(s, p):
	res = ast.Attrib(s.pos(p[1]))
	res.obj = p[0]
	res.attrib = p[2].value
	return res

@pg.production('dotted : var')
def dotted_var(s, p):
	return p[0]

@pg.production('names : names COMMA var')
def names(s, p):
	p[0].append(p[2])
	return p[0]

@pg.production('names : var')
def names_single(s, p):
	return [p[0]]

@pg.production('trait : TRAIT var type-params COLON NL INDENT function-decls DEDENT')
def trait(s, p):
	res = ast.Trait(s.pos(p[0]))
	res.decor = set()
	res.name = p[1]
	res.params = p[2]
	res.methods = p[6]
	return res

@pg.production('function-decls : function-decls function-decl')
def function_decls(s, p):
	p[0].append(p[1])
	return p[0]

@pg.production('function-decls : function-decl')
def function_decls_single(s, p):
	return [p[0]]

@pg.production('function-decl : DEF var formal-list rtype NL')
def function_decl(s, p):
	res = ast.Decl(s.pos(p[0]))
	res.decor = set()
	res.name = p[1]
	res.args = p[2]
	res.rtype = p[3]
	return res

@pg.production('class : CLASS var type-params COLON NL INDENT class-body DEDENT')
def cls(s, p):
	res = ast.Class(s.pos(p[0]))
	res.decor = set()
	res.name = p[1]
	res.params = p[2]
	res.attribs = p[6][0]
	res.methods = p[6][1]
	return res

@pg.production('type-params : LBRA type-params COMMA type-param RBRA')
def params(s, p):
	p[1].append(p[3])
	return p[1]

@pg.production('type-params : LBRA type-param RBRA')
def params_single(s, p):
	return [p[1]]

@pg.production('type-params : ')
def no_params(s, p):
	return []

@pg.production('type-param : type')
def param(s, p):
	return p[0]

@pg.production('class-body : attributes functions')
def complete_class_body(s, p):
	return p[0], p[1]

@pg.production('class-body : attributes')
def attrs_class_body(s, p):
	return p[0], []

@pg.production('class-body : functions')
def methods_class_body(s, p):
	return [], p[0]

@pg.production('class-body : PASS NL')
def empty_class_body(s, p):
	return [], []

@pg.production('functions : functions function')
def functions(s, p):
	p[0].append(p[1])
	return p[0]

@pg.production('functions : function')
def functions_single(s, p):
	return [p[0]]

@pg.production('attributes : attributes attr-decl')
def attributes(s, p):
	p[0].append(p[1])
	return p[0]

@pg.production('attributes : attr-decl')
def attributes_single(s, p):
	return [p[0]]

@pg.production('attr-decl : var COLON type NL')
def attr_decl(s, p):
	return p[2], p[0]

@pg.production('function : DEF var formal-list rtype COLON suite')
def function(s, p):
	res = ast.Function(s.pos(p[0]))
	res.decor = set()
	res.name = p[1]
	res.args = p[2]
	res.rtype = p[3]
	res.suite = p[5]
	return res

@pg.production('rtype : ')
def void_rtype(s, p):
	return

@pg.production('rtype : ARROW type')
def type_rtype(s, p):
	return p[1]

@pg.production('formal-list : LPAR RPAR')
def no_formals(s, p):
	return []

@pg.production('formal-list : LPAR formals RPAR')
def formals_list(s, p):
	return p[1]

@pg.production('formals : formals COMMA formal')
def formals(s, p):
	p[0].append(p[2])
	return p[0]

@pg.production('formals : formal')
def formals_single(s, p):
	return [p[0]]

@pg.production('formal : var')
def untyped_formal(s, p):
	res = ast.Argument(p[0].pos)
	res.name = p[0]
	return res

@pg.production('formal : var COLON type')
def typed_formal(s, p):
	res = ast.Argument(p[0].pos)
	res.name = p[0]
	res.type = p[2]
	return res

@pg.production('suite : NL INDENT statements DEDENT')
def suite(s, p):
	return p[2]

@pg.production('statements : statements stmt')
def statements(s, p):
	p[0].stmts.append(p[1])
	return p[0]

@pg.production('statements : stmt')
def statements_single(s, p):
	res = ast.Suite(p[0].pos)
	res.stmts = [p[0]]
	return res

@pg.production('stmt : TRY COLON suite EXCEPT var COLON suite')
def try_stmt(s, p):
	res = ast.TryBlock(s.pos(p[0]))
	res.suite = p[2]
	handler = ast.Except(s.pos(p[3]))
	handler.type = p[4]
	handler.suite = p[6]
	res.catch = [handler]
	return res

@pg.production('stmt : FOR lval IN expr-tuple COLON suite')
def for_stmt(s, p):
	res = ast.For(s.pos(p[0]))
	res.lvar = p[1]
	res.source = p[3]
	res.suite = p[5]
	return res

@pg.production('stmt : WHILE ternary COLON suite')
def while_stmt(s, p):
	res = ast.While(s.pos(p[0]))
	res.cond = p[1]
	res.suite = p[3]
	return res

@pg.production('stmt : if-suite')
def if_suite_stmt(s, p):
	return p[0]

@pg.production('if-suite : IF ternary COLON suite')
def simple_if_suite(s, p):
	res = ast.If(s.pos(p[0]))
	res.blocks = [(p[1], p[3])]
	return res

@pg.production('if-suite : IF ternary COLON suite ELSE COLON suite')
def if_else_suite(s, p):
	res = ast.If(s.pos(p[0]))
	res.blocks = [(p[1], p[3]), (None, p[6])]
	return res

@pg.production('if-suite : IF ternary COLON suite elifs')
def if_with_elifs(s, p):
	res = ast.If(s.pos(p[0]))
	res.blocks = [(p[1], p[3])] + p[4]
	return res

@pg.production('if-suite : IF ternary COLON suite elifs ELSE COLON suite')
def if_with_elifs_and_else(s, p):
	res = ast.If(s.pos(p[0]))
	res.blocks = [(p[1], p[3])] + p[4] + [(None, p[7])]
	return res

@pg.production('elifs : elifs elif')
def elifs(s, p):
	p[0].append(p[1])
	return p[0]

@pg.production('elifs : elif')
def elifs_single(s, p):
	return [p[0]]

@pg.production('elif : ELIF ternary COLON suite')
def elif_(s, p):
	return p[1], p[3]

@pg.production('stmt : asgt')
def asgt_stmt(s, p):
	return p[0]

@pg.production('asgt : lval ASGT expr-tuple NL')
def asgt(s, p):
	return binop(s, ast.Assign, p)

@pg.production('stmt : aug-asgt')
def aug_asgt_stmt(s, p):
	return p[0]

@pg.production('aug-asgt : lval IADD expr-tuple NL')
def iadd(s, p):
	return binop(s, ast.IAdd, p)

@pg.production('stmt : yield')
def yield_stmt(s, p):
	return p[0]

@pg.production('yield : YIELD expr-tuple NL')
def value_yield(s, p):
	res = ast.Yield(s.pos(p[0]))
	res.value = p[1]
	return res

@pg.production('stmt : return')
def return_stmt(s, p):
	return p[0]

@pg.production('return : RETURN expr-tuple NL')
def value_return(s, p):
	res = ast.Return(s.pos(p[0]))
	res.value = p[1]
	return res

@pg.production('return : RETURN NL')
def void_return(s, p):
	res = ast.Return(s.pos(p[0]))
	res.value = None
	return res

@pg.production('stmt : RAISE ternary NL')
def raise_(s, p):
	res = ast.Raise(s.pos(p[0]))
	res.value = p[1]
	return res

@pg.production('stmt : BREAK NL')
def break_(s, p):
	return ast.Break(s.pos(p[0]))

@pg.production('stmt : CONTINUE NL')
def continue_(s, p):
	return ast.Continue(s.pos(p[0]))

@pg.production('stmt : PASS NL')
def pass_(s, p):
	return ast.Pass(s.pos(p[0]))

@pg.production('stmt : expr NL')
def expr_stmt(s, p):
	return p[0]

@pg.production('type : LPAR type-tuple RPAR')
def tuple_type(s, p):
	return p[1]

@pg.production('type-tuple : type-tuple COMMA type')
def type_tuple(s, p):
	p[0].append(p[2])
	return p[0]

@pg.production('type-tuple : type COMMA type')
def two_type_tuple(s, p):
	res = ast.Tuple(s.pos(p[1]))
	res.values = [p[0], p[2]]
	return res

@pg.production('type : QM type')
def opt_type(s, p):
	res = ast.Opt(s.pos(p[0]))
	res.value = p[1]
	return res

@pg.production('type : ptr-type')
def ptr_type_type(s, p):
	return p[0]

@pg.production('type : TILDE ptr-type')
def mut_type(s, p):
	res = ast.Mut(s.pos(p[0]))
	res.value = p[1]
	return res

@pg.production('ptr-type : DOLLAR vtype')
def owner_type(s, p):
	res = ast.Owner(s.pos(p[0]))
	res.value = p[1]
	return res

@pg.production('ptr-type : AMP vtype')
def ref_type(s, p):
	res = ast.Ref(s.pos(p[0]))
	res.value = p[1]
	return res

@pg.production('type : vtype')
def vtype_type(s, p):
	return p[0]

@pg.production('vtype : var LBRA type RBRA', precedence='LBRA')
def param_type(s, p):
	res = ast.Elem(s.pos(p[1])) # XXX CHANGE TO p[0]?
	res.obj = p[0]
	res.key = p[2]
	return res

@pg.production('vtype : var')
def name_type(s, p):
	return p[0]

@pg.production('expr-tuple : ternary COMMA ternary')
def expr_tuple_multi(s, p):
	res = ast.Tuple(s.pos(p[1]))
	res.values = [p[0], p[2]]
	return res

@pg.production('expr-tuple : ternary')
def expr_tuple_base(s, p):
	return p[0]

@pg.production('ternary : expr IF expr ELSE expr')
def actual_ternary(s, p):
	res = ast.Ternary(s.pos(p[1]))
	res.cond = p[2]
	res.values = [p[0], p[4]]
	return res

@pg.production('ternary : expr')
def ternary_expr(s, p):
	return p[0]

@pg.production('expr : expr LBRA expr RBRA')
def elem(s, p):
	res = ast.Elem(s.pos(p[1]))
	res.obj = p[0]
	res.key = p[2]
	return res

@pg.production('expr : LPAR ternary RPAR')
def parenthesized(s, p):
	return p[1]

@pg.production('expr : expr LPAR actuals RPAR')
def call(s, p):
	res = ast.Call(s.pos(p[1]))
	res.name = p[0]
	res.callbr = None
	res.fun = None
	res.virtual = None
	res.args = p[2]
	return res

@pg.production('actuals : actuals COMMA actual')
def actuals(s, p):
	p[0].append(p[2])
	return p[0]

@pg.production('actuals : actual')
def actuals_single(s, p):
	return [p[0]]

@pg.production('actuals : ')
def actuals_empty(s, p):
	return []

@pg.production('actual : var ASGT ternary')
def named_actual(s, p):
	res = ast.NamedArg(p[0].pos)
	res.name = p[0].name
	res.val = p[2]
	return res

@pg.production('actual : ternary')
def expr_actual(s, p):
	return p[0]

def binop(s, cls, p):
	res = cls(s.pos(p[1]))
	res.left = p[0]
	res.right = p[2]
	return res

@pg.production('expr : expr AND expr')
def and_(s, p):
	return binop(s, ast.And, p)

@pg.production('expr : expr OR expr')
def or_(s, p):
	return binop(s, ast.Or, p)

@pg.production('expr : NOT expr')
def not_(s, p):
	res = ast.Not(s.pos(p[0]))
	res.value = p[1]
	return res

@pg.production('expr : expr AMP expr')
def bwand(s, p):
	return binop(s, ast.BWAnd, p)

@pg.production('expr : expr PIPE expr')
def bwor(s, p):
	return binop(s, ast.BWOr, p)

@pg.production('expr : expr CARET expr')
def bwxor(s, p):
	return binop(s, ast.BWXor, p)

@pg.production('expr : expr IS expr')
def is_(s, p):
	return binop(s, ast.Is, p)

@pg.production('expr : expr EQ expr')
def eq(s, p):
	return binop(s, ast.EQ, p)

@pg.production('expr : expr NE expr')
def ne(s, p):
	return binop(s, ast.NE, p)

@pg.production('expr : expr LT expr')
def lt(s, p):
	return binop(s, ast.LT, p)

@pg.production('expr : expr GT expr')
def gt(s, p):
	return binop(s, ast.GT, p)

@pg.production('expr : expr LE expr')
def le(s, p):
	return binop(s, ast.LE, p)

@pg.production('expr : expr GE expr')
def ge(s, p):
	return binop(s, ast.ge, p)

@pg.production('expr : expr MOD expr')
def mod(s, p):
	return binop(s, ast.Mod, p)

@pg.production('expr : expr MUL expr')
def mul(s, p):
	return binop(s, ast.Mul, p)

@pg.production('expr : expr DIV expr')
def div(s, p):
	return binop(s, ast.Div, p)

@pg.production('expr : expr PLUS expr')
def plus(s, p):
	return binop(s, ast.Add, p)

@pg.production('expr : expr MINUS expr')
def minus(s, p):
	return binop(s, ast.Sub, p)

@pg.production('expr : expr AS type')
def as_(s, p):
	return binop(s, ast.As, p)

@pg.production('expr : expr DOT NAME')
def attr_expr(s, p):
	res = ast.Attrib(s.pos(p[1]))
	res.obj = p[0]
	res.attrib = p[2].value
	return res

@pg.production('expr : var')
def var_expr(s, p):
	return p[0]

@pg.production('lval : lval COMMA lval')
def lval_tuple(s, p):
	res = ast.Tuple(s.pos(p[1]))
	res.values = [p[0], p[2]]
	return res

@pg.production('lval : var')
def var_lval(s, p):
	return p[0]

@pg.production('lval : expr DOT NAME')
def attr_lval(s, p):
	res = ast.Attrib(s.pos(p[1]))
	res.obj = p[0]
	res.attrib = p[2].value
	return res

@pg.production('var : NAME')
def var(s, p):
	return ast.Name(p[0].value, s.pos(p[0]))

@pg.production('expr : STR')
def string(s, p):
	return ast.String(p[0].value[1:-1], s.pos(p[0]))

@pg.production('expr : NUM')
def number(s, p):
	if '.' in p[0].value:
		return ast.Float(p[0].value, s.pos(p[0]))
	else:
		return ast.Int(p[0].value, s.pos(p[0]))

@pg.production('expr : BOOL')
def bool_(s, p):
	return ast.Bool(p[0].value, s.pos(p[0]))

@pg.production('expr : NONE')
def none(s, p):
	return ast.NoneVal(s.pos(p[0]))

@pg.error
def error(s, t):
	raise util.ParseError(s.fn, t, s.pos(t))

parser = pg.build()

class State(object):

	def __init__(self, fn):
		self.fn = fn
		with open(fn) as f:
			self.src = f.read()
		self.lines = self.src.splitlines()
	
	def pos(self, t):
		'''Reprocess location information (see parse() for more details).'''
		ln = t.source_pos.lineno - 1
		if t.value and t.value[0] == '\n':
			ln -= 1

		col = t.source_pos.colno - 1
		line = self.lines[ln] if ln < len(self.lines) else ''
		return (ln, col), (ln, col + len(t.value)), line, self.fn

def parse(fn):
	'''Takes a file name and returns the AST corresponding to the source
	contained in the file. The State thing is here mostly to reprocess
	location information from rply into something easier to use. AST nodes
	get a pos field containing a 4-element tuple:
	
	- Tuple of start location, as 0-based line and column numbers
	- Tuple of end location, as 0-based line and column numbers
	- The full line
	- The file name
	
	This should be everything we need to build good error messages.'''
	state = State(fn)
	return parser.parse(lex(state.src), state=state)
