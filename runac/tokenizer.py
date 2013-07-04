import re, itertools

KEYWORDS = {
	'class', 'def', 'elif', 'else', 'except', 'for', 'from', 'if', 'import',
	'return', 'while', 'pass', 'raise', 'trait', 'try', 'yield',
}
OPERATORS = {'not', 'and', 'or', 'in', 'as'}
SPACES = re.compile('\t*')

MATCHERS = [
	(r'\n', 'nl'),
	(r'#(.*)', 'com'),
	(r' ', '!sp'),
	(r'->|==|!=|>=|<=|[,\[\]:()+=*\-/{}<>.&$|^]', 'op'),
	(r'[a-zA-Z_][a-zA-Z0-9_]*', 'name'),
	(r'@[a-zA-Z_][a-zA-Z0-9_]*', 'deco'),
	(r'[-+]?[0-9]*\.?[0-9]+', 'num'),
	(r"'(.*?)'", 'str'),
	(r'"(.*?)"', 'str'),
]

REGEX = [(re.compile(e), t) for (e, t) in MATCHERS]

def tokenize(f):
	level = 0
	for line, src in enumerate(f):
		
		sp = SPACES.match(src).group()
		pos = len(sp)
		
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
			
			indent = len(sp) - level
			if indent:
				dir = cmp(indent, 0)
				for i in range(0, indent, dir):
					yield 'indent', dir, (line, 0), (line, len(sp)), src
				level = len(sp)
			
			if t[0] == '!':
				continue
			elif t == 'name' and val in OPERATORS:
				t = 'op'
			elif t == 'name' and val in KEYWORDS:
				t = 'kw'
			
			yield t, val, start, end, src
		
		yield 'nl', '\n', (line, pos), (line, pos + 1), src
	
	for i in range(level):
		yield 'indent', -1, (line + 1, 0), (line + 1, 0), ''
