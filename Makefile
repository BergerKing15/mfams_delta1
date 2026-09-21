# Makefile for Financial Data Pipeline
# Alternative to CMake for building the project

CXX := g++
CXXFLAGS := -std=c++17 -Wall -Wextra -Wpedantic -O2
LDFLAGS := -lcurl -lsqlite3

# Directories
BUILD_DIR := build
SRC_DIR := src
TEST_DIR := tests
INCLUDE_DIRS := -Isrc/include -Ithird_party

# Files
SOURCES := pipeline.cpp
CONFIG_SOURCES := config_manager.cpp
OBJECTS := $(addprefix $(BUILD_DIR)/,$(SOURCES:.cpp=.o))
CONFIG_OBJECTS := $(addprefix $(BUILD_DIR)/,$(CONFIG_SOURCES:.cpp=.o))
TARGET := $(BUILD_DIR)/financial_pipeline
CONFIG_TARGET := $(BUILD_DIR)/config_manager

# Headers that every object depends on
HEADERS := $(wildcard $(SRC_DIR)/include/*.hpp)

# Test binaries
TESTS := $(BUILD_DIR)/test_market_calendar $(BUILD_DIR)/test_outlier_filter

# Phony targets
.PHONY: all clean build config test help rebuild run

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
	@echo "  test        - Build and run the unit tests"
	@echo "  clean       - Remove build artifacts"
	@echo "  rebuild     - Clean and build"
	@echo "  run         - Build and run the pipeline"
	@echo ""

# Build main pipeline
build: $(TARGET)

$(TARGET): $(OBJECTS)
	@mkdir -p $(@D)
	$(CXX) $(OBJECTS) -o $(TARGET) $(LDFLAGS)
	@echo "✓ Build successful: $(TARGET)"

$(BUILD_DIR)/%.o: $(SRC_DIR)/%.cpp $(HEADERS)
	@mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) $(INCLUDE_DIRS) -c $< -o $@

# Build configuration manager
config: $(CONFIG_TARGET)

$(CONFIG_TARGET): $(CONFIG_OBJECTS)
	@mkdir -p $(@D)
	$(CXX) $(CONFIG_OBJECTS) -o $(CONFIG_TARGET) $(LDFLAGS)
	@echo "✓ Config manager built: $(CONFIG_TARGET)"

# Build and run the unit tests
test: $(TESTS)
	@echo "Running market calendar tests..."
	@./$(BUILD_DIR)/test_market_calendar
	@echo ""
	@echo "Running outlier filter tests..."
	@./$(BUILD_DIR)/test_outlier_filter

$(BUILD_DIR)/test_%: $(TEST_DIR)/test_%.cpp $(HEADERS)
	@mkdir -p $(@D)
	$(CXX) $(CXXFLAGS) $(INCLUDE_DIRS) $< -o $@

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
