#!/usr/bin/env python3
"""
Diagnose "Compass did not respond to the ping" (C-ECHO) failures.

Run this on the computer that will send DICOM to Compass (the one with network
access). Do not run on a machine that is blocked from the Compass network.

Usage:
    python diagnose_ping.py

Uses COMPASS_HOST, COMPASS_PORT, COMPASS_AE_TITLE, LOCAL_AE_TITLE from .env.
"""

import socket
import sys
from pathlib import Path

# Load .env from project root
project_root = Path(__file__).resolve().parent
dotenv_path = project_root / ".env"
if dotenv_path.exists():
    from dotenv import load_dotenv
    load_dotenv(dotenv_path)

from config import DicomEndpointConfig


def tcp_reachable(host: str, port: int, timeout: float = 5.0) -> bool:
    """Check if host:port accepts TCP connections."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, socket.error, OSError):
        return False


def main() -> int:
    cfg = DicomEndpointConfig.from_env()
    print("Configuration (from .env):")
    print(f"  COMPASS_HOST       = {cfg.host}")
    print(f"  COMPASS_PORT       = {cfg.port}")
    print(f"  COMPASS_AE_TITLE   = {cfg.remote_ae_title}")
    print(f"  LOCAL_AE_TITLE     = {cfg.local_ae_title}")
    print()

    # Step 1: TCP reachability
    print("Step 1: TCP connectivity to {}:{}...".format(cfg.host, cfg.port))
    if not tcp_reachable(cfg.host, cfg.port):
        print("  FAILED: Cannot open TCP connection.")
        print("  Possible causes:")
        print("    - Compass DICOM service not running on this host/port")
        print("    - Firewall blocking the port")
        print("    - Wrong COMPASS_HOST or COMPASS_PORT")
        print("    - VPN or network path down")
        print("  Try: telnet {} {}  (or nc -zv {} {})".format(cfg.host, cfg.port, cfg.host, cfg.port))
        return 1
    print("  OK: TCP connection succeeded.")
    print()

    # Step 2: DICOM C-ECHO
    print("Step 2: DICOM C-ECHO (ping)...")
    try:
        from pynetdicom import AE
        from pynetdicom.sop_class import Verification
    except ImportError:
        print("  FAILED: pynetdicom not installed. Run: pip install pynetdicom")
        return 1

    ae = AE(ae_title=cfg.local_ae_title.encode("ascii", "ignore"))
    ae.add_requested_context(Verification)
    try:
        assoc = ae.associate(
            cfg.host,
            cfg.port,
            ae_title=cfg.remote_ae_title.encode("ascii", "ignore"),
        )
        if not assoc.is_established:
            print("  FAILED: Association not established.")
            if getattr(assoc, "is_rejected", False):
                print("  Reason: Association was rejected (A-ASSOCIATE-RJ).")
                print("  Common cause: COMPASS_AE_TITLE does not match the server's configured Called AE Title.")
            elif getattr(assoc, "is_aborted", False):
                print("  Reason: Association was aborted.")
            else:
                print("  Reason: Unknown (server may have closed or timed out).")
            print("  Check COMPASS_AE_TITLE matches the Compass DICOM AE Title (e.g. COMPASS, LB-HTM-GI).")
            return 1
        status = assoc.send_c_echo()
        assoc.release()
        if status and status.Status == 0x0000:
            print("  OK: C-ECHO succeeded.")
            return 0
        print("  FAILED: C-ECHO returned non-success status: {}".format(getattr(status, "Status", status)))
        return 1
    except Exception as e:
        print("  FAILED: Exception during C-ECHO: {}".format(e))
        return 1
    finally:
        ae.shutdown()


if __name__ == "__main__":
    sys.exit(main())
