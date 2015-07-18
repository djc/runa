import ast, _ast, sys, collections
sys.path.append('..')
from runac import parser

TITLE = 'Language grammar'
PARSER_FILE = '../runac/parser.py'

INTRO = '''The table below (which is generated from the parser's source code)
can serve as a guide to Runa's grammar.
Code literals in rules represent regular expressions.
The special INDENT and DEDENT tokens are inserted by a secondary pass,
after the initial tokenization of source code;
they represent the increase and decrease of the indentation level.'''

def get_rules():
	
	with open(PARSER_FILE) as f:
		src = f.read()
	
	rules = collections.OrderedDict()
	for node in ast.parse(src).body:
		
		if not isinstance(node, _ast.FunctionDef):
			continue
		
		if not node.decorator_list:
			continue
		
		assert len(node.decorator_list) == 1
		decorator = node.decorator_list[0]
		if not isinstance(decorator, _ast.Call):
			continue
		
		func = decorator.func
		if not isinstance(func, _ast.Attribute):
			continue
		
		assert func.attr == 'production'
		ln = decorator.args[0].s
		name, match = ln.split(' : ', 1)
		rules.setdefault(name, []).append(tuple(match.split()))
	
	return rules

def get_tokens():
	
	tokens = {'INDENT': 'INDENT', 'DEDENT': 'DEDENT'}
	for rule in parser.LEXER.rules:
		name, pattern = rule.name, rule.re.pattern
		tokens[rule.name] = rule.re.pattern
	
	for word in parser.NAME_LIKE:
		tokens[word.upper()] = word
	
	return tokens

def main():
	
	rules, tokens = get_rules(), get_tokens()
	lines, columns = [], [0, 0]
	for name, expands in rules.iteritems():
		columns[0] = max(columns[0], len(name))
		for i, expand in enumerate(expands):
			
			bits = list(expand)
			for idx, s in enumerate(expand):
				if s.upper() == s:
					bits[idx] = '``' + tokens[s] + '``'
			
			defn = ' '.join(bits)
			columns[1] = max(columns[1], len(defn))
			lines.append((name if not i else '', defn))
	
	separator = ''.join((
		'+',
		'-' * (columns[0] + 2),
		'+',
		'-' * (columns[1] + 2),
		'+',
	))
	fmt = '| %%-%is | %%-%is |' % tuple(columns)
	
	print '*' * len(TITLE)
	print TITLE
	print '*' * len(TITLE)
	print
	print INTRO
	print
	
	for i, ln in enumerate(lines):
		print separator
		print fmt % ln
	print separator

if __name__ == '__main__':
	main()
