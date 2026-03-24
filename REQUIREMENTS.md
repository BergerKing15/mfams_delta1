# System Requirements

## Minimum Requirements

- **OS**: Linux, macOS, or Windows (with Visual Studio)
- **CPU**: 1 GHz dual-core processor
- **RAM**: 512 MB
- **Disk Space**: 100 MB for source code + unlimited for database
- **Internet**: Required for API connections

## Required Software

### Essential (Required)

1. **C++ Compiler** (one of the following)
   - GCC 7.0+ (Linux, macOS via Homebrew)
   - Clang 5.0+ (Linux, macOS, Windows)
   - Microsoft Visual Studio 2015+ (Windows)
   - MinGW-w64 (Windows)

2. **CMake** 3.10+
   - Download: https://cmake.org/download/
   - Or: `apt-get install cmake` / `brew install cmake`

3. **libcurl** 7.0+
   - Linux: `libcurl4-openssl-dev`
   - macOS: `curl` (via Homebrew)
   - Windows: Pre-compiled binaries available

4. **SQLite3** 3.0+
   - Linux: `libsqlite3-dev` and `sqlite3`
   - macOS: `sqlite3` (via Homebrew)
   - Windows: Pre-compiled available

### Optional (Recommended)

- **pkg-config**: For finding libraries during compilation
- **Git**: For version control and cloning repositories
- **Python 3**: For advanced data processing and analysis
- **Pandas**: For DataFrames (Python-based data output)

## Installation by Operating System

### Ubuntu/Debian Linux

```bash
# Update package manager
sudo apt-get update

# Install all dependencies at once
sudo apt-get install -y \
    build-essential \
    cmake \
    libcurl4-openssl-dev \
    libsqlite3-dev \
    pkg-config \
    git \
    wget

# Optional but recommended
sudo apt-get install -y \
    sqlite3 \
    python3 \
    python3-pip
```

### Fedora/RHEL/CentOS

```bash
# Install all dependencies
sudo dnf install -y \
    gcc-c++ \
    cmake \
    libcurl-devel \
    sqlite-devel \
    pkgconfig \
    git \
    wget
```

### macOS (with Homebrew)

```bash
# First install Homebrew if not already installed
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew install cmake curl sqlite3 wget

# Optional
brew install python3
```

### Windows

#### Option 1: Visual Studio Community (Recommended)
1. Download: https://visualstudio.microsoft.com/downloads/
2. Select "Desktop development with C++"
3. During installation, include:
   - C++ core features
   - CMake tools for Windows
   - Windows 10/11 SDK

#### Option 2: MinGW + CMake
1. Install MinGW-w64: https://www.mingw-w64.org/
2. Install CMake: https://cmake.org/download/
3. Install libcurl for Windows: https://curl.se/download.html
4. Install SQLite3 for Windows: https://www.sqlite.org/download.html

#### Option 3: WSL (Windows Subsystem for Linux)
```bash
# Inside WSL terminal
wsl --install

# Then follow Ubuntu/Debian instructions above
sudo apt-get update
sudo apt-get install -y build-essential cmake libcurl4-openssl-dev libsqlite3-dev
```

## Dependency Details

### libcurl

**Purpose**: HTTP client library for API requests
- **Version**: 7.0 or later
- **Used for**: FRED API and Yahoo Finance API requests
- **Size**: ~3-5 MB compiled

**Installation Verification**:
```bash
curl --version
pkg-config --modversion libcurl
```

### SQLite3

**Purpose**: Embedded database engine
- **Version**: 3.0 or later (3.30+ recommended)
- **Used for**: Local data storage and querying
- **Size**: ~1-2 MB compiled

**Installation Verification**:
```bash
sqlite3 --version
pkg-config --modversion sqlite3
```

### CAcert Bundle

**Purpose**: SSL/TLS certificate verification for HTTPS connections
- **Important**: Required for API calls to work
- **Download**: Usually included with curl

**Installation**:
```bash
# Linux
sudo apt-get install ca-certificates

# macOS
brew install curl-ca-bundle

# Windows (usually automatic with Visual Studio)
```

### nlohmann/json

**Purpose**: Header-only JSON library for data parsing
- **Version**: 3.10+
- **Size**: ~500 KB (header file only)
- **Download**: Automatically handled by build script

**Alternative Installation**:
```bash
# System-wide installation
sudo apt-get install nlohmann-json3-dev  # Linux

# Or manual
mkdir -p include/nlohmann
wget https://github.com/nlohmann/json/releases/download/v3.11.2/json.hpp \
    -O include/nlohmann/json.hpp
```

## Python Dependencies (Optional)

If you want to use Python for advanced data processing:

```bash
# Install Python packages
pip install pandas numpy scipy matplotlib
```

## Compilation Flags / Optimization

