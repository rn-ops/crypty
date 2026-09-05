cmake_minimum_required(VERSION 3.20)
project(crypty VERSION 0.1.0 LANGUAGES CXX)

include(CTest)

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

if(WIN32)
	add_executable(crypty WIN32 app/main.cpp ui/desktop_ui.cpp)
	target_include_directories(crypty PRIVATE ui)
	target_link_libraries(crypty PRIVATE crypty_core comctl32)
	target_compile_features(crypty PRIVATE cxx_std_17)
else()
	add_custom_target(crypty_demo ALL
		COMMAND ${CMAKE_COMMAND} -E echo "Crypty native demo currently targets Windows; open ui/index.html for the browser fallback"
		WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}
	)
endif()
