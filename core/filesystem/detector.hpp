
#pragma once

#include <crypty/filesystem/reader.hpp>
#include <crypty/filesystem/types.hpp>

namespace crypty::filesystem {

// Identifies a filesystem from a reader positioned at the
// beginning of a volume. Does not enumerate or recover files.
FilesystemInfo detect_filesystem(const ReadAt& read_at);

} // namespace crypty::filesystem
