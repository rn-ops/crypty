cmake_minimum_required(VERSION 3.20)
project(crypty VERSION 0.1.0 LANGUAGES CXX)

include(CTest)
find_package(Python3 COMPONENTS Interpreter REQUIRED)

add_library(crypty_core
	core/src/workflow.cpp
	reporting/report.cpp
)
target_include_directories(crypty_core PUBLIC core/include reporting)
target_compile_features(crypty_core PUBLIC cxx_std_17)

if(BUILD_TESTING)
	add_executable(crypty_workflow_test tests/workflow_test.cpp)
	target_link_libraries(crypty_workflow_test PRIVATE crypty_core)
	add_test(NAME crypty_workflow COMMAND crypty_workflow_test)
endif()

add_custom_target(crypty_ui
	COMMAND ${Python3_EXECUTABLE} -m crypty.app.main
	WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/..
	COMMENT "Launching the Crypty PySide6 UI"
)
