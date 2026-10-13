#pragma once

#include "reader.hpp"
#include "types.hpp"

namespace crypty::filesystem {

FilesystemInfo detect_filesystem(const ReadAt& read_at);

}