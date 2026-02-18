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


def tcp_reachable(host: str, port: int, timeout: float = 5.0):
    """
    Try to open TCP connection to host:port.
    Returns (True, None) on success, (False, error_message) on failure.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, None
    except socket.timeout:
        return False, "Connection timed out (no response from host)"
    except ConnectionRefusedError as e:
        return False, "Connection refused (nothing listening on that port). errno={}".format(getattr(e, "errno", getattr(e, "winerror", "?")))
    except OSError as e:
        errno = getattr(e, "errno", "")
        winerror = getattr(e, "winerror", "")
        parts = [str(e)] if str(e) else []
        if errno is not None and errno != "":
            parts.append("errno={}".format(errno))
        if winerror is not None and winerror != "":
            parts.append("winerror={}".format(winerror))
        return False, " ".join(parts) or type(e).__name__
    except (socket.error, Exception) as e:
        return False, str(e) or "{}".format(type(e).__name__)


def main() -> int:
    cfg = DicomEndpointConfig.from_env()
    print("diagnose_ping.py (run from project root so .env is used)")
    print("Configuration (from .env):")
    print(f"  COMPASS_HOST       = {cfg.host}")
    print(f"  COMPASS_PORT       = {cfg.port}")
    print(f"  COMPASS_AE_TITLE   = {cfg.remote_ae_title}")
    print(f"  LOCAL_AE_TITLE     = {cfg.local_ae_title}")
    print()

    # Step 1: TCP reachability
    print("Step 1: TCP connectivity to {}:{}...".format(cfg.host, cfg.port))
    ok, err = tcp_reachable(cfg.host, cfg.port)
    if not ok:
        print("  FAILED: Cannot open TCP connection.")
        print("  Detail: {}".format(err or "Unknown"))
        print("  (If Detail is empty, pull latest diagnose_ping.py from the repo.)")
        print("  Possible causes:")
        print("    - Compass DICOM service not running on this host/port")
        print("    - Firewall blocking the port (Windows Firewall, corporate, or server-side)")
        print("    - Wrong COMPASS_HOST or COMPASS_PORT in .env")
        print("    - VPN required but not connected (or wrong network)")
        print("  On Windows (PowerShell): Test-NetConnection -ComputerName {} -Port {}".format(cfg.host, cfg.port))
        print("  If that also fails: check VPN, .env host/port, and ask admin to confirm Compass is listening and firewall allows you.")
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
