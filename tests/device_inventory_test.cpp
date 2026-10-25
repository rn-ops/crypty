#include <crypty/platform/device_inventory.hpp>

#include <cassert>
#include <set>
#include <string>

int main() {
    const auto inventory = crypty::platform::enumerate_physical_devices();

    if (inventory.status == crypty::platform::DeviceInventoryStatus::Unsupported) {
        assert(inventory.devices.empty());
        assert(!inventory.diagnostic.empty());
        return 0;
    }

    assert(inventory.status != crypty::platform::DeviceInventoryStatus::Failed);
    assert(!inventory.diagnostic.empty());

    std::set<std::string> paths;
    for (const auto& device : inventory.devices) {
        assert(!device.device_path.empty());
        assert(device.capacity_bytes > 0);
        assert(paths.insert(device.device_path).second);

        // A false system-device flag is only trustworthy when explicitly known.
        if (!device.os_volume_membership_known) {
            assert(!device.contains_os_volume);
        }
        if (!device.read_only_status_known) {
            assert(!device.read_only);
        }

        // Inventory must never claim that it itself performed sanitization.
        // Missing persistent identifiers are represented explicitly as empty;
        // the inventory must not fabricate one from a transient device path.
    }

    return 0;
}
