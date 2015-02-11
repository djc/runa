import os, sys

BASE = os.path.dirname(os.path.dirname(__file__))
CORE_DIR = os.path.join(BASE, 'core')
IGNORE = {'pos'}

if sys.version_info[0] < 3:
	def keys(d):
		return d.iterkeys()
	def values(d):
		return d.itervalues()
	def items(d):
		return d.iteritems()
else:
	def keys(d):
		return d.keys()
	def values(d):
		return d.values()
	def items(d):
		return d.items()

class AttribRepr(object):
	'''Helper class to provide a nice __repr__ for other classes'''
	def __repr__(self):
		contents = sorted(items(self.__dict__))
		show = ('%s=%r' % (k, v) for (k, v) in contents if k not in IGNORE)
		return '<%s(%s)>' % (self.__class__.__name__, ', '.join(show))

def error(fn, msg, pos):
	'''Helper function to print useful error messages.
	
	Tries to mangle location information and message into a layout that's
	easy to read and provides good data about the underlying error message.
	
	This is in a separate function because of the differences between Error
	and ParseError, which both need this functionality.'''
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
	'''Error class used for throwing user errors from the compiler'''
	
	def __init__(self, node, msg):
		Exception.__init__(self, msg)
		self.node = node
		self.msg = msg
	
	def show(self):
		fn = os.path.basename(self.node.pos[3])
		return error(fn, self.msg, getattr(self.node, 'pos', None))

class ParseError(Exception):
	'''Parse errors, raised from rply's error handling function'''
	
	def __init__(self, fn, t, pos):
		self.fn = fn
		self.t = t
		self.pos = pos
	
	def show(self):
		fn = os.path.basename(self.pos[3])
		msg = 'unexpected token %s (%r)' % (self.t.name, self.t.value)
		return error(fn, msg, self.pos)
