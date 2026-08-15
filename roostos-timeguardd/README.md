# RoostOS Screen Time Daemon

A lightweight system daemon that monitors screen time for configured users on Debian/Ubuntu client systems.

## Features
- Track session state via `systemd-logind` over D-Bus.
- Lock user session automatically when time limit is reached.
- Block login/unlock attempts using PAM configurations.
- Optional periodic syncing with a RoostOS router.
