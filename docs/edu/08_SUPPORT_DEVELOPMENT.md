# Development Workflow and Contribution Guidelines

## Introduction

This document outlines the development workflow and contribution guidelines for the E2E3D platform. It provides information on project structure, coding standards, testing practices, and the process for submitting contributions to help new developers become productive quickly.

## Project Structure

### Repository Organization

The E2E3D repository is organized into several key directories:

```
e2e3d/
├── production/             # Production-ready code
│   ├── scripts/            # Core scripts for reconstruction and API
│   ├── utils/              # Utility functions and helpers
│   └── tests/              # Unit and integration tests
├── dags/                   # Airflow DAG definitions
├── docker/                 # Docker-related files and configurations
├── kubernetes/             # Kubernetes manifests (if applicable)
├── docs/                   # Documentation
│   ├── edu/                # Educational materials
│   ├── api/                # API documentation
│   └── architecture/       # Architecture documents
├── tests/                  # Test suites
│   ├── unit/               # Unit tests
│   └── integration/        # Integration tests
├── configs/                # Configuration files
├── data/                   # Sample data and test datasets
│   ├── input/              # Input data storage
│   └── output/             # Output data storage
└── tools/                  # Development and utility tools
```

### Key Components

The main components of the E2E3D system are:

1. **Reconstruction Service**: Core photogrammetry pipeline
2. **API Service**: REST API for job management and system control
3. **Airflow DAGs**: Workflow definitions for processing jobs
4. **Storage System**: MinIO-based object storage
5. **Monitoring System**: Prometheus and Grafana for metrics

## Development Environment Setup

### Prerequisites

Before starting development, ensure you have:

- Git
- Docker and Docker Compose
- Python 3.9 or later
- A code editor (VSCode recommended)
- Make (optional, for using Makefile)

### Local Development Setup

Follow these steps to set up a local development environment:

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/e2e3d.git
   cd e2e3d
   ```

2. **Create a virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install development dependencies**:
   ```bash
   pip install -r requirements-dev.txt
   ```

4. **Set up pre-commit hooks**:
   ```bash
   pre-commit install
   ```

5. **Start services with Docker Compose**:
   ```bash
   docker-compose -f docker-compose.dev.yml up -d
   ```

6. **Configure environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your local configuration
   ```

## Coding Standards

### Python Style Guide

E2E3D follows the PEP 8 style guide with these additional guidelines:

- Use 4 spaces for indentation
- Maximum line length of 100 characters
- Use docstrings for all public functions, classes, and methods
- Type hints are encouraged for new code

Example of proper function styling:

```python
def process_image_set(
    input_path: str,
    output_path: str,
    options: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Process an image set to produce a 3D reconstruction.
    
    Args:
        input_path: Path to the directory containing input images
        output_path: Path where output files will be saved
        options: Dictionary of processing options
            
    Returns:
        Dictionary containing metadata about the processed results
            
    Raises:
        FileNotFoundError: If input_path does not exist
        ProcessingError: If reconstruction fails
    """
    if not os.path.exists(input_path):
        raise FileNotFoundError(f"Input path not found: {input_path}")
        
    options = options or {}
    default_options = {
        "feature_type": "sift",
        "matcher_type": "flann",
        "reconstruction_quality": "medium"
    }
    
    # Merge default options with provided options
    effective_options = {**default_options, **options}
    
    # Process images
    # ...
    
    return {
        "status": "success",
        "mesh_path": os.path.join(output_path, "mesh", "model.obj"),
        "point_count": 123456,
        "face_count": 78910
    }
```

### Code Organization

Follow these principles for code organization:

- **Single Responsibility**: Each module and class should have a single responsibility
- **Dependency Injection**: Pass dependencies explicitly rather than importing within functions
- **Configuration Separation**: Keep configuration separate from code logic
- **Error Handling**: Provide meaningful error messages and appropriate exception handling

### Git Workflow

The E2E3D project uses a feature branch workflow:

1. **Main Branches**:
   - `main`: Production-ready code
   - `develop`: Integration branch for new features

2. **Feature Branches**:
   - Create feature branches from `develop`
   - Use naming convention: `feature/short-description`
   - Example: `feature/improve-point-cloud-generation`

