import os
import subprocess
import glob
import shutil

def main():
    if os.name == 'nt':
        try:
            subprocess.run(["taskkill", "/F", "/IM", "ZetaCap.exe"], capture_output=True)
        except Exception:
            pass

    print("Step 1: Compiling Python files to Cython binaries...")
    subprocess.run(["python", "build_secure.py"], check=True)

    print("\nStep 2: Hiding original .py files...")
    # Find all .pyd files that were generated
    pyd_files = glob.glob("project/services/*.pyd") + glob.glob("project/workers/*.pyd")
    
    hidden_files = []
    for pyd in pyd_files:
        # pyd name looks like: backend_renderer.cp310-win_amd64.pyd
        base_name = os.path.basename(pyd).split('.')[0]
        dir_name = os.path.dirname(pyd)
        py_file = os.path.join(dir_name, base_name + ".py")
        
        if os.path.exists(py_file):
            bak_file = py_file + ".bak"
            os.rename(py_file, bak_file)
            hidden_files.append((bak_file, py_file))

    print("\nStep 3: Running PyInstaller (it will now only see .pyd files!)...")
    try:
        subprocess.run(["pyinstaller", "--clean", "-y", "ZetaCap.spec"], check=True)
    finally:
        print("\nStep 4: Restoring original .py files...")
        for bak_file, py_file in hidden_files:
            if os.path.exists(bak_file):
                os.rename(bak_file, py_file)

        print("\nStep 5: Cleaning up generated .c files...")
        c_files = glob.glob("project/services/*.c") + glob.glob("project/workers/*.c")
        for c in c_files:
            try:
                os.remove(c)
            except:
                pass
                
        print("\nBuild complete! The secure executable is in the dist folder.")

if __name__ == "__main__":
    main()
