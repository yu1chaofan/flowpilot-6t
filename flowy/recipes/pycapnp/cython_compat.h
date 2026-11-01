/*
 * CPython 3.12+ compatibility shim for Cython-generated code.
 *
 * Cython's SetNameInClass utility emits a call to
 * _PyDict_SetItem_KnownHash() guarded by
 *
 *     #if CYTHON_COMPILING_IN_CPYTHON && PY_VERSION_HEX >= 0x030500A1
 *
 * That symbol lived in cpython/dictobject.c and was declared only in the
 * private header pycore_dict.h, which p4a's python3 build does not install
 * (it ships include/python3.14 only, without the pycore_* headers). The
 * result is a hard compile failure:
 *
 *     capnp/lib/capnp.cpp:109876:7: error: use of undeclared identifier
 *       '_PyDict_SetItem_KnownHash'
 *
 * The fix is deliberately conservative: provide a *macro* that forwards to
 * the public PyDict_SetItem(). We lose only the pre-computed-hash fast path
 * for exact-dict inserts, which is a negligible cost for pycapnp (its hot
 * path is capnp serialization, not dict building), and we get a definition
 * that is correct on every CPython version.
 *
 * We do not try to declare the real private symbol: it is no longer exported
 * from libpython in 3.13+, so a declaration would link on some versions and
 * fail on others.
 *
 * This header must be force-included (-include) so it is seen before
 * capnp.cpp uses the macro.
 */
#ifndef PYCAPNP_CYTHON_COMPAT_H
#define PYCAPNP_CYTHON_COMPAT_H

#include <Python.h>

#if PY_VERSION_HEX >= 0x030C0000
/* Python 3.12+ : _PyDict_SetItem_KnownHash is internal / removed. */
#ifndef _PyDict_SetItem_KnownHash
#define _PyDict_SetItem_KnownHash(d, k, v, h) \
  PyDict_SetItem((PyObject *)(d), (PyObject *)(k), (PyObject *)(v))
#endif
#endif

#if PY_VERSION_HEX >= 0x030C0000
/* Same story for the interpreter-config accessor used by some Cython 3 output. */
#include <Python.h>
#endif

#endif /* PYCAPNP_CYTHON_COMPAT_H */
