IGNORE = {'pos'}

class AttribRepr(object):
	def __repr__(self):
		contents = sorted(self.__dict__.iteritems())
		show = ('%s=%r' % (k, v) for (k, v) in contents if k not in IGNORE)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

class Error(Exception):
	
	def __init__(self, node, msg):
		self.node = node
		self.msg = msg
	
	def show(self, fn):
		
		if getattr(self.node, 'pos', None) is None:
			return '%s: %s\n' % (fn, self.msg)
		
		pos = self.node.pos
		col = len(pos[2][:pos[0][1]].replace('\t', ' ' * 4)) + 1
		a = '%s [%s.%s]: %s' % (fn, pos[0][0] + 1, col, self.msg)
		b = pos[2].replace('\t', ' ' * 4).rstrip()
		c = ' ' * (pos[0][1] + 3 * pos[2].count('\t')) + '^'
		return '\n'.join((a, b, c)) + '\n'
