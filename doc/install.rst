Installing Genshi
=================


Prerequisites
-------------

* Python_ 2.4 or later
* Optional: Setuptools_ 0.6c3 or later

.. _python: http://www.python.org/
.. _setuptools: http://cheeseshop.python.org/pypi/setuptools

Setuptools is only required for the `template engine plugin`_, which can be
used to integrate Genshi with Python web application frameworks such as Pylons
or TurboGears. Genshi also provides a Setuptools-based plugin that integrates
its `internationalization support`_ with the Babel_ library, but that support
can also be used without Setuptools being available (although in a slightly
less convenient fashion).

.. _`template engine plugin`: plugin.html
.. _`internationalization support`: i18n.html
.. _babel: http://babel.edgewall.org/


Installing via ``easy_install``
-------------------------------

If you have a recent version of Setuptools_ installed, you can directly install
Genshi using the easy_install command-line tool::

  $ easy_install Genshi

This downloads and installs the latest version of the Genshi package.

If you have an older Genshi release installed and would like to upgrade, add
the ``-U`` option to the above command.


Installing from a Binary Installer
----------------------------------

Binary packages for Windows and Mac OS X are provided for Genshi. To install
from such a package, simply download and open it.


Installing from a Source Tarball
--------------------------------

Once you've downloaded and unpacked a Genshi source release, enter the
directory where the archive was unpacked, and run::

  $ python setup.py install

Note that you may need administrator/root privileges for this step, as this
command will by default attempt to install Genshi to the Python
``site-packages`` directory on your system.

Genshi comes with an optional extension module written in C that is used to
improve performance in some areas. This extension is automatically compiled
when you run the ``setup.py`` script as shown above. In the case that the
extension can not be compiled, possibly due to a missing or incompatible C
compiler, the compilation is skipped. If you'd prefer Genshi to not use this
native extension module, you can explicitly bypass the compilation using the
``--without-speedups`` option::

  $ python setup.py --without-speedups install

For other build and installation options, please consult the easy_install_
and/or the Python distutils_ documentation.

.. _easy_install: http://peak.telecommunity.com/DevCenter/EasyInstall
.. _distutils:  http://docs.python.org/inst/inst.html


Support
-------

If you encounter any problems with Genshi, please don't hesitate to ask
questions on the Genshi `mailing list`_ or `IRC channel`_.

.. _`mailing list`: http://genshi.edgewall.org/wiki/MailingList
.. _`irc channel`: http://genshi.edgewall.org/wiki/IrcChannel
