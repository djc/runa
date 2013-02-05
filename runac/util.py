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
		
		if self.node.pos is None:
			return '%s: %s\n' % (fn, self.msg)
		
		pos = self.node.pos
		a = '%s [%s.%s]: %s' % (fn, pos[0][0] + 1, pos[0][1] + 1, self.msg)
		b = pos[2].replace('\t', ' ' * 4).rstrip()
		mv = -1 if '\t' in pos[2] else 0
		c = ' ' * (mv + pos[0][1] + 4 * pos[2].count('\t')) + '^'
		return '\n'.join((a, b, c)) + '\n'
