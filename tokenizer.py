import sys, re, itertools

KEYWORDS = {'def', 'return', 'if', 'else', 'elif', 'for', 'while'}
OPERATORS = {'not', 'and', 'or', 'in'}
SPACES = re.compile('[ \t]*')

MATCHERS = [
	(r'\n', 'nl'),
	(r'#(.*)', 'com'),
	(r' ', '!sp'),
	(r'->|==|!=|[,\[\]:()+=*\-/{}<]', 'op'),
	(r'[a-zA-Z_][a-zA-Z0-9_]*', 'name'),
	(r'[0-9\-.]+', 'num'),
	(r"'(.*?)'", 'str'),
	(r'"(.*?)"', 'str'),
]

REGEX = [(re.compile(e), t) for (e, t) in MATCHERS]

def tokenize(f):
	indent, level, prev = None, 0, None
	for line, src in enumerate(f):
		
		sp = SPACES.match(src).group()
		pos = len(sp)
		if prev is not None:
			indent = len(sp)
		
		for m, t in itertools.cycle(REGEX):
			
			m = m.match(src, pos)
			if not m: continue
			if t == 'nl': break
			
			start = line, pos
			pos = m.end()
			end = line, pos
			
			val = m.group()
			if m.groups():
				val = m.groups()[0]
			
			if indent is not None and indent != level:
				yield 'nl', '\n', (line - 1, prev - 1), (line - 1, prev)
				yield 'indent', cmp(indent, level), (line, 0), (line, indent)
				level, indent = indent, None
			elif indent is not None:
				yield 'nl', '\n', (line - 1, prev - 1), (line - 1, prev)
				indent = None
			
			if t[0] == '!':
				continue
			elif t == 'name' and val in OPERATORS:
				t = 'op'
			elif t == 'name' and val in KEYWORDS:
				t = 'kw'
			
			yield t, val, start, end
		
		prev = len(src)
	
	yield 'nl', '\n', (line, pos), (line, pos + 1)
	for i in range(level):
		yield 'indent', -1, (line + 1, 0), (line + 1, 0)
