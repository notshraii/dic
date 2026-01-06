"""
Example script to test Compass connectivity and discovery.

This script will help you:
1. Test C-FIND (DICOM Query) connection - RECOMMENDED
2. Test API connection (if available)
3. Test database connection (fallback)
4. Discover schema and endpoints

Usage:
    # Test all methods
    python test_compass_connection.py --mode all
    
    # Test specific method
    python test_compass_connection.py --mode cfind
    python test_compass_connection.py --mode api
    python test_compass_connection.py --mode database
    
    # Show discovery instructions
    python test_compass_connection.py --mode discover
"""

import argparse
import sys
import logging
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).resolve().parent
dotenv_path = project_root / ".env"

if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_cfind_connection():
    """Test C-FIND (DICOM Query) connection."""
    try:
        from compass_cfind_client import CompassCFindConfig, CompassCFindClient
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        logger.error("Make sure compass_cfind_client.py is in the same directory")
        return False
    
    try:
        logger.info("Loading C-FIND configuration from environment...")
        config = CompassCFindConfig.from_env()
        logger.info(f"Host: {config.host}")
        logger.info(f"Port: {config.port}")
        logger.info(f"Called AE: {config.remote_ae_title}")
        logger.info(f"Calling AE: {config.local_ae_title}")
        
        client = CompassCFindClient(config)
        
        # Test connection
        logger.info("\nTesting C-FIND connection...")
        if not client.test_connection():
            logger.error("Connection test failed!")
            return False
        
        logger.info("Connection successful!")
        
        # Try to query today's studies
        from datetime import datetime
        today = datetime.now().strftime("%Y%m%d")
        logger.info(f"\nQuerying studies from today ({today})...")
        
        studies = client.find_studies_by_date_range(today)
        logger.info(f"Found {len(studies)} studies today")
        
        if studies:
            logger.info("\nFirst study:")
            study_dict = client.dataset_to_dict(studies[0])
            for key, value in list(study_dict.items())[:10]:  # Show first 10 fields
                logger.info(f"  {key}: {value}")
        
        return True
        
    except ConnectionError as e:
        logger.error(f"\nConnection failed: {e}")
        logger.error("\nPossible issues:")
        logger.error("1. Host/port incorrect")
        logger.error("2. Compass not responding to C-FIND queries")
        logger.error("3. AE Title mismatch")
        logger.error("4. Network/firewall blocking connection")
        logger.error("\nCheck environment variables:")
        logger.error("  COMPASS_HOST (default: roelbc200a.mayo.edu)")
        logger.error("  COMPASS_PORT (default: 11112)")
        logger.error("  COMPASS_AE_TITLE (default: COMPASS)")
        logger.error("  LOCAL_AE_TITLE (default: QUERY_SCU)")
        return False
        
    except Exception as e:
        logger.error(f"\nError: {e}")
        logger.error("\nMake sure pynetdicom is installed:")
        logger.error("  pip install pynetdicom")
        return False


def test_database_connection():
    """Test database connection and discover schema."""
    try:
        from compass_db_query import CompassDatabaseConfig, CompassDatabaseClient
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        logger.error("Make sure compass_db_query.py is in the same directory")
        return False
    
    try:
        logger.info("Loading database configuration from environment...")
        config = CompassDatabaseConfig.from_env()
        logger.info(f"Server: {config.server}")
        logger.info(f"Database: {config.database}")
        logger.info(f"Port: {config.port}")
        logger.info(f"Windows Auth: {config.use_windows_auth}")
        
        with CompassDatabaseClient(config) as client:
            # Test connection
            logger.info("\nTesting connection...")
            if not client.test_connection():
                logger.error("Connection test failed!")
                return False
            
            logger.info("Connection successful!")
            
            # Discover tables
            logger.info("\nDiscovering tables...")
            tables = client.discover_tables()
            logger.info(f"\nFound {len(tables)} tables in database:")
            for i, table in enumerate(tables, 1):
                logger.info(f"  {i}. {table}")
            
            # Get schema for interesting tables
            interesting_keywords = ['job', 'study', 'series', 'instance', 'image', 'dicom', 'tag']
            interesting_tables = [
                t for t in tables 
                if any(keyword in t.lower() for keyword in interesting_keywords)
            ]
            
            if interesting_tables:
                logger.info(f"\nInteresting tables (likely DICOM-related):")
                for table in interesting_tables[:5]:  # Show first 5
                    logger.info(f"\n  Table: {table}")
                    schema = client.get_table_schema(table)
                    for col in schema[:10]:  # Show first 10 columns
                        nullable = "NULL" if col['IS_NULLABLE'] == 'YES' else "NOT NULL"
                        logger.info(f"    - {col['COLUMN_NAME']}: {col['DATA_TYPE']} {nullable}")
            
            return True
            
    except ImportError as e:
        logger.error(f"\nMissing dependency: {e}")
        logger.error("\nTo install required packages:")
        logger.error("  pip install pyodbc")
        return False
        
    except Exception as e:
        logger.error(f"\nError: {e}")
        logger.error("\nMake sure to set environment variables:")
        logger.error("  COMPASS_DB_SERVER (default: ROCFDN019Q)")
        logger.error("  COMPASS_DB_NAME (default: ODM)")
        logger.error("  COMPASS_DB_PORT (default: 1433)")
        logger.error("\nFor SQL Server authentication:")
        logger.error("  COMPASS_DB_USER=your_username")
        logger.error("  COMPASS_DB_PASSWORD=your_password")
        logger.error("\nFor Windows authentication:")
        logger.error("  COMPASS_DB_WINDOWS_AUTH=true")
        return False


