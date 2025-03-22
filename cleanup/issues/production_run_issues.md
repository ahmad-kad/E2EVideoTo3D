# E2E3D Production Run Issues Log

This document tracks issues encountered during the production run of the E2E3D pipeline and their resolutions.

## Issues Tracking

| Issue # | Description | Solution | Status |
|---------|-------------|----------|--------|
| 1 | Numpy 1.18.5 installation fails in Docker base image build with Cython compilation errors | Update numpy version to a newer pre-compiled wheel that doesn't require compilation | Fixed |
| 2 | Requirements installation fails in Docker base image with package compatibility issues | Create a minimal set of required packages and update the Docker build process | In Progress |

## Details

### Issue 1: Numpy Installation Failure

**Description:**
When building the base Docker image, the installation of numpy 1.18.5 fails with Cython compilation errors:
```
Error compiling Cython file:
_sfc64.pyx:90:35: Cannot assign type 'uint64_t (*)(void *) except? -1 nogil' to 'uint64_t (*)(void *) noexcept nogil'
```

**Root Cause:**
The specific numpy version 1.18.5 is trying to compile from source but is incompatible with the current Python environment in the Docker container.

**Solution:**
Update the numpy version to a newer version that provides pre-compiled wheels, eliminating the need for compilation during installation.

### Issue 2: Package Installation Failures

**Description:**
After fixing the numpy issue, we're encountering problems with the installation of other packages in the Docker base image. The error occurs during the installation of the packages listed in `requirements-common.txt`.

**Error Message:**
```
ERROR: failed to solve: process "/bin/sh -c grep -v \"numpy\" requirements-common.txt > /app/requirements-without-numpy.txt && pip3 install --no-cache-dir -r /app/requirements-without-numpy.txt" did not complete successfully: exit code: 1
```

**Root Cause:**
There may be compatibility issues between the packages listed in `requirements-common.txt` or problems with the installation order. Some packages may be incompatible with the Python 3.7 version used in the Docker image.

**Solution:**
1. Create a simplified requirements file with only essential packages
2. Install packages one by one to identify problematic dependencies
3. Update the Docker build process to handle dependencies more robustly 