Runa
====

.. image:: https://travis-ci.org/djc/runa.svg?branch=master
   :target: https://travis-ci.org/djc/runa

A Python-like systems programming language.

Note: this is pre-alpha quality software. Use at your own peril.

All feedback welcome. Feel free to file bugs, requests for documentation and
any other feedback to the `issue tracker`_, `tweet me`_ or join the #runa
channel on freenode.

.. _issue tracker: https://github.com/djc/runa/issues
.. _tweet me: https://twitter.com/djco/


Installation
------------

Dependencies:

* Python 2.7
* rply (tested with 0.7.2)
* Clang (tested with 3.3 and 3.4)

So far, it has only been tested on 64-bits OS X and Linux and 32-bits Linux.
The LLVM IR targets Yosemite on OS X, this could cause warnings on older
versions. Look at the final lines of ``runac/codegen.py`` to change the
target triple.


How to get started
------------------

Type the following program into a file called ``hello.rns``:

.. code::
   
   def main():
       print('hello, world')

Make sure to use tabs for indentation.
Now, run the compiler to generate a binary, then run it:

.. code::
   
   djc@enrai runa $ ./runa compile hello.rns
   djc@enrai runa $ ./hello
   hello, world

Review the test cases in ``tests/`` for other code that should work.


Hacking
-------

I think the code is fairly readable, but then I wrote most of it. Here are
some pointers if you want to take a look around. The compiler driver
is in ``runac/__main__.py``: it's a small script implementing a few useful
commands. The code actually driving the compiler is in ``runac/__init__.py``.
Here you can see the lexer, parser, transformation passes, codegen, and
compilation of LLVM IR to machine code being done.

The parser, which is based on rply, returns an AST (node classes in
``runac/ast.py``). This gets processed by the AST walker in
``runac/blocks.py`` to get to a control flow graph with shallow basic blocks:
all expressions are flattened into a single statement, with assignment to
temporary variables, and all control flow is structured as a graph, with
relevant AST nodes at the top of this file.

The resulting tree is then passed through a number of transformation passes.
Currently, the ``liveness`` pass determines variable liveness, the ``typer``
pass performs type inference, the ``specialize`` pass improves on the
inferenced types, the ``escapes`` pass performs an escape analysis, and the
``destruct`` pass inserts code to clean up heap-allocated objects.

The transformed tree is then passed to the AST walker in ``runac/codegen.py``,
where LLVM IR is generated. This can then be passed into ``clang``.

A regression test suite is implemented in the ``tests/`` dir, where each
source file (``rns`` extension) represents a single test case. Execute the
entire suite by executing ``make test`` in the root directory.


To do before 0.1
----------------

- Core types: str, array
- Collections: list, dict, set
- Memory management
- Error handling/exceptions
- Argument handling: default args, *args, **kwargs
- Basic documentation
