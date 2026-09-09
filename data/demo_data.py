DEMO_DEVICES = [
    {
        "id": "ssd-001",
        "name": "Samsung Portable SSD",
        "capacity": "1 TB",
        "interface": "USB 3.2",
        "media_type": "SSD",
        "filesystem": "NTFS",
        "health": "Good",
        "mount": "/E:",
        "path": ".",
        "status": "CONNECTED",
        "type": "Solid State Drive",
    },
    {
        "id": "hdd-002",
        "name": "WD Blue",
        "capacity": "1 TB",
        "interface": "SATA",
        "media_type": "HDD",
        "filesystem": "NTFS",
        "health": "Stable",
        "mount": "/D:",
        "path": ".",
        "status": "CONNECTED",
        "type": "Hard Disk Drive",
    },
    {
        "id": "usb-003",
        "name": "Kingston DataTraveler",
        "capacity": "64 GB",
        "interface": "USB",
        "media_type": "REMOVABLE",
        "filesystem": "FAT32",
        "health": "Good",
        "mount": "/F:",
        "path": ".",
        "status": "CONNECTED",
        "type": "Removable Drive",
    },
]

RECOVERY_RESULTS = [
    {
        "file": "photo_001.jpg",
        "type": "JPEG",
        "size": "3.2 MB",
        "method": "Carving",
        "confidence": 96,
        "status": "Valid",
    },
    {
        "file": "document_14.pdf",
        "type": "PDF",
        "size": "842 KB",
        "method": "Filesystem",
        "confidence": 99,
        "status": "Valid",
    },
    {
        "file": "video_03.mp4",
        "type": "MP4",
        "size": "184 MB",
        "method": "Reconstruction",
        "confidence": 78,
        "status": "Review",
    },
    {
        "file": "archive_07.zip",
        "type": "ZIP",
        "size": "12 MB",
        "method": "Carving",
        "confidence": 64,
        "status": "Uncertain",
    },
]

AUDIT_LOG = [
    {
        "timestamp": "09:42:11",
        "operator": "Demo Investigator",
        "action": "DEVICE_ANALYSIS",
        "target": "Samsung Portable SSD",
        "status": "SUCCESS",
    },
    {
        "timestamp": "09:43:05",
        "operator": "Demo Investigator",
        "action": "RECOVERY_SCAN",
        "target": "Samsung Portable SSD",
        "status": "SUCCESS",
    },
    {
        "timestamp": "09:44:31",
        "operator": "Demo Investigator",
        "action": "FILE_VALIDATION",
        "target": "127 objects",
        "status": "SUCCESS",
    },
    {
        "timestamp": "09:51:18",
        "operator": "Demo Investigator",
        "action": "SANITIZATION_REQUEST",
        "target": "Samsung Portable SSD",
        "status": "DEMO ONLY",
    },
    {
        "timestamp": "09:51:23",
        "operator": "Demo Investigator",
        "action": "SANITIZATION_VERIFICATION",
        "target": "Samsung Portable SSD",
        "status": "PASSED",
    },
]

RECENT_OPERATIONS = [
    {"time": "09:42", "operation": "Device Analysis", "device": "Portable SSD", "status": "COMPLETE"},
    {"time": "09:37", "operation": "Recovery Scan", "device": "Evidence Image", "status": "COMPLETE"},
    {"time": "09:18", "operation": "File Verification", "device": "Evidence Image", "status": "COMPLETE"},
]

REPORT_SUMMARY = {
    "case_id": "CRYPTY-DEMO-001",
    "operator": "Demo Investigator",
    "device": "Samsung Portable SSD",
    "operation": "Recovery Analysis",
    "start_time": "09:37",
    "status": "Completed",
    "files_identified": 127,
    "high_confidence": 94,
    "integrity": "SHA-256 records generated",
    "audit_events": 12,
}
