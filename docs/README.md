# Documentation

This directory contains documentation for the e2e3d project.

## Structure

- `api/`: Auto-generated API documentation from docstrings
- `docker-setup.md`: Guide for Docker setup
- `project-structure.md`: Guide for project structure
- `legacy/`: Legacy documentation

## Generating Documentation

To generate API documentation from docstrings, run:

```bash
make docs
```

Or manually:

```bash
python scripts/generate_docs.py src
```

## Documentation Guidelines

When writing documentation:

1. Use Markdown for all documentation files
2. Include docstrings for all modules, classes, and functions
3. Follow the Google docstring style for Python code
4. Keep documentation up-to-date with code changes
5. Include examples where appropriate

## API Documentation

The API documentation is generated from docstrings in the source code. To ensure good documentation:

- Every module should have a module-level docstring explaining its purpose
- Every class should have a class-level docstring explaining its purpose and usage
- Every method and function should have a docstring explaining:
  - What it does
  - Parameters (with types and descriptions)
  - Return values (with types and descriptions)
  - Exceptions that may be raised
  - Examples of usage (where appropriate) 