cmake_minimum_required(VERSION 3.10)
project(FinancialDataPipeline)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(CURL REQUIRED)
find_package(SQLite3 REQUIRED)

# Include directories
include_directories(${CURL_INCLUDE_DIRS})
include_directories(${SQLite3_INCLUDE_DIRS})

# Add nlohmann/json header-only library (download from https://github.com/nlohmann/json)
# If you have it installed system-wide, uncomment the find_package line below
# find_package(nlohmann_json REQUIRED)

# You can also add it as a subdirectory if it's in your project
# add_subdirectory(nlohmann_json)

# Main executable
add_executable(financial_pipeline pipeline.cpp)

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

# Installation target (optional)
install(TARGETS financial_pipeline DESTINATION bin)
