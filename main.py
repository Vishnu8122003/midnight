import os
import sys
import asyncio
import shutil

print("\n--- DEBUG: main.py started ---")
print(f"--- DEBUG: Current Directory: {os.getcwd()}")
print(f"--- DEBUG: Contents: {os.listdir('.')}")

# --- AUTO-HEAL LOGIC ---
# If the user uploaded files flat (e.g. 'core', 'plugins' are in root), move them into 'anony'
if os.path.isdir("core") and os.path.isdir("plugins") and not os.path.isdir("anony"):
    print("--- DEBUG: Detected flat upload structure. Auto-healing to 'anony/'... ---")
    os.makedirs("anony", exist_ok=True)
    # Move subfolders
    for folder in ["core", "helpers", "locales", "plugins", "cookies"]:
        if os.path.isdir(folder):
            try:
                shutil.move(folder, os.path.join("anony", folder))
                print(f"--- DEBUG: Moved folder {folder} to anony/ ---")
            except Exception as e:
                print(f"--- DEBUG: Warning: Could not move {folder}: {e} ---")
    # Move core files
    for file in ["__init__.py", "__main__.py"]:
        if os.path.isfile(file):
            try:
                shutil.move(file, os.path.join("anony", file))
                print(f"--- DEBUG: Moved file {file} to anony/ ---")
            except Exception as e:
                print(f"--- DEBUG: Warning: Could not move {file}: {e} ---")

# Handle structure
if os.path.isdir("anony"):
    print("--- DEBUG: Found 'anony' folder. Proceeding... ---")
elif os.path.isdir("AnonXMusic/anony"):
    print("--- DEBUG: Found 'AnonXMusic/anony'. Switching directory... ---")
    os.chdir("AnonXMusic")
    sys.path.append(os.getcwd())

# Import the main bot function
try:
    print("--- DEBUG: Attempting to import anony.__main__... ---")
    from anony.__main__ import main as bot_main
    print("--- DEBUG: Successfully imported bot_main. ---")
except ImportError as e:
    print(f"--- DEBUG: ImportError root: {e} ---")
    # Final fallback: Try to import main from root if still not moved
    try:
        if os.path.isfile("__main__.py"):
            print("--- DEBUG: Found __main__.py in root. Importing... ---")
            import __main__ as bot_main
            bot_main = bot_main.main
        else:
            raise ImportError("Could not find __main__.py anywhere.")
    except (ImportError, AttributeError) as err:
        print(f"--- DEBUG: Final Error: {err} ---")
        print(f"--- DEBUG: Contents after heal: {os.listdir('.')} ---")
        sys.exit(1)

if __name__ == "__main__":
    print("--- DEBUG: Starting event loop... ---")
    # Use the existing event loop to avoid "different loop" errors
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(bot_main())
    except KeyboardInterrupt:
        print("--- DEBUG: Bot stopped by user. ---")
    except Exception as e:
        print(f"--- DEBUG: CRITICAL RUNTIME ERROR: {e} ---")
        import traceback
        traceback.print_exc()
        sys.exit(1)
