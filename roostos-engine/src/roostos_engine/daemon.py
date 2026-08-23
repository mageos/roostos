"""Backwards-compatibility module re-exporting from roostos_engine.daemon."""

from roostos_engine.daemon import (
    RoostDaemonInterface,
    BUS_NAME,
    OBJECT_PATH,
    BackupHandler,
    UPnPHandler,
    AllowanceTracker,
    extract_plugin_ui,
    start_daemon,
    main,
)

if __name__ == "__main__":
    main()
