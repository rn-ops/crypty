
cmake_minimum_required(VERSION 3.20)

project(crypty VERSION 0.1.0 LANGUAGES CXX)

include(CTest)

# --------------------------------------------------
# Common C++ configuration
# --------------------------------------------------

set(CRYPTY_CXX_STANDARD 17)

# --------------------------------------------------
# Platform adapter
# --------------------------------------------------

if(WIN32)
    set(CRYPTY_PLATFORM_SOURCE
        core/platform/windows_device_access.cpp
    )
elseif(UNIX)
    set(CRYPTY_PLATFORM_SOURCE
        core/platform/posix_device_access.cpp
    )
else()
    message(FATAL_ERROR
        "Crypty device access is not implemented for this platform."
    )
endif()

# --------------------------------------------------
# Existing core: workflow, recovery and reporting
# --------------------------------------------------

add_library(crypty_core STATIC
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
    core/reporting/report.cpp
)

target_compile_features(crypty_core PUBLIC
    cxx_std_${CRYPTY_CXX_STANDARD}
)

target_include_directories(crypty_core
    PUBLIC
        "${CMAKE_CURRENT_SOURCE_DIR}/core/includes"
    PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/core"
        "${CMAKE_CURRENT_SOURCE_DIR}/core/src"
        "${CMAKE_CURRENT_SOURCE_DIR}/core/filesystem"
        "${CMAKE_CURRENT_SOURCE_DIR}/core/recovery"
        "${CMAKE_CURRENT_SOURCE_DIR}/core/reporting"
)

# --------------------------------------------------
# Platform device access
# --------------------------------------------------

add_library(crypty_platform STATIC
    ${CRYPTY_PLATFORM_SOURCE}
)

target_compile_features(crypty_platform PUBLIC
    cxx_std_${CRYPTY_CXX_STANDARD}
)

target_include_directories(crypty_platform
    PUBLIC
        "${CMAKE_CURRENT_SOURCE_DIR}/core/includes"
        "${CMAKE_CURRENT_SOURCE_DIR}/core"
)

# --------------------------------------------------
# Data sanitization
# --------------------------------------------------

add_library(crypty_sanitization STATIC
    core/sanitization/policy_engine.cpp
    core/sanitization/sanitization_engine.cpp
)

target_compile_features(crypty_sanitization PUBLIC
    cxx_std_${CRYPTY_CXX_STANDARD}
)

target_include_directories(crypty_sanitization
    PUBLIC
        "${CMAKE_CURRENT_SOURCE_DIR}/core/includes"
    PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/core/sanitization"
)

# --------------------------------------------------
# Native C ABI bridge
# --------------------------------------------------

add_library(crypty_native SHARED
    core/src/native_bridge.cpp
)

target_link_libraries(crypty_native PRIVATE
    crypty_core
    crypty_platform
    crypty_sanitization
)

target_compile_features(crypty_native PRIVATE
    cxx_std_${CRYPTY_CXX_STANDARD}
)

target_include_directories(crypty_native PRIVATE
    "${CMAKE_CURRENT_SOURCE_DIR}/core"
    "${CMAKE_CURRENT_SOURCE_DIR}/core/src"
    "${CMAKE_CURRENT_SOURCE_DIR}/core/recovery"
    "${CMAKE_CURRENT_SOURCE_DIR}/core/reporting"
)

# --------------------------------------------------
# Tests
# --------------------------------------------------

if(BUILD_TESTING)
    add_executable(crypty_workflow_test
        tests/workflow_test.cpp
    )
    target_link_libraries(crypty_workflow_test PRIVATE crypty_core)
    add_test(NAME crypty_workflow COMMAND crypty_workflow_test)

    add_executable(crypty_filesystem_test
        tests/filesystem_detector_test.cpp
    )
    target_link_libraries(crypty_filesystem_test PRIVATE crypty_core)
    target_include_directories(crypty_filesystem_test PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/core"
    )
    add_test(NAME crypty_filesystem COMMAND crypty_filesystem_test)

    add_executable(crypty_fat32_test
        tests/fat32_recovery_test.cpp
    )
    target_link_libraries(crypty_fat32_test PRIVATE crypty_core)
    target_include_directories(crypty_fat32_test PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/core"
    )
    add_test(NAME crypty_fat32 COMMAND crypty_fat32_test)

    add_executable(crypty_platform_read_test
        tests/platform_read_test.cpp
    )
    target_link_libraries(crypty_platform_read_test PRIVATE crypty_platform)
    add_test(NAME crypty_platform_read COMMAND crypty_platform_read_test)

    add_executable(crypty_ntfs_boot_test
        tests/ntfs_boot_test.cpp
    )
    target_link_libraries(crypty_ntfs_boot_test PRIVATE crypty_core)
    target_include_directories(crypty_ntfs_boot_test PRIVATE
        "${CMAKE_CURRENT_SOURCE_DIR}/core"
    )
    add_test(NAME crypty_ntfs_boot COMMAND crypty_ntfs_boot_test)

    add_executable(crypty_sanitization_policy_test
        tests/sanitization_policy_test.cpp
    )
    target_link_libraries(crypty_sanitization_policy_test
        PRIVATE crypty_sanitization
    )
    add_test(
        NAME crypty_sanitization_policy
        COMMAND crypty_sanitization_policy_test
    )
endif()

# --------------------------------------------------
# Developer convenience
# --------------------------------------------------

find_package(Python3 COMPONENTS Interpreter QUIET)

if(Python3_Interpreter_FOUND)
    add_custom_target(crypty_ui
        COMMAND "${Python3_EXECUTABLE}" -m app.main
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        COMMENT "Launching the Crypty PySide6 UI"
    )
endif()
