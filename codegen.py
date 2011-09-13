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
		'lib': {
			'write': '@"\\01_write"', 
		},
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
			if isinstance(attr, list):
				for v in attr:
					self.visit(v)
			else:
				self.visit(attr)

class CodeGen(object):
	
	def __init__(self):
		pass
	
	def visit(self, node):
		
		if hasattr(self, node.__class__.__name__):
			getattr(self, node.__class__.__name__)(node)
			return
		
		for k in node.fields:
			attr = getattr(node, k)
			if isinstance(attr, list):
				for v in attr:
					self.visit(v)
			else:
				self.visit(attr)
	
	def Call(self, node):
		x = 'call void @' + node.name + '('
		x += '%struct.str* ' + self.const.table[node.args] + ')'
		self.lines.append(x)
	
	def Suite(self, node):
		for stmt in node.stmts:
			self.visit(stmt)
	
	def Module(self, node):
		
		self.const = ConstantFinder(node)
		defined = {i.name: i for i in node.values}
		main = defined['__main__']
		
		self.lines = self.const.lines + ['']
		self.lines.append(' '.join(['define i32 @main(i32 %argc,',
									'i8** %argv) nounwind ssp {']))
		self.visit(main.code)
		self.lines.append('ret i32 0')
		self.lines.append('}')
		
		return self.lines

def layout(data):
	bits = []
	for decl in data:
		bits.append(':'.join(str(i) for i in decl))
	return '-'.join(bits)

def prologue(mod):
	lines = ["; ModuleID = 'test'"]
	meta = META[sys.platform]
	lines.append('target datalayout = "%s"' % layout(meta['layout']))
	lines.append('target triple = "%s"' % meta['triple'])
	return lines

def stdlib():
	return open('std.ll').read().splitlines() + ['']

def source(mod):
	lines = prologue(mod) + ['']
	lines += stdlib()
	lines += CodeGen().Module(mod) + ['']
	return '\n'.join(lines)

if __name__ == '__main__':
	src = open(sys.argv[1]).read()
	tokens = tokenizer.indented(tokenizer.tokenize(src))
	mod = ast.Module.parse(parser.Buffer(tokens))
	print source(mod)