3. **Fix Branches**:
   - For bug fixes, use: `fix/short-description`
   - Example: `fix/memory-leak-in-meshing`

4. **Release Branches**:
   - For preparing releases: `release/version`
   - Example: `release/1.2.0`

### Commit Messages

Follow these guidelines for commit messages:

- Use the imperative mood ("Add feature" not "Added feature")
- First line is a summary (max 50 characters)
- Leave a blank line after the summary
- Provide details in the body if necessary (wrap at 72 characters)
- Reference issues or tickets where applicable

Example:
```
Add support for OBJ texture export

- Implement UV mapping for texture coordinates
- Add texture atlas generation
- Support both PNG and JPEG textures

Fixes #123
```

## Testing Guidelines

### Test Structure

E2E3D uses a multi-level testing approach:

1. **Unit Tests**: Test individual functions and classes
2. **Integration Tests**: Test interaction between components
3. **End-to-End Tests**: Test complete workflows
4. **Performance Tests**: Measure and verify performance metrics

### Writing Tests

When writing tests, follow these guidelines:

- Use pytest for all new tests
- Name test files with `test_` prefix
- Group tests by functionality and component
- Use fixtures for test setup and teardown
- Mock external dependencies

Example of a unit test:

```python
import pytest
from e2e3d.production.utils.mesh_processing import simplify_mesh

@pytest.fixture
def sample_mesh():
    # Create or load a sample mesh for testing
    vertices = [[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]]
    faces = [[0, 1, 2], [0, 2, 3], [0, 3, 1], [1, 3, 2]]
    return {"vertices": vertices, "faces": faces}

def test_simplify_mesh_reduces_face_count(sample_mesh):
    # Test that mesh simplification reduces the number of faces
    original_face_count = len(sample_mesh["faces"])
    target_face_count = original_face_count // 2
    
    simplified_mesh = simplify_mesh(
        sample_mesh,
        target_face_count=target_face_count
    )
    
    assert len(simplified_mesh["faces"]) <= target_face_count
    assert len(simplified_mesh["vertices"]) <= len(sample_mesh["vertices"])
```

### Test Automation

Tests are automatically run in the CI/CD pipeline on:
- Pull request creation
- Updates to pull requests
- Merges to main branches

## Pull Request Process

### Creating a Pull Request

When submitting changes:

1. **Ensure Tests Pass**: Run tests locally before submitting
2. **Update Documentation**: Add or update relevant documentation
3. **Create a Pull Request**: Submit a PR from your feature branch to `develop`
4. **Fill the PR Template**: Complete all sections of the PR template
5. **Request Review**: Assign appropriate reviewers

### PR Template

The PR template includes:

```markdown
## Description
[Describe the changes in this PR]

## Related Issues
[Link to related issues, e.g., "Fixes #123"]

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Enhancement to existing features
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Tested manually

## Checklist
- [ ] My code follows the style guidelines
- [ ] I have performed a self-review
- [ ] I have commented my code, particularly in hard-to-understand areas
- [ ] I have updated the documentation
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix/feature works
```

### Code Review Process

The code review process includes:

1. **Automated Checks**: CI checks for style, tests, and build
2. **Peer Review**: At least one approval from a team member
3. **Maintainer Review**: Final review by a project maintainer
4. **Merge**: Once approved, the PR can be merged

## Dependency Management

### Python Dependencies

For managing Python dependencies:

- Use specific versions in requirements files
- Pin dependencies for production code
- Group dependencies by purpose (core, dev, test)
- Document the purpose of non-obvious dependencies

Example requirements file structure:
```
requirements-common.txt     # Shared dependencies
requirements-reconstruction.txt   # Reconstruction-specific
requirements-api.txt        # API service-specific
requirements-airflow.txt    # Airflow-specific
requirements-dev.txt        # Development tools
```

### Docker Dependencies

For Docker images:

- Use specific tags for base images
- Document system-level dependencies
- Keep images as small as possible
- Use multi-stage builds for complex dependencies

## Documentation Guidelines

### Code Documentation

For code documentation:

