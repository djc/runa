*******************
High-level overview
*******************

Rationale
=========

Having written lots of Python code over the past 10 years (in several capacities),
I greatly admire the Python programming language.
Here are some important things it gets right:

1. **Readability** -- Python is often mentioned as almost pseudo-language;
   there is very little syntactic noise.
   Using indentation to mark blocks is a great way to ensure
   visual scanning matches the understanding of the parser,
   and the colons used to introduce blocks make this even easier.

2. **Built-in namespacing** -- except for a relatively small set of built-ins,
   every name used in Python code is introduced in the same file.
   This makes it much easier to understand new code;
   you can always figure out how a variable was introduced into the current context.
   (Similarly, explicit ``self`` means that arguments and other variables are clearly
   distinguished from object members.)

3. **Exceptions** -- while this point may be controversial,
   I think exceptions are a better error handling method than using status returns.
   Errors signalled through exceptions can be handled at the correct layer,
   whereas status returns have to be handled and propagated to the next layer explicitly
   (resulting in cluttered code).
   Ned Batchelder has written `eloquently`_ on `this subject`_.

4. **Flexible type system** -- relying on duck typing of well-defined "protocols"
   trivially allows implementation of new classes conforming to pre-existing interfaces.
   Run-time reflection is available to do run-time type checking where necessary,
   and no extra work is necessary to implement generics.

However, the Python language also has some clear drawbacks.

1. **Implementation complexity** -- as a scripting language,
   Python code requires substantial accidental complexity to run
   (e.g. lots of hash table lookups and inefficient memory allocation).
   In CPython, this manifests as run-time overhead (i.e. lower performance)
   while keeping the virtual machine implementation relatively simple.
   Alternative implementations, such as `PyPy`_ or `Pyston`_,
   attempt to eliminate the run-time overhead at the cost of requiring
   significantly more complexity in a good JIT compiler.

2. **Basic mistakes are caught later** -- unlike languages where more time is spent
   on checking the source code in a compilation step before running it,
   most errors in Python code are only caught at run-time.
   This makes it harder to catch mistakes like typos or type errors,
   especially in large or legacy projects.
   Automated tests can be a good way to make these easier to find,
   but generating enough coverage is a significant investment.

3. **Implicit types** -- while explicit type annotations are mostly superfluous
   in small projects, research has shown that explicit type annotations can
   provide benefits as a form of documentation in larger projects.

It has been my hypothesis for some time that many of the attractive qualities of Python
do not depend on it being a dynamically-typed interpreted language.
Runa is my attempt to verify this hypothesis,
by building a compiler for a language that has the benefits mentioned above,
while avoiding the stated drawbacks.

.. _eloquently: http://nedbatchelder.com/text/exceptions-vs-status.html
.. _this subject: http://nedbatchelder.com/text/exceptions-in-the-rainforest.html
.. _PyPy: http://pypy.org/
.. _Pyston: http://blog.pyston.org/


Roadmap
=======

I'm currently working to build an initial release of the Runa compiler.
Here are some things left to do that should be done before such a release:

* **Type system** -- immmutability, correct handling of owner types
* **Memory/resource management** -- make sure cleanup works correctly
* **Fill out core types** -- number types, ``Str`` and ``Array``
* **Add collection types** -- ``List``, ``Dict`` and ``Set``
* **Argument handling** -- default args, ``*args``, ``**kwargs``
* **I/O interactions** -- reading from and writing to files and network
* **Documentation** -- some tutorial materials, API reference, etc
