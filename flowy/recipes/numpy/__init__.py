import os
from os.path import dirname, join

import pythonforandroid.recipes.numpy as p4a_numpy
from pythonforandroid.recipes.numpy import NumpyRecipe

# p4a's own numpy patches live next to the built-in recipe. Referencing them by
# bare filename fails, because patch paths are resolved relative to *this*
# recipe's directory -- p4a then looks for
#   flowy/recipes/numpy/patches/remove-default-paths.patch
# and aborts with "Can't open patch file". Resolve them absolutely.
P4A_PATCH_DIR = join(dirname(p4a_numpy.__file__), 'patches')


class NumpyCompatRecipe(NumpyRecipe):
    """p4a's numpy (1.22.3) plus a distutils compatibility patch.

    numpy 1.22.3's bundled numpy.distutils calls compiler.cxx_compiler() in
    numpy/core/setup.py:

        config_cmd.compiler = bk_c.cxx_compiler()

    Newer setuptools' distutils no longer exposes that helper:

        AttributeError: 'UnixCCompiler' object has no attribute 'cxx_compiler'

    Downgrading setuptools globally is not an option -- pyzmq's setup.py does
    `from setuptools.errors import OptionError`, which old releases lack -- so
    patch numpy to fall back to the C compiler when the C++ one is missing.
    get_mathlib_info() only needs *a* compiler to probe libm; the extension
    itself is still compiled with the C++ compiler afterwards.
    """

    name = 'numpy'
    patches = [
        join(P4A_PATCH_DIR, 'remove-default-paths.patch'),
        join(P4A_PATCH_DIR, 'add_libm_explicitly_to_build.patch'),
        join(P4A_PATCH_DIR, 'ranlib.patch'),
        join('patches', 'cxx_compiler.patch'),
    ]


recipe = NumpyCompatRecipe()
