import sys, re

def indent(s):
	yield 'nl', '\n'
	yield 'indent', len(s)

MATCHING = {
	None: [
		(r'\n', 'nl', 'indent', indent),
		(r' ', '!sp', None, None),
		(r'->|[,\[\]:()+=*\-/]', 'op', None, None),
		(r'[a-zA-Z_][a-zA-Z0-9_]*', 'name', None, None),
		(r'[0-9\-.]+', 'num', None, None),
		(r"'(.*?)'", 'str', None, None),
	],
	'indent': [
		(r'[ \t]', 'indent', None, None),
		(r'', 'end', None, None),
	],
}

REGEX = {}
for k, v in MATCHING.iteritems():
	REGEX[k] = [(re.compile(e), t, g, r) for (e, t, g, r) in v]

def tokenize(src):
	pos = 0
	grammar = [None]
	buffer = []
	while True:
		for m, t, g, r in REGEX[grammar[-1]]:
			
			m = m.match(src, pos)
			if not m: continue
			pos = m.end()
			# print 'MATCHED', repr(m.group())
			
			val = m.group()
			if m.groups():
				val = m.groups()[0]
			
			if g:
				grammar.append(g)
				buffer.append((r, []))
				break
			
			if t[0] == '!':
				break
			elif t == 'end' and not buffer:
				return
			elif t == 'end' and buffer:
				grammar.pop()
				buf = buffer.pop()
				res = list(buf[0](buf[1]))
			else:
				res = [(t, val)]
			
			if buffer:
				# print 'BUFFER', res
				buffer[-1][1].append(res)
				break
			
			for x in res:
				yield x
			
			break
		
		else:
			return

def indented(gen):
	level, future, hold = 0, None, []
	for t, v in gen:
		if t == 'nl':
			future = None
			hold = [(t, v)]
			continue
		elif t != 'indent':
			if future is not None:
				level, future = future, None
			for x in hold:
				yield x
			hold = []
			yield t, v
		elif v > level:
			future = v
			hold.append(('indent', 1))
		elif v < level:
			future = v
			hold.append(('indent', -1))
		elif v == level:
			continue
	for x in hold:
		yield x

def show(src):
	for x in indented(tokenize(src)):
		print x

if __name__ == '__main__':
	show(open(sys.argv[1]).read())
