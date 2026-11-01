from os.path import join

from pythonforandroid.recipes.numpy import NumpyRecipe


class NumpyCompatRecipe(NumpyRecipe):
    """numpy 1.22.3 with a distutils compatibility patch.

    p4a pins numpy 1.22.3, whose bundled numpy.distutils calls
    compiler.cxx_compiler() in numpy/core/setup.py:

        config_cmd.compiler = bk_c.cxx_compiler()

    Modern setuptools' distutils no longer exposes that helper, so the build
    dies with:

        AttributeError: 'UnixCCompiler' object has no attribute 'cxx_compiler'

    We cannot simply downgrade setuptools for the whole build: pyzmq's setup.py
    imports setuptools.errors.OptionError, which only exists in newer releases.
    So patch numpy instead -- fall back to the C compiler when the C++ one is
    unavailable. get_mathlib_info() only needs *a* working compiler to probe
    libm, and the extension itself is built later with the C++ compiler anyway.
    """

    name = 'numpy'
    patches = NumpyRecipe.patches + [join('patches', 'cxx_compiler.patch')]


recipe = NumpyCompatRecipe()
