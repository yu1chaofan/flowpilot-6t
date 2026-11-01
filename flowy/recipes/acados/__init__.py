from os.path import join, dirname, exists
from pythonforandroid.util import current_directory, ensure_dir
from pythonforandroid.recipe import Recipe
from pythonforandroid.toolchain import shprint
import sh


class AcadosRecipe(Recipe):
    version = 'v0.2.2'
    url = 'git+https://github.com/acados/acados.git'
    # NDK r28c clang treats implicit function declarations as errors; qpOASES 3.1embedded
    # calls malloc() without including <stdlib.h>. MessageHandling.h is pulled in by every
    # qpOASES source through Utils.h, so one include fixes all 6 malloc sites.
    patches = ['patches/qpoases_stdlib.patch']
    generated_libraries = [
        'acados/libacados.so',
        'external/blasfeo/libblasfeo.so',
        'external/qpoases/lib/libqpOASES_e.so',
        'external/hpipm/libhpipm.so',
    ]

    def build_arch(self, arch, **kwargs):        
        build_dir = join(self.get_build_dir(arch.arch), 'build')
        ensure_dir(build_dir)
        with current_directory(build_dir):
            env = self.get_recipe_env(arch)

            shprint(sh.cmake,
                    '-DANDROID_ABI={}'.format(arch.arch),
                    '-DANDROID_NATIVE_API_LEVEL={}'.format(self.ctx.ndk_api),
                    '-DCMAKE_TOOLCHAIN_FILE={}'.format(
                        join(self.ctx.ndk_dir, 'build', 'cmake',
                             'android.toolchain.cmake')),
                    '-DCMAKE_ASM_FLAGS=-DOS_LINUX',
                    '-DACADOS_WITH_QPOASES=ON',
                    '-UBLASFEO_TARGET',
                    '-DBLASFEO_TARGET=ARMV8A_ARM_CORTEX_A57',
                    # NDK r28c clang: -std=c99 hides posix_memalign -> implicit decl error in
                    # blasfeo_stdlib.c; qpOASES 3.1 also trips on older -Werror defaults.
                    # _POSIX_C_SOURCE=200112L exposes posix_memalign under -std=c99.
                    '-DCMAKE_C_FLAGS=-D_POSIX_C_SOURCE=200112L',

                    '..',
                    _env=env)
            shprint(sh.make)
            
            sh.cp('-a', *self.generated_libraries, self.ctx.get_libs_dir(arch.arch))

    def download_if_necessary(self):
        """Fetch the pinned tag without tripping over shallow-clone checkout.

        p4a's Recipe.fetch() does `git fetch --depth 1 origin <version>` and
        then `git checkout <version>`. With --depth 1 the tag object itself is
        not brought down, only FETCH_HEAD, so checkout fails with:

            error: pathspec 'v0.2.2' did not match any file(s) known to git

        Detaching onto FETCH_HEAD is equivalent (that IS the tag's commit) and
        works regardless of clone depth.
        """
        import sh
        from pythonforandroid.util import current_directory
        from pythonforandroid.logger import info

        super().download_if_necessary()

        # download() has just run `git fetch --depth 1 origin v0.2.2`, which
        # puts the commit in FETCH_HEAD but not the tag object. p4a then tries
        # `git checkout v0.2.2` later and fails with "pathspec did not match".
        # Detach onto FETCH_HEAD now, while we are still in the same repo.
        build_dir = self.get_build_container_dir(None)
        target = join(build_dir, self.name)
        if exists(join(target, '.git')):
            with current_directory(target):
                info("acados: detaching onto FETCH_HEAD (shallow tag fetch)")
                sh.git.checkout('--force', 'FETCH_HEAD')


recipe = AcadosRecipe()