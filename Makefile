# Makefile for Financial Data Pipeline
# Alternative to CMake for building the project

CXX := g++
CXXFLAGS := -std=c++17 -Wall -Wextra -Wpedantic -O2
LDFLAGS := -lcurl -lsqlite3

# Directories
BUILD_DIR := build
SRC_DIR := .
INCLUDE_DIR := include

# Files
SOURCES := pipeline.cpp
CONFIG_SOURCES := config_manager.cpp
OBJECTS := $(addprefix $(BUILD_DIR)/,$(SOURCES:.cpp=.o))
CONFIG_OBJECTS := $(addprefix $(BUILD_DIR)/,$(CONFIG_SOURCES:.cpp=.o))
TARGET := $(BUILD_DIR)/financial_pipeline
CONFIG_TARGET := $(BUILD_DIR)/config_manager

# Phony targets
.PHONY: all clean build config help

# Default target
all: build

# Help
help:
	@echo "Financial Data Pipeline - Makefile"
	@echo ""
	@echo "Usage: make [TARGET]"
	@echo ""
	@echo "Targets:"
	@echo "  all         - Build the main pipeline (default)"
	@echo "  build       - Build the main pipeline"
	@echo "  config      - Build configuration manager utility"
	@echo "  clean       - Remove build artifacts"
	@echo "  rebuild     - Clean and build"
	@echo "  run         - Build and run the pipeline"
	@echo ""

# Create build directory
$(BUILD_DIR):
	@mkdir -p $(BUILD_DIR)

# Build main pipeline
build: $(TARGET)

$(TARGET): $(OBJECTS) | $(BUILD_DIR)
	$(CXX) $(OBJECTS) -o $(TARGET) $(LDFLAGS)
	@echo "✓ Build successful: $(TARGET)"

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -I$(INCLUDE_DIR) -c $< -o $@

# Build configuration manager
config: $(CONFIG_TARGET)

$(CONFIG_TARGET): $(CONFIG_OBJECTS) | $(BUILD_DIR)
	$(CXX) $(CONFIG_OBJECTS) -o $(CONFIG_TARGET) $(LDFLAGS)
	@echo "✓ Config manager built: $(CONFIG_TARGET)"

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp | $(BUILD_DIR)
	$(CXX) $(CXXFLAGS) -I$(INCLUDE_DIR) -c $< -o $@

# Clean build artifacts
clean:
	@echo "Cleaning build artifacts..."
	@rm -rf $(BUILD_DIR)
	@echo "✓ Clean complete"

# Clean and rebuild
rebuild: clean build

# Build and run
run: build
	@echo "Running pipeline..."
	./$(TARGET)

.PHONY: all build config clean rebuild run help
