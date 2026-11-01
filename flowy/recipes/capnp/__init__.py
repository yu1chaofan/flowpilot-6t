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
                'CXXFLAGS=-fPIC -fPIE -shared -mno-outline-atomics',
                'LIBS=-ldl',
                _env=env)
            shprint(sh.make, _env=env)
            with current_directory(join(curdir, '.libs')):
                # The version in the .so name tracks the capnproto release and
                # changes with every bump. Globbing any lib*-<ver>.so keeps this
                # working when `version` moves, instead of silently shipping no
                # libraries (which is what happened when we went from v1.0.1 to
                # v1.1.0 while this glob still said 1.0.1 -- pycapnp then failed
                # with "no member named 'allowCancellation'", because it was
                # compiling against nothing at all).
                libs = sh.glob("lib*.so.*")
                if not libs:
                    raise RuntimeError(
                        "capnp: no built libraries found in {}/.libs".format(curdir))
                for lib in libs:
                    shprint(sh.cp, '-a', lib, self.ctx.get_libs_dir(arch.arch))
                    # Also copy the unversioned symlink target name, so p4a's
                    # biglink step can resolve -lcapnp / -lkj.
                    base = lib.split('.so.')[0] + '.so'
                    shprint(sh.cp, '-a', lib, base, self.ctx.get_libs_dir(arch.arch))


recipe = CapnpRecipe()