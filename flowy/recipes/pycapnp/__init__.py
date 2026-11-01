from os.path import join

from pythonforandroid.recipe import CythonRecipe, Recipe


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
    version = 'v1.0.0'
    depends = ['python3', 'capnp']
    hostpython_prerequisites = ['setuptools', 'cython==0.29.37']
    call_hostpython_via_targetpython = False
    patches = ['build.patch']

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch)
        capnp_dir = Recipe.get_recipe("capnp", self.ctx).get_build_dir(arch.arch)
        env['CXXFLAGS'] += ' -I{}/c++/src/'.format(capnp_dir)
        env['CXXFLAGS'] += ' -L{}/c++/.libs/'.format(capnp_dir)
        return env


recipe = PycapnpRecipe()
