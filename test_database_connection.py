#!/usr/bin/env python3
"""
Test Database Connection Script

Verifies that database credentials work and discovers the actual table/column schema.
Run this FIRST before running tests.

Usage:
    python test_database_connection.py
    
Expected Output:
    - Database version
    - List of tables
    - Schema for relevant tables
    - Sample query results

Author: DICOM Automation Team
"""

import sys
from pathlib import Path
from dotenv import load_dotenv

# Load .env file
project_root = Path(__file__).resolve().parent
dotenv_path = project_root / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
    print(f"Loaded .env from: {dotenv_path}\n")
else:
    print(f"WARNING: .env file not found at {dotenv_path}")
    print("Using environment variables or defaults\n")

from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig


def test_connection():
    """Test basic database connectivity."""
    print("=" * 80)
    print("COMPASS DATABASE CONNECTION TEST")
    print("=" * 80)
    
    # First, check available ODBC drivers
    print("\n[ODBC DRIVERS CHECK]")
    print("-" * 80)
    try:
        import pyodbc
        available_drivers = pyodbc.drivers()
        if available_drivers:
            print(f"Found {len(available_drivers)} ODBC driver(s):\n")
            for i, driver in enumerate(available_drivers, 1):
                # Highlight SQL Server drivers
                if "SQL Server" in driver or "ODBC Driver" in driver:
                    print(f"  {i:2d}. {driver} ← SQL Server driver")
                else:
                    print(f"  {i:2d}. {driver}")
        else:
            print("WARNING: No ODBC drivers found!")
            print("\nTo install SQL Server ODBC driver:")
            print("  macOS:   brew install msodbcsql18")
            print("  Windows: Download from https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server")
            print("  Linux:   See https://learn.microsoft.com/en-us/sql/connect/odbc/linux-mac/installing-the-microsoft-odbc-driver-for-sql-server")
            return False
    except ImportError:
        print("ERROR: pyodbc is not installed")
        print("\nInstall with: pip install pyodbc")
        return False
    
    # Load config
    config = CompassDatabaseConfig.from_env()
    print(f"\n\n[CONFIGURATION]")
    print("-" * 80)
    print(f"  Server: {config.server}")
    print(f"  Database: {config.database}")
    print(f"  Port: {config.port}")
    print(f"  Configured Driver: {config.driver}")
    print(f"  Windows Auth: {config.use_windows_auth}")
    if not config.use_windows_auth:
        print(f"  Username: {config.username}")
        print(f"  Password: {'*' * len(config.password) if config.password else 'NOT SET'}")
    print()
    
    try:
        with CompassDatabaseClient(config) as client:
            # Test 1: Connection
            print("\n[TEST 1: Connection]")
            print("-" * 80)
            if client.test_connection():
                print("SUCCESS: Database connection established!")
            else:
                print("FAILED: Could not connect to database")
                return False
            
            # Test 2: Discover tables
            print("\n[TEST 2: Discover Tables]")
            print("-" * 80)
            tables = client.discover_tables()
            print(f"Found {len(tables)} tables:\n")
            for i, table in enumerate(tables, 1):
                print(f"  {i:2d}. {table}")
            
            # Test 3: Get schema for Jobs table
            print("\n[TEST 3: Jobs Table Schema]")
            print("-" * 80)
            if "Jobs" in tables:
                schema = client.get_table_schema("Jobs")
                print(f"Jobs table has {len(schema)} columns:\n")
                for col in schema:
                    nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
                    max_len = f"({col['CHARACTER_MAXIMUM_LENGTH']})" if col['CHARACTER_MAXIMUM_LENGTH'] else ""
                    print(f"  {col['COLUMN_NAME']:30s} {col['DATA_TYPE']:15s}{max_len:10s} {nullable}")
            else:
                print("WARNING: 'Jobs' table not found. Actual table name may be different.")
                print("Available tables:", tables[:5])
            
            # Test 4: Get schema for DicomTags table
            print("\n[TEST 4: DicomTags Table Schema]")
            print("-" * 80)
            if "DicomTags" in tables:
                schema = client.get_table_schema("DicomTags")
                print(f"DicomTags table has {len(schema)} columns:\n")
                for col in schema:
                    nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
                    max_len = f"({col['CHARACTER_MAXIMUM_LENGTH']})" if col['CHARACTER_MAXIMUM_LENGTH'] else ""
                    print(f"  {col['COLUMN_NAME']:30s} {col['DATA_TYPE']:15s}{max_len:10s} {nullable}")
            else:
                print("WARNING: 'DicomTags' table not found. Actual table name may be different.")
            
            # Test 5: Get recent jobs
            print("\n[TEST 5: Recent Jobs Query]")
            print("-" * 80)
            try:
                jobs = client.get_jobs(limit=5)
                print(f"Found {len(jobs)} recent jobs:\n")
                for i, job in enumerate(jobs, 1):
                    print(f"  Job {i}:")
                    print(f"    Study UID: {job.get('StudyInstanceUID', 'N/A')}")
                    print(f"    Patient ID: {job.get('PatientID', 'N/A')}")
                    print(f"    Modality: {job.get('Modality', 'N/A')}")
                    print(f"    Status: {job.get('Status', 'N/A')}")
                    print(f"    Created: {job.get('CreatedAt', 'N/A')}")
                    print()
            except Exception as e:
                print(f"WARNING: Could not query Jobs table: {e}")
                print("This is expected if table/column names are different than assumed.")
            
            print("\n" + "=" * 80)
            print("ALL TESTS COMPLETED SUCCESSFULLY!")
            print("=" * 80)
            print("\nYou can now run pytest tests with database verification.")
            print("The tests will use the same credentials from your .env file.")
            return True
            
    except ImportError as e:
        print(f"\nERROR: {e}")
        print("\nTo install pyodbc:")
        print("  pip install pyodbc")
        return False
        
    except Exception as e:
        print(f"\nERROR: {e}")
        print("\nPossible issues:")
        print("  1. Database credentials are incorrect")
        print("  2. Database server is not accessible from your network")
        print("  3. Firewall blocking connection to port 1433")
        print("  4. ODBC driver not installed")
        print("\nMake sure your .env file has correct values:")
        print("  COMPASS_DB_SERVER=ROCFDN019Q")
        print("  COMPASS_DB_NAME=ODM")
        print("  COMPASS_DB_USER=your_username")
        print("  COMPASS_DB_PASSWORD=your_password")
        return False


if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

