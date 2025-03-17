#!/bin/bash

# install_mesh_tools.sh - Helper script to install mesh generation tools
# 
# This script helps install:
# 1. PoissonRecon - for generating meshes from point clouds
# 2. Open3D and related Python libraries if needed

set -e  # Exit on error

WORK_DIR=$(pwd)
POISSON_DIR="$WORK_DIR/tools/PoissonRecon"
PLATFORM=$(uname -s)

# Show help message
show_help() {
    echo "Usage: $0 [OPTIONS] [COMMAND]"
    echo ""
    echo "Commands:"
    echo "  all                 Install all mesh tools (default)"
    echo "  poisson             Install PoissonRecon only"
    echo "  python-deps         Install Python dependencies only"
    echo ""
    echo "Options:"
    echo "  -h, --help          Show this help message"
    echo "  -c, --clean         Clean existing installations before installing"
    echo ""
    echo "Examples:"
    echo "  $0                           # Install all mesh tools"
    echo "  $0 poisson                   # Install PoissonRecon only"
    echo "  $0 --clean all               # Clean and install all tools"
    echo ""
}

# Parse command line options
CLEAN=false
COMMAND="all"

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -c|--clean)
            CLEAN=true
            shift
            ;;
        all|poisson|python-deps)
            COMMAND="$1"
            shift
            ;;
        *)
            echo "Error: Unknown option or command '$1'"
            show_help
            exit 1
            ;;
    esac
done

# Function to install Python dependencies
install_python_deps() {
    echo "Installing Python mesh generation dependencies..."
    
    if [[ -f "requirements.txt" ]]; then
        pip install -r requirements.txt
    else
        pip install open3d numpy-stl pymeshlab trimesh pyntcloud pyvista
    fi
    
    echo "Python dependencies installed!"
    echo "You can now use Open3D for mesh generation in the pipeline."
}

# Function to install PoissonRecon
install_poisson() {
    echo "Installing PoissonRecon..."
    
    # Check dependencies
    if [[ $PLATFORM == "Linux" ]]; then
        echo "Checking Linux dependencies..."
        if ! command -v cmake &> /dev/null; then
            echo "Installing cmake..."
            sudo apt-get update && sudo apt-get install -y cmake build-essential
        fi
    elif [[ $PLATFORM == "Darwin" ]]; then
        echo "Checking macOS dependencies..."
        if ! command -v brew &> /dev/null; then
            echo "Homebrew not found. Installing..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        
        if ! command -v cmake &> /dev/null; then
            echo "Installing cmake..."
            brew install cmake
        fi
    else
        echo "Unsupported platform: $PLATFORM"
        echo "Please install cmake and git manually, then try again."
        exit 1
    fi
    
    # Create tools directory
    mkdir -p "tools"
    cd "tools"
    
    # Clean if requested
    if [[ $CLEAN == true && -d "PoissonRecon" ]]; then
        echo "Cleaning existing PoissonRecon installation..."
        rm -rf "PoissonRecon"
    fi
    
    # Clone and build PoissonRecon
    if [[ ! -d "PoissonRecon" ]]; then
        echo "Cloning PoissonRecon repository..."
        git clone https://github.com/mkazhdan/PoissonRecon.git
        cd "PoissonRecon"
    else
        echo "Using existing PoissonRecon repository..."
        cd "PoissonRecon"
        git pull
    fi
    
    echo "Building PoissonRecon..."
    # Use CMake build
    mkdir -p build
    cd build
    cmake ..
    make
    
    # Add binaries to PATH
    POISSON_BIN_DIR="$PWD"
    cd "$WORK_DIR"
    
    echo ""
    echo "PoissonRecon installed successfully at:"
    echo "$POISSON_BIN_DIR"
    echo ""
    echo "To use PoissonRecon in the pipeline, you need to:"
    echo "1. Add the binary to your PATH:"
    echo "   export PATH=\"$POISSON_BIN_DIR:\$PATH\""
    echo ""
    echo "2. Or set the MESHING_TOOL environment variable to 'poisson' and ensure"
    echo "   the binary is in your PATH before running the pipeline."
    echo ""
    
    # If running on Linux, offer to update .bashrc
    if [[ $PLATFORM == "Linux" ]]; then
        read -p "Do you want to add PoissonRecon to your PATH in .bashrc? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "export PATH=\"$POISSON_BIN_DIR:\$PATH\"" >> ~/.bashrc
            echo "Added to .bashrc. Please restart your shell or run 'source ~/.bashrc'"
        fi
    elif [[ $PLATFORM == "Darwin" ]]; then
        read -p "Do you want to add PoissonRecon to your PATH in .zshrc? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            echo "export PATH=\"$POISSON_BIN_DIR:\$PATH\"" >> ~/.zshrc
            echo "Added to .zshrc. Please restart your shell or run 'source ~/.zshrc'"
        fi
    fi
}

# Execute the command
case $COMMAND in
    all)
        install_python_deps
        install_poisson
        
        echo ""
        echo "All mesh tools installed successfully!"
        echo "You can now use the mesh generation feature in the pipeline."
        ;;
        
    poisson)
        install_poisson
        ;;
        
    python-deps)
        install_python_deps
        ;;
        
    *)
        echo "Error: Unknown command '$COMMAND'"
        show_help
        exit 1
        ;;
esac 