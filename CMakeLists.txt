cmake_minimum_required(VERSION 3.10)
project(FinancialDataPipeline)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(CURL REQUIRED)
find_package(SQLite3 REQUIRED)

# Include directories
#   src/include  - project headers (market calendar, outlier filter)
#   third_party  - vendored nlohmann/json
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/src/include)
include_directories(${CMAKE_CURRENT_SOURCE_DIR}/third_party)
include_directories(${CURL_INCLUDE_DIRS})
include_directories(${SQLite3_INCLUDE_DIRS})

# Main executable
add_executable(financial_pipeline src/pipeline.cpp)

# Link libraries
target_link_libraries(financial_pipeline 
    PRIVATE 
    ${CURL_LIBRARIES}
    ${SQLite3_LIBRARIES}
)

# Compiler flags for better warnings
if(MSVC)
    target_compile_options(financial_pipeline PRIVATE /W4)
else()
    target_compile_options(financial_pipeline PRIVATE -Wall -Wextra -Wpedantic)
endif()

# Unit tests (header-only, no external deps)
enable_testing()
foreach(test_name test_market_calendar test_outlier_filter)
    add_executable(${test_name} tests/${test_name}.cpp)
    add_test(NAME ${test_name} COMMAND ${test_name})
endforeach()

# Installation target (optional)
install(TARGETS financial_pipeline DESTINATION bin)
