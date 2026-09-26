# Security and sensitive data

Do not publish or attach device-unique material to issues, pull requests, commits, or Actions artifacts unless it has been explicitly sanitized.

Sensitive examples include full SPI dumps, MAC-address allocations, RF calibration tables, Wi-Fi/admin credentials, configuration backups, HAR captures, and private serial numbers.

The Actions workflows in this repository intentionally use GitHub-hosted runners. Do not add a self-hosted runner while the repository is public.
