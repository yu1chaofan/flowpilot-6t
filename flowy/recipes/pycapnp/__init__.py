from os.path import dirname, join
from pythonforandroid.util import ensure_dir

from pythonforandroid.recipe import CythonRecipe, Recipe
from pythonforandroid.logger import info


class PycapnpRecipe(CythonRecipe):
    """pycapnp for python-for-android.

    Why this subclasses CythonRecipe instead of PythonRecipe
    -------------------------------------------------------
    PythonRecipe only builds a wheel via `pip install . --compile --target`.
    Because pycapnp v1.0.0 ships no pyproject.toml, pip builds it in an
    isolated env (/tmp/pip-build-env-*) containing just setuptools, while
    setup.py does `from Cython.Distutils import build_ext` at import time.
    That combination dies with:

        ModuleNotFoundError: No module named 'Cython'

    CythonRecipe instead runs `setup.py build_ext` against the *host* python
    (which has our pinned cython==0.29.37) and, if that fails as expected,
    calls cythonize_build() to produce capnp/lib/capnp.cpp itself. By the time
    pip runs, the .cpp already exists and Cython is no longer needed.

    The Cython pin matters for a second reason: Cython 3 emits CPython private
    symbols (_PyDict_SetItem_KnownHash, _PyInterpreterState_GetConfig) that the
    p4a python3 headers do not expose, which is exactly how pycapnp v2.0.0
    failed in run #1. 0.29.x generates compatible code.

    The build.patch additionally removes the `import pkgconfig` (absent in the
    p4a image) and forces the system-libcapnp path, since p4a's 'capnp' recipe
    already provides libcapnp and exports its dirs through CXXFLAGS.
    """

    url = 'git+https://github.com/capnproto/pycapnp.git'
    version = '50d3a8e96461df768caeddc5ed5e8c5d1114dbce'  # v1.0.0
    depends = ['python3', 'capnp']
    hostpython_prerequisites = ['setuptools', 'cython==0.29.37']
    call_hostpython_via_targetpython = False
    patches = ['build.patch']

    # pycapnp's capnp/lib/capnp.pyx is C++ throughout (it uses libc++, STL
    # containers and `cdef extern from *` C++ helpers). p4a's cythonize_file()
    # shells out to `cython <file>` with only self.cython_args appended and
    # never passes --cplus, so the default C mode fails with:
    #   capnp/lib/capnp.pyx:3924:17: Operation only allowed in c++
    # These args are appended verbatim by recipe.py:1194.
    cython_args = ['-3', '--cplus', '-I', '.']

    def _ensure_host_deps(self, arch):
        """Install setuptools/cython into the host python's site-packages.

        The p4a host python is configured with --without-ensurepip (visible in
        the log's configure line), so `hostpython -m pip` can never work:

            hostpython3/native-build/python3: No module named pip

        Bootstrap through the *building* interpreter instead (the one running
        buildozer, which always has pip) with --target pointing at the host
        python's site-packages. That sidesteps the missing pip entirely and is
        the same trick p4a itself uses when it bootstraps setuptools.
        """
        import sys
        import sh
        from pythonforandroid.toolchain import shprint

        # <native-build>/python3 -> site-packages lives next to the binary
        host_site = join(dirname(self.hostpython_location), 'Lib', 'site-packages')
        ensure_dir(host_site)

        env = self.get_recipe_env(arch)
        env.pop('PYTHONPATH', None)
        # Cython must stay at 0.29.x: Cython 3 emits CPython private symbols
        # (_PyDict_SetItem_KnownHash, _PyInterpreterState_GetConfig) that p4a's
        # headers do not expose.
        shprint(sh.Command(sys.executable), '-m', 'pip', 'install', '-q',
                '--disable-pip-version-check', '--upgrade',
                '--target', host_site,
                'setuptools', 'wheel', 'cython==0.29.37', _env=env)

    def build_arch(self, arch):
        self._ensure_host_deps(arch)
        super().build_arch(arch)

    def cythonize_build(self, env, build_dir="."):
        """Cythonize only the real .pyx files.

        p4a's default walks the tree with fnmatch("*.pyx"), which also picks up
        capnp/templates/module.pyx. That file is a Jinja2 template, not Cython
        source, so cython fails on it:

            capnp/templates/module.pyx:10:1: Expected an identifier or literal
            {% macro getter(field, type) -%}

        pycapnp's own setup.py templates it into capnp/lib/capnp.pyx at build
        time, so we only translate that generated file (plus the standalone
        benchmark helper, which is harmless but skip-worthy).
        """
        from os.path import join
        info("Cythonizing capnp/lib/capnp.pyx only (skipping Jinja2 templates)")
        self.cythonize_file(env, build_dir, join(build_dir, "capnp/lib/capnp.pyx"))

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch)
        capnp_dir = Recipe.get_recipe("capnp", self.ctx).get_build_dir(arch.arch)
        env['CXXFLAGS'] += ' -I{}/c++/src/'.format(capnp_dir)
        env['CXXFLAGS'] += ' -L{}/c++/.libs/'.format(capnp_dir)
        # Cython's SetNameInClass utility calls _PyDict_SetItem_KnownHash on
        # PY_VERSION_HEX >= 0x030500A1 (i.e. every Python we care about). That
        # symbol is declared only in the *private* pycore_dict.h, which the p4a
        # python3 recipe does not install, so the generated C++ fails with
        #   error: use of undeclared identifier '_PyDict_SetItem_KnownHash'
        # (this is not a Cython 3 symptom -- 0.29.33/0.29.37 emit it too, and
        # p4a's python is 3.14 where the symbol is gone entirely).
        # Force-include a shim that maps it onto the public PyDict_SetItem().
        shim = join(dirname(__file__), 'cython_compat.h')
        env['CXXFLAGS'] += ' -include {}'.format(shim)
        env['CFLAGS'] += ' -include {}'.format(shim)
        return env


recipe = PycapnpRecipe()