def test_api_connection():
    """Test API connection and discover endpoints."""
    try:
        from compass_api_client import CompassAPIConfig, CompassAPIClient
    except ImportError as e:
        logger.error(f"Import failed: {e}")
        logger.error("Make sure compass_api_client.py is in the same directory")
        return False
    
    try:
        logger.info("Loading API configuration from environment...")
        config = CompassAPIConfig.from_env()
        logger.info(f"Base URL: {config.base_url}")
        
        client = CompassAPIClient(config)
        
        # Try to discover API
        logger.info("\nAttempting to discover API endpoints...")
        api_info = client.discover_endpoints()
        
        if "error" not in api_info:
            logger.info("API discovered successfully!")
            logger.info(f"API Info: {api_info}")
        else:
            logger.warning("Could not auto-discover API")
        
        # Test connection
        logger.info("\nTesting API connection...")
        if client.test_connection():
            logger.info("API connection successful!")
            
            # Try to get jobs
            logger.info("\nAttempting to retrieve jobs...")
            jobs = client.get_jobs(limit=5)
            logger.info(f"Retrieved {len(jobs)} jobs")
            
            if jobs:
                logger.info("\nFirst job:")
                for key, value in list(jobs[0].items())[:10]:  # Show first 10 fields
                    logger.info(f"  {key}: {value}")
            
            return True
        else:
            logger.warning("API connection failed")
            return False
            
    except Exception as e:
        logger.error(f"\nError: {e}")
        logger.error("\nAPI connection failed. This could mean:")
        logger.error("1. Authentication is required")
        logger.error("2. The API endpoint is different")
        logger.error("3. API is not available")
        logger.error("\nSet environment variables:")
        logger.error("  COMPASS_API_URL (default: http://roelbc200a.mayo.edu:10400)")
        logger.error("  COMPASS_API_USER=your_username (if needed)")
        logger.error("  COMPASS_API_PASSWORD=your_password (if needed)")
        logger.error("  COMPASS_API_KEY=your_api_key (if using API key)")
        return False


def print_discovery_instructions():
    """Print instructions for discovering API using browser."""
    from compass_api_client import CompassWebInspector
    
    inspector = CompassWebInspector()
    print(inspector.inspect_browser_network())
    
    print("\n" + "="*80)
    print("QUICK START GUIDE")
    print("="*80)
    print("\n1. ACCESS THE WEB INTERFACE:")
    print("   http://roelbc200a.mayo.edu:10400/#/app/dicom/jobs")
    
    print("\n2. OPEN DEVELOPER TOOLS:")
    print("   - Press F12 (or Cmd+Option+I on Mac)")
    print("   - Click on the 'Network' tab")
    
    print("\n3. RELOAD THE PAGE:")
    print("   - Press Ctrl+R (or Cmd+R on Mac)")
    print("   - Watch the Network tab for API calls")
    
    print("\n4. LOOK FOR:")
    print("   - XHR/Fetch requests")
    print("   - Endpoints containing 'api', 'jobs', 'studies', etc.")
    print("   - JSON responses")
    
    print("\n5. DOCUMENT:")
    print("   - Full URL of API endpoints")
    print("   - Authentication headers (if any)")
    print("   - Request parameters")
    print("   - Response structure")
    
    print("\n6. ALTERNATIVE: DIRECT DATABASE ACCESS")
    print("   If no API is available or accessible, you can:")
    print("   - Request database credentials from your DBA")
    print("   - Use the database client (compass_db_query.py)")
    print("   - Query the ODM database directly")
    
    print("\n7. CONTACT:")
    print("   - Compass/Laurel Bridge administrator")
    print("   - Database administrator")
    print("   - Ask for:")
    print("     * API documentation or REST API access")
    print("     * Database read-only credentials")
    print("     * Schema documentation")
    
    print("\n" + "="*80)
    print()


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Test Compass connectivity and discover query methods",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test C-FIND (DICOM Query) - RECOMMENDED
  python test_compass_connection.py --mode cfind
  
  # Test API connection
  python test_compass_connection.py --mode api
  
  # Test database connection
  python test_compass_connection.py --mode database
  
  # Show discovery instructions
  python test_compass_connection.py --mode discover
  
  # Test all methods
  python test_compass_connection.py --mode all

