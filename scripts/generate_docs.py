#!/usr/bin/env python3
"""
Documentation Generator

This script generates Markdown documentation from Python docstrings.
"""

import os
import sys
import inspect
import importlib
import pkgutil
import argparse
from typing import List, Dict, Any, Optional, Tuple


def get_module_docstring(module):
    """Return the module docstring as a list of lines."""
    if module.__doc__:
        return [line.strip() for line in module.__doc__.strip().split('\n')]
    return []


def get_class_method_docs(cls) -> Dict[str, List[str]]:
    """Get documentation for class methods."""
    method_docs = {}
    
    for name, member in inspect.getmembers(cls, inspect.isfunction):
        if name.startswith('_') and name != '__init__':
            continue
            
        doc = []
        if member.__doc__:
            doc = [line.strip() for line in member.__doc__.strip().split('\n')]
        
        method_docs[name] = doc
        
    return method_docs


def get_function_docs(func) -> List[str]:
    """Get documentation for a function."""
    if func.__doc__:
        return [line.strip() for line in func.__doc__.strip().split('\n')]
    return []


def get_package_modules(package_name: str) -> List[Tuple[str, Any]]:
    """Get all modules in a package."""
    package = importlib.import_module(package_name)
    
    modules = []
    for _, name, is_pkg in pkgutil.iter_modules(package.__path__, package.__name__ + '.'):
        if is_pkg:
            modules.extend(get_package_modules(name))
        else:
            module = importlib.import_module(name)
            modules.append((name, module))
            
    return modules


def generate_module_doc(module_name: str, module: Any) -> str:
    """Generate documentation for a module."""
    doc = f"# {module_name.split('.')[-1]}\n\n"
    
    # Add module docstring
    module_doc = get_module_docstring(module)
    if module_doc:
        doc += '\n'.join(module_doc) + '\n\n'
    
    # Add class documentation
    for name, member in inspect.getmembers(module, inspect.isclass):
        if member.__module__ != module.__name__:
            continue
            
        doc += f"## Class: {name}\n\n"
        
        # Add class docstring
        class_doc = get_module_docstring(member)
        if class_doc:
            doc += '\n'.join(class_doc) + '\n\n'
            
        # Add method documentation
        method_docs = get_class_method_docs(member)
        for method_name, method_doc in method_docs.items():
            doc += f"### {name}.{method_name}\n\n"
            if method_doc:
                doc += '\n'.join(method_doc) + '\n\n'
    
    # Add function documentation
    for name, member in inspect.getmembers(module, inspect.isfunction):
        if member.__module__ != module.__name__:
            continue
            
        doc += f"## Function: {name}\n\n"
        
        # Add function docstring
        func_doc = get_function_docs(member)
        if func_doc:
            doc += '\n'.join(func_doc) + '\n\n'
    
    return doc


def main():
    parser = argparse.ArgumentParser(description="Generate documentation from Python docstrings")
    parser.add_argument("package", help="Package name to document")
    parser.add_argument("--output-dir", "-o", default="docs/api", help="Output directory for documentation")
    args = parser.parse_args()
    
    # Make sure the output directory exists
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Get all modules in the package
    modules = get_package_modules(args.package)
    
    # Generate documentation for each module
    for module_name, module in modules:
        # Create the documentation file
        module_path = module_name.split('.')
        if len(module_path) > 2:
            # Create subdirectories for nested modules
            subdir = os.path.join(args.output_dir, *module_path[1:-1])
            os.makedirs(subdir, exist_ok=True)
            doc_path = os.path.join(subdir, f"{module_path[-1]}.md")
        else:
            doc_path = os.path.join(args.output_dir, f"{module_path[-1]}.md")
        
        # Generate and write the documentation
        doc = generate_module_doc(module_name, module)
        with open(doc_path, 'w') as f:
            f.write(doc)
        
        print(f"Generated documentation for {module_name} -> {doc_path}")
    
    print(f"\nDocumentation generation complete. Files saved to {args.output_dir}")


if __name__ == "__main__":
    main() 