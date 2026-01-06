#!/usr/bin/env python3
"""
Quick script to check what ODBC drivers are available on your system.

Usage:
    python check_odbc_drivers.py

Author: DICOM Automation Team
"""

def check_drivers():
    """Check and display available ODBC drivers."""
    print("=" * 80)
    print("ODBC DRIVER CHECK")
    print("=" * 80)
    
    try:
        import pyodbc
    except ImportError:
        print("\nERROR: pyodbc is not installed")
        print("\nInstall with:")
        print("  pip install pyodbc")
        return False
    
    print("\n[AVAILABLE ODBC DRIVERS]")
    print("-" * 80)
    
    available_drivers = pyodbc.drivers()
    
    if not available_drivers:
        print("No ODBC drivers found on this system!\n")
        print_install_instructions()
        return False
    
    print(f"Found {len(available_drivers)} ODBC driver(s):\n")
    
    sql_server_drivers = []
    other_drivers = []
    
    for driver in available_drivers:
        if "SQL Server" in driver or "ODBC Driver" in driver:
            sql_server_drivers.append(driver)
        else:
            other_drivers.append(driver)
    
    if sql_server_drivers:
        print("SQL Server Compatible Drivers:")
        for driver in sql_server_drivers:
            print(f"  ✓ {driver}")
        print()
    
    if other_drivers:
        print("Other Drivers:")
        for driver in other_drivers:
            print(f"  - {driver}")
        print()
    
    if not sql_server_drivers:
        print("WARNING: No SQL Server drivers found!")
        print_install_instructions()
        return False
    
    print("-" * 80)
    print(f"✓ You have SQL Server driver(s) installed!")
    print(f"\nRecommended driver: {sql_server_drivers[0]}")
    print("\nThe code will auto-detect and use this driver.")
    print("You don't need to set COMPASS_DB_DRIVER in your .env file.")
    return True


def print_install_instructions():
    """Print installation instructions for SQL Server ODBC driver."""
    print("\n" + "=" * 80)
    print("HOW TO INSTALL SQL SERVER ODBC DRIVER")
    print("=" * 80)
    
    print("\n[macOS]")
    print("-" * 80)
    print("Using Homebrew:")
    print("  brew tap microsoft/mssql-release https://github.com/Microsoft/homebrew-mssql-release")
    print("  brew update")
    print("  brew install msodbcsql18")
    print("\nOr for older version:")
    print("  brew install msodbcsql17")
    
    print("\n[Windows]")
    print("-" * 80)
    print("Download and install from Microsoft:")
    print("  https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server")
    print("\nChoose:")
    print("  - ODBC Driver 18 for SQL Server (recommended)")
    print("  - Or ODBC Driver 17 for SQL Server")
    
    print("\n[Linux (Ubuntu/Debian)]")
    print("-" * 80)
    print("Run these commands:")
    print("  curl https://packages.microsoft.com/keys/microsoft.asc | sudo apt-key add -")
    print("  curl https://packages.microsoft.com/config/ubuntu/$(lsb_release -rs)/prod.list \\")
    print("    | sudo tee /etc/apt/sources.list.d/mssql-release.list")
    print("  sudo apt-get update")
    print("  sudo ACCEPT_EULA=Y apt-get install -y msodbcsql18")
    
    print("\n[Linux (RHEL/CentOS)]")
    print("-" * 80)
    print("Run these commands:")
    print("  sudo curl https://packages.microsoft.com/config/rhel/8/prod.repo \\")
    print("    | sudo tee /etc/yum.repos.d/mssql-release.repo")
    print("  sudo yum remove unixODBC-utf16 unixODBC-utf16-devel")
    print("  sudo ACCEPT_EULA=Y yum install -y msodbcsql18")
    
    print("\n" + "=" * 80)
    print("\nAfter installation, run this script again to verify.")


if __name__ == "__main__":
    import sys
    success = check_drivers()
    sys.exit(0 if success else 1)

