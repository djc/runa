import sys, re

KEYWORDS = {'def', 'return', 'if', 'else', 'elif', 'for', 'while'}
OPERATORS = {'not', 'and', 'or', 'in'}
SPACES = re.compile('[ \t]*')

MATCHERS = [
	(r'\n', 'nl'),
	(r' ', '!sp'),
	(r'->|==|!=|[,\[\]:()+=*\-/#{}<]', 'op'),
	(r'[a-zA-Z_][a-zA-Z0-9_]*', 'name'),
	(r'[0-9\-.]+', 'num'),
	(r"'(.*?)'", 'str'),
	(r'"(.*?)"', 'str'),
]

REGEX = [(re.compile(e), t) for (e, t) in MATCHERS]

def tokenize(src):
	pos, line = 0, 0
	while True:
		for m, t in REGEX:
			
			if pos == len(src):
				return
			
			m = m.match(src, pos)
			if not m: continue
			#print 'MATCHED', line, pos - base, repr(m.group())
			pos = m.end()
			
			val = m.group()
			if m.groups():
				val = m.groups()[0]
			
			if t == 'nl':
				line = line + 1
				yield t, val, line
				sp = SPACES.match(src, pos).group()
				yield 'indent', len(sp), line
				pos += len(sp)
				continue
			
			if t[0] == '!':
				continue
			elif t == 'name' and val in OPERATORS:
				t = 'op'
			elif t == 'name' and val in KEYWORDS:
				t = 'kw'
			
			yield t, val, line

def indented(gen):
	level, future, hold = 0, None, []
	for t, v, ln in gen:
		if t == 'nl':
			future = None
			hold = [(t, v, ln)]
			continue
		elif t != 'indent':
			if future is not None:
				level, future = future, None
			for x in hold:
				yield x
			hold = []
			yield t, v, ln
		elif v > level:
			future = v
			hold.append(('indent', 1, ln))
		elif v < level:
			future = v
			hold += [('indent', -1, ln)] * (level - v)
		elif v == level:
			continue
	for x in hold:
		yield x

def show(src):
	for x in indented(tokenize(src)):
		print x

if __name__ == '__main__':
	show(open(sys.argv[1]).read())
