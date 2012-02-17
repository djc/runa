import sys, ast, tokenizer, parser

TRIPLES = {
	'darwin': 'x86_64-apple-darwin11.0.0',
	'linux2': 'x86_64-pc-linux-gnu',
}

TYPES = {
	'void': 'void',
	'int': 'i64',
	'str': '%struct.str*',
}

LIBRARY = {
	'print': ('void', 'str'),
	'str': ('str', 'int'),
}

class ConstantFinder(object):
	
	def __init__(self, node):
		self.data = {}
		self.table = {}
		self.next = 0
		self.lines = []
		self.visit(node)
	
	def id(self, type):
		s = '@%s%s' % (type, self.next)
		self.next += 1
		return s
	
	def String(self, node):
		
		id = self.id('str')
		self.data[id] = node
		self.table[node] = id
		l = len(node.value)
		type = '[%i x i8]' % l
		
		bits = [id + '_data', '=', 'constant']
		bits += ['%s c"%s"' % (type, node.value)]
		self.lines.append(' '.join(bits))
		
		data = type, id
		bits = [id, '=', 'constant', TYPES['str'][:-1]]
		bits.append('{ i64 %s,' % l)
		bits.append('i8* getelementptr(%s* %s_data, i32 0, i32 0)}' % data)
		self.lines.append(' '.join(bits))
	
	def Number(self, node):
		id = self.id('num')
		self.data[id] = node
		self.table[node] = id
		bits = id, TYPES['int'], node.val
		self.lines.append('%s = constant %s %s' % bits)
		
	def visit(self, node):
		
		if hasattr(self, node.__class__.__name__):
			getattr(self, node.__class__.__name__)(node)
			return
		
		for k in node.fields:
			attr = getattr(node, k)
			if isinstance(attr, list) or isinstance(attr, tuple):
				for v in attr:
					self.visit(v)
			else:
				self.visit(attr)

class CodeGen(object):
	
	def __init__(self):
		self.buf = []
		self.level = 0
		self.start = True
		self.var = 1
	
	def varname(self):
		self.var += 1
		return '%%%i' % (self.var - 1)
	
	def visit(self, node):
		
		if hasattr(self, node.__class__.__name__):
			return getattr(self, node.__class__.__name__)(node)
		
		for k in node.fields:
			attr = getattr(node, k)
			if isinstance(attr, list):
				for v in attr:
					self.visit(v)
			else:
				self.visit(attr)
	
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
	
	def String(self, node):
		return TYPES['str'], self.const.table[node]
	
	def Number(self, node):
		bits = self.varname(), TYPES['int'], self.const.table[node]
		self.writeline('%s = load %s* %s' % bits)
		return TYPES['int'], bits[0]
	
	def Call(self, node):
		
		args = []
		for arg in node.args:
			args.append('%s %s' % self.visit(arg))
		
		store, start = None, 'call'
		void = LIBRARY[node.name.name][0] == 'void'
		if not void:
			store = self.varname()
			start = '%s = call' % store
		
		rtype = TYPES[LIBRARY[node.name.name][0]]
		call = '@' + node.name.name + '(' + ', '.join(args) + ')'
		self.writeline(' '.join((start, rtype, call)))
		return rtype, store
	
	def Suite(self, node):
		for stmt in node.stmts:
			self.visit(stmt)
	
	def Module(self, node):
		
		self.const = ConstantFinder(node)
		defined = {i.name: i for i in node.values}
		self.writelines(self.const.lines)
		self.newline()
		self.newline()
		
		if '__main__' in defined:
			decl = 'define i32 @main(i32 %argc, i8** %argv) nounwind ssp {'
			self.writeline(decl)
			self.indent()
			self.visit(defined['__main__'].code)
			self.writeline('ret i32 0')
			self.dedent()
			self.writeline('}')
		
		return ''.join(self.buf).split('\n')

def layout(data):
	bits = []
	for decl in data:
		bits.append(':'.join(str(i) for i in decl))
	return '-'.join(bits)

def prologue(mod):
	return ['target triple = "%s"' % TRIPLES[sys.platform]]

def stdlib():
	return open('std.ll').read().splitlines() + ['']

def source(mod):
	lines = prologue(mod) + ['']
	lines += stdlib()
	lines += CodeGen().Module(mod)
	return '\n'.join(lines)

if __name__ == '__main__':
	print source(parser.fromfile(sys.argv[1]))
