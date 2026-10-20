
cmake_minimum_required(VERSION 3.20)
project(crypty VERSION 0.1.0 LANGUAGES CXX)

include(CTest)

add_library(crypty_core
    core/src/workflow.cpp

    core/filesystem/detector.cpp
    core/filesystem/volume_info.cpp

    core/recovery/recovery_engine.cpp

    core/recovery/ntfs/ntfs_recovery.cpp
    core/recovery/ntfs/mft_parser.cpp
    core/recovery/ntfs/runlist.cpp
    core/recovery/ntfs/data_attribute.cpp

    core/recovery/fat32/fat32_recovery.cpp
    core/recovery/exfat/exfat_recovery.cpp

    reporting/report.cpp
)


target_include_directories(crypty_core 
    PUBLIC
        core/include
        core/filesystem
        reporting
        "${CMAKE_CURRENT_SOURCE_DIR}/core/include"
    PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/core"
)

target_compile_features(crypty_core PUBLIC cxx_std_17)

add_library(crypty_native SHARED
    core/src/native_bridge.cpp
)

target_link_libraries(crypty_native PRIVATE crypty_core)

target_include_directories(crypty_native PRIVATE
    core/include
    core/filesystem
    reporting
)

target_compile_features(crypty_native PRIVATE cxx_std_17)

if(BUILD_TESTING)
    add_executable(crypty_workflow_test tests/workflow_test.cpp)
    target_link_libraries(crypty_workflow_test PRIVATE crypty_core)
    add_test(NAME crypty_workflow COMMAND crypty_workflow_test)

    add_executable(
        crypty_filesystem_test
        tests/filesystem_detector_test.cpp
    )
    target_link_libraries(crypty_filesystem_test PRIVATE crypty_core)
    add_test(NAME crypty_filesystem COMMAND crypty_filesystem_test)

    add_executable(
        crypty_fat32_test
        tests/fat32_recovery_test.cpp
    )

    target_link_libraries(crypty_fat32_test PRIVATE crypty_core)

    target_compile_features(crypty_fat32_test PRIVATE cxx_std_17)

    add_test(NAME crypty_fat32 COMMAND crypty_fat32_test)
endif()

add_custom_target(crypty_ui
    COMMAND ${Python3_EXECUTABLE} -m crypty.app.main
    WORKING_DIRECTORY ${CMAKE_CURRENT_SOURCE_DIR}/..
    COMMENT "Launching the Crypty PySide6 UI"
)
