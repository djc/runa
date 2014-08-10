IGNORE = {'pos'}

class AttribRepr(object):
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%r' % (k, v) for (k, v) in contents if k not in IGNORE)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

def error(fn, msg, pos):
	
	if pos is None:
		return '%s: %s\n' % (fn, msg)
	
	col = len(pos[2][:pos[0][1]].replace('\t', ' ' * 4)) + 1
	desc = '%s [%s.%s]: %s' % (fn, pos[0][0] + 1, col, msg)
	if not pos[2]:
		return desc + '\n'
	
	line = pos[2].replace('\t', ' ' * 4).rstrip()
	spaces = pos[0][1] + 3 * min(pos[0][1], pos[2].count('\t'))
	return '\n'.join((desc, line, ' ' * spaces + '^')) + '\n'

class Error(Exception):
	
	def __init__(self, node, msg):
		Exception.__init__(self, msg)
		self.node = node
		self.msg = msg
	
	def show(self, fn):
		return error(fn, self.msg, getattr(self.node, 'pos', None))

class ParseError(Exception):
	
	def __init__(self, fn, t, pos):
		self.fn = fn
		self.t = t
		self.pos = pos
	
	def show(self, fn):
		msg = 'unexpected token %s (%r)' % (self.t.name, self.t.value)
		return error(fn, msg, self.pos)
