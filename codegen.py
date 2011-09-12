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

BUILTIN = {'print'}

TYPES = {
	'struct.str': '{ i64, i8* }',
}

def transform(call, consts):
	meta = META[sys.platform]
	if call.name == 'print':
		lines = [
			'%lenptr = getelementptr %struct.str* @str0, i32 0, i32 0',
			'%len = load i64* %lenptr',
			'%dataptr = getelementptr %struct.str* @str0, i32 0, i32 1',
			'%data = load i8** %dataptr',
			'call i64 ' + meta['lib']['write'] + '(i32 1, i8* %data, i64 %len)', 
			'ret i32 0',
		]
		return '\t' + '\n\t'.join(lines)

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
		if node.name in BUILTIN:
			self.lines.append(transform(node, self.const))
	
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

def externals():
	lines = []
	meta = META[sys.platform]
	for name, alias in sorted(meta['lib'].iteritems()):
		lines.append('declare i64 %s(i32, i8*, i64)' % alias)
	return lines

def types():
	lines = []
	for k, v in sorted(TYPES.iteritems()):
		lines.append('%%%s = type %s' % (k, v))
	return lines

def source(mod):
	lines = prologue(mod) + ['']
	lines += types() + ['']
	lines += CodeGen().Module(mod) + ['']
	lines += externals()
	return '\n'.join(lines)

if __name__ == '__main__':
	src = open(sys.argv[1]).read()
	tokens = tokenizer.indented(tokenizer.tokenize(src))
	mod = ast.Module.parse(parser.Buffer(tokens))
	print source(mod)
