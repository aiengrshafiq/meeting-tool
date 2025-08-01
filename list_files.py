import os

def list_project_files(root_dir, ignore_dirs=None):
    if ignore_dirs is None:
        ignore_dirs = {'venv', '.git', '__pycache__','data'}

    for root, dirs, files in os.walk(root_dir):
        # Modify dirs in-place to skip ignored directories
        dirs[:] = [d for d in dirs if d not in ignore_dirs]

        for file in files:
            rel_dir = os.path.relpath(root, root_dir)
            if rel_dir == '.':
                print(file)
            else:
                print(f"{rel_dir}\\{file}")

# Replace 'your_project_folder' with the path to your project
list_project_files('C:\projects\meeting-tool')
