from pythonforandroid.recipe import Recipe
from pythonforandroid.logger import shprint
from pythonforandroid.util import current_directory
from os.path import join, basename
import sh


class CapnpRecipe(Recipe):
    # v1.0.1 lacks CallContext::allowCancellation(), which both pycapnp
    # v1.0.0 and v1.1.0 call in their .pyx:
    #   error: no member named 'allowCancellation' in
    #     'capnp::CallContext<capnp::DynamicStruct, capnp::DynamicStruct>'
    # Match pycapnp v1.1.0 with the capnproto release it was written against.
    version = 'b34ec28cceaf15b1082b74b50f03f770873c3636'  # v1.1.0
    url = 'git+https://github.com/capnproto/capnproto.git'
    patches = ['path.patch']

    def get_recipe_env(self, arch, **kwargs):
        env = super().get_recipe_env(arch)
        env['ANDROID_NDK_ROOT'] = self.ctx.ndk_dir
        env['NDK_VERSION'] = 'android-ndk-r25b'
        env['PATH'] = '{}:{}'.format(self.ctx.ndk.llvm_prebuilt_dir, env['PATH'])
        return env

    def build_arch(self, arch):
        env = self.get_recipe_env(arch)

        curdir = join(self.get_build_dir(arch.arch), "c++")

        with current_directory(curdir):
            bash = sh.Command('bash')
            shprint(sh.autoreconf, '-i', _env=env)
            shprint(bash,
                './configure',
                '--host=arm-linux-androideabi',
                'CC={}-clang'.format(arch.target),
                'CXX={}-clang++'.format(arch.target),
                '--with-external-capnp',
                '--without-fibers',
                # Without this autoconf builds libcapnp/.a only, so .libs ends
                # up with no lib*.so.* at all -- which is exactly what the
                # explicit check below reported after the version bump.
                '--enable-shared',
                '--disable-static',
                'CXXFLAGS=-fPIC -fPIE -shared -mno-outline-atomics',
                'LIBS=-ldl',
                _env=env)
            shprint(sh.make, _env=env)
            # Copy the freshly linked shared objects out of .libs.
            #
            # Three traps here, each observed in a CI round:
            #  1. The version in the .so name tracks the capnproto release, so a
            #     hardcoded 'lib*-1.0.1.so' glob silently matches nothing after a
            #     version bump; pycapnp then compiles against stale headers and
            #     fails with "no member named 'allowCancellation'".
            #  2. autoconf needs --enable-shared, otherwise only .a files exist.
            #  3. sh.glob() proved unreliable here -- it returned nothing even
            #     with an absolute pattern, while libtool had demonstrably
            #     linked libkj.so/libcapnp.so into that very directory. Use the
            #     stdlib instead; it has no cwd/ quoting surprises.
            import os as _os

            libs_dir = join(curdir, '.libs')
            if not _os.path.isdir(libs_dir):
                raise RuntimeError("capnp: {} does not exist".format(libs_dir))
            real = []
            for entry in sorted(_os.listdir(libs_dir)):
                path = join(libs_dir, entry)
                # Real versioned shared object: libkj.so.1.0.2, libcapnp.so.1.1.0
                if not entry.startswith('lib') or '.so.' not in entry:
                    continue
                if _os.path.islink(path):
                    continue
                real.append(path)
            if not real:
                raise RuntimeError(
                    "capnp: no built libraries in {} (contents: {})".format(
                        libs_dir, sorted(_os.listdir(libs_dir))[:20]))
            for lib in real:
                shprint(sh.cp, '-a', lib, self.ctx.get_libs_dir(arch.arch))
                # Publish the unversioned name so biglink resolves
                # -lcapnp / -lkj / -lkj-async.
                base = lib.split('.so.')[0] + '.so'
                shprint(sh.cp, '-a', lib, base, self.ctx.get_libs_dir(arch.arch))

recipe = CapnpRecipe()