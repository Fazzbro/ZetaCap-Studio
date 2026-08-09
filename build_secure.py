from setuptools import setup
from Cython.Build import cythonize
import glob
import os

def get_extensions():
    targets = [
        "project/services/*.py",
        "project/workers/*.py"
    ]
    
    files_to_compile = []
    for target in targets:
        files = glob.glob(target)
        for f in files:
            if "__init__.py" in f or "backend_renderer_backup.py" in f:
                continue
            files_to_compile.append(f)
            
    # language_level=3 tells Cython we are using Python 3
    return cythonize(files_to_compile, compiler_directives={'language_level': "3"})

if __name__ == "__main__":
    setup(
        ext_modules=get_extensions(),
        script_args=["build_ext", "--inplace"]
    )
