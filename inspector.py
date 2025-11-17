# inspector.py
import importlib
import pkgutil
import sys

print("--- INSPECTOR'S VERDICT ---")

# The name of the library we want to inspect
# In the future, we could pass this as an argument
LIBRARY_TO_INSPECT = "langchain"

try:
    print(f"Attempting to import: {LIBRARY_TO_INSPECT}")
    # Dynamically import the library
    module = importlib.import_module(LIBRARY_TO_INSPECT)
    print(f"SUCCESS: Imported {LIBRARY_TO_INSPECT}")
    print(f"Path: {module.__path__}")
    print("-" * 20)
    print("Walking all modules...")

    # Recursively find and print every single submodule
    # This is the ground truth map of the library
    for submodule in pkgutil.walk_packages(module.__path__, module.__name__ + '.'):
        print(f"Found module: {submodule.name}")

except ImportError as e:
    print(f"!!! INSPECTOR FAILED: Could not import the library. Error: {e}")
    sys.exit(1)
except Exception as e:
    print(f"!!! An unexpected error occurred: {e}")
    sys.exit(1)

print("-" * 20)
print("--- VERDICT COMPLETE ---")
# Exit with a success code. The container will run, print the logs, and then stop.
sys.exit(0)