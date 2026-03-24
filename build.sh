#!/bin/bash

# Financial Data Pipeline - Build and Setup Script
# This script handles dependency installation and building

set -e  # Exit on any error

echo "=========================================="
echo "Financial Data Pipeline - Build Script"
echo "=========================================="

# Detect OS
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    OS="linux"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    OS="unknown"
fi

echo "Detected OS: $OS"

# ============ Dependency Installation ============

install_dependencies() {
    if [ "$OS" == "linux" ]; then
        echo "Installing Linux dependencies..."
        sudo apt-get update
        sudo apt-get install -y \
            build-essential \
            cmake \
            libcurl4-openssl-dev \
            libsqlite3-dev \
            git \
            wget
    elif [ "$OS" == "macos" ]; then
        echo "Installing macOS dependencies..."
        # Check if Homebrew is installed
        if ! command -v brew &> /dev/null; then
            echo "Installing Homebrew..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
        fi
        
        brew install cmake curl sqlite3
    fi
}

# ============ Download JSON Library ============

setup_json_library() {
    echo "Setting up nlohmann/json library..."
    
    if [ ! -f "include/nlohmann/json.hpp" ]; then
        mkdir -p include/nlohmann
        echo "Downloading json.hpp from GitHub..."
        wget -q https://github.com/nlohmann/json/releases/download/v3.11.2/json.hpp \
            -O include/nlohmann/json.hpp
        echo "JSON library downloaded successfully"
    else
        echo "JSON library already exists"
    fi
}

# ============ Build Project ============

build_project() {
    echo "Building project..."
    
    if [ -d "build" ]; then
        echo "Cleaning previous build..."
        rm -rf build
    fi
    
    mkdir -p build
    cd build
    
    echo "Running CMake..."
    cmake ..
    
    echo "Compiling..."
    make
    
    cd ..
    
    if [ -f "build/financial_pipeline" ]; then
        echo "✓ Build successful!"
        echo "Executable: ./build/financial_pipeline"
    else
        echo "✗ Build failed!"
        exit 1
    fi
}

# ============ Configuration Setup ============

setup_configuration() {
    echo ""
    echo "=========================================="
    echo "Configuration Setup"
    echo "=========================================="
    
    if [ ! -f "config.json" ]; then
        echo "config.json not found. Creating template..."
        # Template creation is handled elsewhere
    fi
    
    echo ""
    echo "Please edit config.json with your settings:"
    echo "  1. Add your FRED API key (get from https://fredaccount.stlouisfed.org)"
    echo "  2. Configure stock symbols you want to track"
    echo "  3. Set date range and other preferences"
    echo ""
    
    read -p "Press Enter when configuration is complete..."
}

# ============ Verify Installation ============

verify_installation() {
    echo ""
    echo "=========================================="
    echo "Verifying Installation"
    echo "=========================================="
    
    local missing_deps=0
    
    # Check curl
    if ! pkg-config --exists libcurl; then
        echo "✗ libcurl not found"
        missing_deps=$((missing_deps + 1))
    else
        echo "✓ libcurl found"
    fi
    
    # Check sqlite3
    if ! pkg-config --exists sqlite3; then
        echo "✗ sqlite3 not found"
        missing_deps=$((missing_deps + 1))
    else
        echo "✓ sqlite3 found"
    fi
    
    # Check cmake
    if ! command -v cmake &> /dev/null; then
        echo "✗ cmake not found"
        missing_deps=$((missing_deps + 1))
    else
        echo "✓ cmake found ($(cmake --version | head -n1))"
    fi
    
    # Check C++ compiler
    if ! command -v g++ &> /dev/null && ! command -v clang++ &> /dev/null && ! command -v clang++ &> /dev/null; then
        echo "✗ C++ compiler not found"
        missing_deps=$((missing_deps + 1))
    else
        echo "✓ C++ compiler found"
    fi
    
    if [ $missing_deps -gt 0 ]; then
        echo ""
        echo "Some dependencies are missing. Run this script to install them:"
        echo "  ./build.sh --install-deps"
        return 1
    fi
    
    return 0
}

# ============ Usage ============

print_usage() {
    cat << EOF
Usage: ./build.sh [OPTIONS]

Options:
    --install-deps      Install system dependencies
    --setup-json         Download nlohmann/json library
    --build             Build the project (default)
    --clean             Clean build artifacts
    --verify            Verify installation
    --full              Install deps, setup, and build (recommended for first run)
    --help              Show this message

Examples:
    ./build.sh                    # Build project (assumes deps installed)
    ./build.sh --full            # Complete setup from scratch
    ./build.sh --install-deps    # Install dependencies only
    ./build.sh --clean           # Clean build artifacts

EOF
}

# ============ Main Script ============

# Default action
ACTION="build"

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --install-deps)
            install_dependencies
            shift
            ;;
        --setup-json)
            setup_json_library
            shift
            ;;
        --build)
            ACTION="build"
            shift
            ;;
        --clean)
            echo "Cleaning build artifacts..."
            rm -rf build CMakeCache.txt CMakeFiles
            echo "Clean complete"
            exit 0
            ;;
        --verify)
            verify_installation
            exit $?
            ;;
        --full)
            install_dependencies
            setup_json_library
            verify_installation
            build_project
            setup_configuration
            exit 0
            ;;
        --help)
            print_usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            print_usage
            exit 1
            ;;
    esac
done

# Execute main action
case $ACTION in
    build)
        if ! verify_installation; then
            echo ""
            echo "Installation verification failed. Run with --install-deps first."
            exit 1
        fi
        setup_json_library
        build_project
        ;;
esac

echo ""
echo "=========================================="
echo "Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "  1. Edit config.json with your API keys and settings"
echo "  2. Run: ./build/financial_pipeline"
echo ""