- Use docstrings for all public functions, classes, and methods
- Document parameters, return values, and exceptions
- Provide usage examples for complex functions
- Include references to algorithms or papers when applicable

### Project Documentation

For project documentation:

- Keep the README.md up-to-date with setup and usage instructions
- Maintain architecture documentation in the `docs/architecture` directory
- Document the API in the `docs/api` directory
- Provide tutorials and examples in the `docs/edu` directory

## Versioning and Releases

### Semantic Versioning

E2E3D follows semantic versioning (SemVer):

- **Major Version**: Incompatible API changes
- **Minor Version**: Backwards-compatible new features
- **Patch Version**: Backwards-compatible bug fixes

Example: `1.2.3` where 1 is major, 2 is minor, and 3 is patch.

### Release Process

The release process includes:

1. **Create Release Branch**: From `develop` to `release/x.y.z`
2. **Version Bump**: Update version in code and documentation
3. **Final Testing**: Comprehensive testing of the release candidate
4. **Release Notes**: Document changes, improvements, and fixes
5. **Merge to Main**: Merge the release branch to `main`
6. **Tag Release**: Create a Git tag for the release
7. **Merge Back**: Merge `main` back to `develop`

## Continuous Integration

### CI/CD Pipeline

The CI/CD pipeline includes:

1. **Code Linting**: Check code style and format
2. **Unit Tests**: Run unit tests for all components
3. **Integration Tests**: Run integration tests
4. **Build Images**: Build Docker images
5. **Deployment**: Deploy to staging environments
6. **Performance Tests**: Run performance benchmarks

### CI Configuration

The CI is configured in `.github/workflows` (for GitHub Actions) or similar for other CI systems.

## Troubleshooting Development Issues

### Common Problems

Solutions for common development issues:

1. **Docker Compose Service Won't Start**:
   - Check logs: `docker-compose logs <service_name>`
   - Verify port conflicts: `netstat -tuln`
   - Check resource limits

2. **Tests Failing**:
   - Run with `-v` flag for more details: `pytest -v`
   - Check test dependencies
   - Look for environmental differences

3. **Import Errors**:
   - Verify PYTHONPATH includes the project root
   - Check for circular imports
   - Ensure packages are installed

### Debugging Tools

Useful debugging tools:

- **pdb**: Python's built-in debugger
- **pytest --pdb**: Drop into debugger on test failure
- **Docker logs**: View container logs
- **ipdb**: Enhanced interactive debugger

## Performance Optimization

### Profiling

Tools and methods for profiling:

- **cProfile**: Profile Python code execution
- **memory_profiler**: Monitor memory usage
- **py-spy**: Sampling profiler for running processes

### Optimization Guidelines

When optimizing:

1. **Measure First**: Profile before optimizing
2. **Focus on Hotspots**: Target the most resource-intensive parts
3. **Verify Improvements**: Re-profile after optimization
4. **Maintain Readability**: Don't sacrifice readability for small gains

## Contributing to Documentation

### Documentation Structure

The documentation is organized as:

- **User Guides**: How to use the system
- **API Reference**: Detailed API documentation
- **Architecture**: System design and components
- **Tutorials**: Step-by-step guides
- **Educational Materials**: Conceptual explanations

### Documentation Format

Documentation uses Markdown with these guidelines:

- Use headers for organization (# for title, ## for sections)
- Include code examples with syntax highlighting
- Use bullet points for lists
- Include diagrams for complex concepts (as SVG or PNG)

## Community Guidelines

### Communication Channels

Ways to interact with the community:

- **GitHub Issues**: Bug reports and feature requests
- **Pull Requests**: Code contributions
- **Discussions**: Design and architecture discussions
- **Slack/Discord**: Real-time communication (if applicable)

### Code of Conduct

All contributors must adhere to the code of conduct, which promotes:

- Respectful and inclusive language
- Acceptance of constructive criticism
- Focus on what's best for the community
- Showing empathy towards others

## Conclusion

Following these development workflow and contribution guidelines will help maintain the quality, consistency, and maintainability of the E2E3D platform. By adhering to these standards, contributors can work together effectively to improve and extend the system's capabilities while ensuring a positive experience for all users and developers. 