### Debug Build (with symbols)
```bash
cmake -DCMAKE_BUILD_TYPE=Debug ..
```

### Release Build (optimized, no symbols)
```bash
cmake -DCMAKE_BUILD_TYPE=Release ..
```

### With Address Sanitizer (detect memory leaks)
```bash
cmake -DCMAKE_CXX_FLAGS="-fsanitize=address" ..
```

## Verifying Installation

### Complete System Check

Run this script to verify all dependencies:

```bash
#!/bin/bash
echo "Checking system requirements..."

# C++ Compiler
if command -v g++ &> /dev/null; then
    echo "✓ GCC/G++: $(g++ --version | head -n1)"
elif command -v clang++ &> /dev/null; then
    echo "✓ Clang++: $(clang++ --version | head -n1)"
else
    echo "✗ No C++ compiler found"
fi

# CMake
if command -v cmake &> /dev/null; then
    echo "✓ CMake: $(cmake --version | head -n1)"
else
    echo "✗ CMake not found"
fi

# pkg-config
if command -v pkg-config &> /dev/null; then
    echo "✓ pkg-config: $(pkg-config --version)"
else
    echo "✗ pkg-config not found"
fi

# libcurl
if pkg-config --exists libcurl; then
    echo "✓ libcurl: $(pkg-config --modversion libcurl)"
else
    echo "✗ libcurl not found"
fi

# SQLite3
if pkg-config --exists sqlite3; then
    echo "✓ SQLite3: $(pkg-config --modversion sqlite3)"
else
    echo "✗ SQLite3 not found"
fi

# Git
if command -v git &> /dev/null; then
    echo "✓ Git: $(git --version)"
else
    echo "⚠ Git not found (optional)"
fi

echo "System check complete!"
```

## Troubleshooting Installation

### "Cannot find -lcurl"
```bash
# Linux
sudo apt-get install libcurl4-openssl-dev
pkg-config --cflags --libs libcurl

# macOS
brew install curl
pkg-config --cflags --libs libcurl
```

### "Cannot find -lsqlite3"
```bash
# Linux
sudo apt-get install libsqlite3-dev
pkg-config --cflags --libs sqlite3

# macOS
brew install sqlite3
pkg-config --cflags --libs sqlite3
```

### CMake Cannot Find Packages
```bash
# Update pkg-config database
pkg-config --list-all | grep -E "curl|sqlite"

# Or set paths manually
cmake .. -DCURL_LIBRARY=/usr/lib/libcurl.so -DCURL_INCLUDE_DIR=/usr/include
```

### "pkg-config not found"
```bash
# Linux
sudo apt-get install pkg-config

# macOS
brew install pkg-config
```

## Docker Setup (Alternative)

If you prefer containerized development:

```dockerfile
FROM ubuntu:22.04

RUN apt-get update && apt-get install -y \
    build-essential \
    cmake \
    libcurl4-openssl-dev \
    libsqlite3-dev \
    wget \
    git

WORKDIR /app

# Copy your code
COPY . /app

# Build
RUN mkdir build && cd build && cmake .. && make

# Run
CMD ["./build/financial_pipeline"]
```

Build and run:
```bash
docker build -t financial-pipeline .
docker run financial-pipeline
```

## Estimated Space Requirements

| Component | Size |
|-----------|------|
| GCC/Clang | 500 MB - 2 GB |
| CMake | 50 MB |
| libcurl | 5 MB |
| SQLite3 | 2 MB |
| nlohmann/json | 500 KB |
| Build artifacts | 10-20 MB |
| Database (per year) | 10-100 MB |
| **Total** | ~1-2.5 GB minimal |

## Network Requirements

- **FRED API**: 1 request per second (120/min with key)
- **Yahoo Finance**: ~1-2 requests per second (no official limit)
- **Bandwidth**: ~1-5 KB per request
- **Typical daily usage**: ~500 KB

## Performance Notes

- **Single stock data**: ~1-2 seconds to fetch and process
- **10 stocks**: ~15-20 seconds
- **50 FRED series**: ~30-60 seconds
- **Database queries**: <100 ms for 1 year of data

## Version Compatibility

| Component | Minimum | Tested | Recommended |
|-----------|---------|--------|-------------|
| C++       | C++17   | C++17  | C++20+      |
| CMake     | 3.10    | 3.20+  | 3.24+       |
| libcurl   | 7.0     | 7.75+  | 7.87+       |
| SQLite    | 3.0     | 3.37+  | 3.40+       |
| GCC       | 7.0     | 10+    | 12+         |
| Clang     | 5.0     | 12+    | 15+         |

## Getting Help

If you encounter any installation issues:

1. Check this requirements file
2. Review the QUICKSTART.md
3. Look at CMAKE build output for specific missing libraries
4. Run the verification scripts above
5. Check for typos in library names or paths