Environment Variables:
  C-FIND (DICOM Query) - RECOMMENDED:
    COMPASS_HOST            Server hostname (default: roelbc200a.mayo.edu)
    COMPASS_PORT            DICOM port (default: 11112)
    COMPASS_AE_TITLE        Called AE Title (default: COMPASS)
    LOCAL_AE_TITLE          Calling AE Title (default: QUERY_SCU)
  
  API:
    COMPASS_API_URL         Base URL (default: http://roelbc200a.mayo.edu:10400)
    COMPASS_API_USER        Username (if needed)
    COMPASS_API_PASSWORD    Password (if needed)
    COMPASS_API_KEY         API key (if needed)
    
  Database (fallback):
    COMPASS_DB_SERVER       Server name (default: ROCFDN019Q)
    COMPASS_DB_NAME         Database name (default: ODM)
    COMPASS_DB_PORT         Port (default: 1433)
    COMPASS_DB_USER         Username for SQL auth
    COMPASS_DB_PASSWORD     Password for SQL auth
    COMPASS_DB_WINDOWS_AUTH Set to 'true' for Windows auth
        """
    )
    
    parser.add_argument(
        '--mode',
        choices=['cfind', 'api', 'database', 'discover', 'all'],
        default='cfind',
        help='Test mode: cfind (recommended), api, database, discover, or all'
    )
    
    args = parser.parse_args()
    
    print("="*80)
    print("COMPASS CONNECTIVITY TEST")
    print("="*80)
    print()
    
    success = False
    
    if args.mode == 'discover':
        print_discovery_instructions()
        success = True
        
    elif args.mode == 'cfind':
        success = test_cfind_connection()
        
    elif args.mode == 'api':
        success = test_api_connection()
        
    elif args.mode == 'database':
        success = test_database_connection()
        
    elif args.mode == 'all':
        print("Testing C-FIND Connection (DICOM Query - Recommended)...")
        print("-"*80)
        cfind_success = test_cfind_connection()
        
        print("\n" + "="*80)
        print("Testing API Connection...")
        print("-"*80)
        api_success = test_api_connection()
        
        print("\n" + "="*80)
        print("Testing Database Connection...")
        print("-"*80)
        db_success = test_database_connection()
        
        success = cfind_success or api_success or db_success
        
        print("\n" + "="*80)
        print("SUMMARY")
        print("-"*80)
        print(f"C-FIND:   {'SUCCESS' if cfind_success else 'FAILED'}")
        print(f"API:      {'SUCCESS' if api_success else 'FAILED'}")
        print(f"Database: {'SUCCESS' if db_success else 'FAILED'}")
        
        if cfind_success:
            print("\nRECOMMENDATION: Use C-FIND for your tests (easiest)")
        elif api_success:
            print("\nRECOMMENDATION: Use API for your tests")
        elif db_success:
            print("\nRECOMMENDATION: Use Database for your tests (fallback)")
        else:
            print("\nNo methods working. See discovery instructions:")
            print_discovery_instructions()
    
    print("\n" + "="*80)
    if success:
        print("SUCCESS: At least one connection method works!")
    else:
        print("FAILED: Could not establish connection")
        print("\nNext steps:")
        print("1. Run with --mode discover to see how to find API endpoints")
        print("2. Verify network connectivity (ping, VPN, firewall)")
        print("3. Check configuration (host, port, AE titles)")
        print("4. Contact your administrator for credentials")
    print("="*80)
    
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())

