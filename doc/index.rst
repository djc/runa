Start
=====

.. image:: https://travis-ci.org/djc/runa.svg?branch=master
   :target: https://travis-ci.org/djc/runa
.. image:: https://img.shields.io/coveralls/djc/runa.svg?branch=master
   :target: https://coveralls.io/r/djc/runa?branch=master

Runa is a Python-like systems programming language.
This means that the design borrows as much from Python
as makes sense in the context of a statically-typed, compiled language,
and tries to apply the `Zen of Python`_ to everything else.
The most important design goals for Runa are developer ergonomics
and performance.
The compiler is written in Python and targets LLVM IR;
there's no run-time.

Note: this is pre-alpha quality software. Use at your own peril.

All feedback welcome. Feel free to file bugs, requests for documentation and
any other feedback to the `issue tracker`_, `tweet me`_ or join the #runa
channel on freenode.

.. _issue tracker: https://github.com/djc/runa/issues
.. _tweet me: https://twitter.com/djco/
.. _Zen of Python: https://www.python.org/dev/peps/pep-0020/

Table of contents
-----------------

.. toctree::
   :maxdepth: 2
   
   overview.rst
   hacking.rst
   grammar.rst
   refs.rst
   notes.rst
