import sys, re, itertools

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
	pos, line, base = 0, 0, 0
	hold, level = None, 0
	for m, t in itertools.cycle(REGEX):
		
		if pos == len(src):
			lend = hold[2][0], hold[2][1] + 1
			yield 'nl', hold[0], hold[2], lend
			ipos = (hold[2][0] + 1, 0), (hold[2][0] + 1, hold[1])
			for i in range(level):
				yield 'indent', -1, ipos[0], ipos[1]
			return
		
		m = m.match(src, pos)
		if not m: continue
		start = line, pos - base
		#print 'MATCHED', line, pos - base, repr(m.group())
		pos = m.end()
		end = line, pos - base
		
		val = m.group()
		if m.groups():
			val = m.groups()[0]
		
		if t == 'nl':
			line, base = line + 1, pos
			sp = SPACES.match(src, pos).group()
			pos += len(sp)
			hold = val, len(sp), start, pos - base
			continue
		elif hold:
			lend = hold[2][0], hold[2][1] + 1
			yield 'nl', hold[0], hold[2], lend
			ipos = (hold[2][0] + 1, 0), (hold[2][0] + 1, hold[1])
			if hold[1] > level:
				yield 'indent', 1, ipos[0], ipos[1]
				level = hold[1]
			elif hold[1] < level:
				yield 'indent', -1, ipos[0], ipos[1]
				level = hold[1]
			hold = None
		
		if t[0] == '!':
			continue
		elif t == 'name' and val in OPERATORS:
			t = 'op'
		elif t == 'name' and val in KEYWORDS:
			t = 'kw'
		
		yield t, val, start, end

def show(src):
	for x in tokenize(src):
		print x

if __name__ == '__main__':
	show(open(sys.argv[1]).read())
