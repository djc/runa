import sys, ast, tokenizer, parser

META = {
	'darwin': {
		'triple': 'x86_64-apple-darwin11.0.0',
		'layout': [
			('e',),
			('p', 64, 64, 64),
			('i1', 8, 8),
			('i8', 8, 8),
			('i16', 16, 16),
			('i32', 32, 32),
			('i64', 64, 64),
			('f32', 32, 32),
			('f64', 64, 64),
			('v64', 64, 64),
			('v128', 128, 128),
			('a0', 0, 64),
			('s0', 64, 64),
			('f80', 128, 128),
			('n8', 16, 32, 64),
		],
	},
	'linux2': {
		'triple': 'x86_64-pc-linux-gnu',
		'layout': [
			('e',),
			('p', 64, 64, 64),
			('i1', 8, 8),
			('i8', 8, 8),
			('i16', 16, 16),
			('i32', 32, 32),
			('i64', 64, 64),
			('f32', 32, 32),
			('f64', 64, 64),
			('v64', 64, 64),
			('v128', 128, 128),
			('a0', 0, 64),
			('s0', 64, 64),
			('f80', 128, 128),
			('n8', 16, 32, 64),
			('S128',)
		],
	}
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
		bits = [id, '=', 'internal', 'constant', '%struct.str']
		bits.append('{ i64 %s,' % l)
		bits.append('i8* getelementptr(%s* %s_data, i32 0, i32 0)' % data)
		bits.append('}, align 8')
		self.lines.append(' '.join(bits))
	
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
	
	def Call(self, node):
		x = 'call void @' + node.name.name + '('
		x += '%struct.str* ' + self.const.table[node.args[0]] + ')'
		self.writeline(x)
	
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
	meta = META[sys.platform]
	return ['target triple = "%s"' % meta['triple']]

def stdlib():
	return open('std.ll').read().splitlines() + ['']

def source(mod):
	lines = prologue(mod) + ['']
	lines += stdlib()
	lines += CodeGen().Module(mod) + ['']
	return '\n'.join(lines)

if __name__ == '__main__':
	print source(parser.fromfile(sys.argv[1]))
