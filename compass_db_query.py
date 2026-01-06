"""
Compass Database Query Module

This module provides functions to query the Compass ODM database for DICOM job information.
Requires database credentials and pyodbc (for SQL Server) or appropriate driver.

Usage:
    1. Set environment variables in .env file or export them
    2. Import and use query functions
    3. Or use the REST API wrapper if available

Author: DICOM Automation Team
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).resolve().parent
dotenv_path = project_root / ".env"

if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CompassDatabaseConfig:
    """Configuration for Compass database connection."""
    server: str
    database: str
    port: int = 1433
    username: Optional[str] = None
    password: Optional[str] = None
    use_windows_auth: bool = False
    driver: str = "ODBC Driver 17 for SQL Server"
    
    @classmethod
    def from_env(cls) -> "CompassDatabaseConfig":
        """Load database configuration from environment variables."""
        return cls(
            server=os.getenv("COMPASS_DB_SERVER", "ROCFDN019Q"),
            database=os.getenv("COMPASS_DB_NAME", "ODM"),
            port=int(os.getenv("COMPASS_DB_PORT", "1433")),
            username=os.getenv("COMPASS_DB_USER"),
            password=os.getenv("COMPASS_DB_PASSWORD"),
            use_windows_auth=os.getenv("COMPASS_DB_WINDOWS_AUTH", "false").lower() == "true",
            driver=os.getenv("COMPASS_DB_DRIVER", "ODBC Driver 17 for SQL Server"),
        )


class CompassDatabaseClient:
    """Client for querying Compass database."""
    
    def __init__(self, config: CompassDatabaseConfig):
        self.config = config
        self.connection = None
        
    def connect(self):
        """Establish database connection."""
        try:
            import pyodbc
        except ImportError:
            raise ImportError(
                "pyodbc is required for SQL Server connections. "
                "Install it with: pip install pyodbc"
            )
        
        # Build connection string
        if self.config.use_windows_auth:
            conn_str = (
                f"DRIVER={{{self.config.driver}}};"
                f"SERVER={self.config.server},{self.config.port};"
                f"DATABASE={self.config.database};"
                f"Trusted_Connection=yes;"
            )
        else:
            if not self.config.username or not self.config.password:
                raise ValueError("Username and password required for SQL authentication")
            conn_str = (
                f"DRIVER={{{self.config.driver}}};"
                f"SERVER={self.config.server},{self.config.port};"
                f"DATABASE={self.config.database};"
                f"UID={self.config.username};"
                f"PWD={self.config.password};"
            )
        
        logger.info(f"Connecting to database {self.config.database} on {self.config.server}...")
        self.connection = pyodbc.connect(conn_str, timeout=10)
        logger.info("Database connection established")
        
    def disconnect(self):
        """Close database connection."""
        if self.connection:
            self.connection.close()
            logger.info("Database connection closed")
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def execute_query(self, query: str, params: Optional[tuple] = None) -> List[Dict[str, Any]]:
        """
        Execute a SQL query and return results as list of dictionaries.
        
        Args:
            query: SQL query string
            params: Optional tuple of parameters for parameterized queries
            
        Returns:
            List of dictionaries, one per row
        """
        if not self.connection:
            raise RuntimeError("Not connected to database. Call connect() first or use context manager.")
        
        cursor = self.connection.cursor()
        
        try:
            if params:
                cursor.execute(query, params)
            else:
                cursor.execute(query)
            
            # Get column names
            columns = [column[0] for column in cursor.description]
            
            # Fetch all rows and convert to dictionaries
            results = []
            for row in cursor.fetchall():
                results.append(dict(zip(columns, row)))
            
            return results
            
        finally:
            cursor.close()
    
    # ========================================================================
    # Example Query Methods (Update table/column names based on actual schema)
    # ========================================================================
    
    def get_jobs(
        self, 
        limit: int = 100,
        patient_id: Optional[str] = None,
        study_uid: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """
        Get jobs from Compass database.
        
        NOTE: Table and column names are EXAMPLES - update based on actual schema.
        
        Args:
            limit: Maximum number of jobs to return
            patient_id: Filter by patient ID
            study_uid: Filter by study instance UID
            start_date: Filter jobs after this date
            end_date: Filter jobs before this date
            
        Returns:
            List of job dictionaries
        """
        # EXAMPLE QUERY - Update table/column names based on actual schema
        query = """
        SELECT TOP (?)
            JobID,
            StudyInstanceUID,
            PatientID,
            PatientName,
            AccessionNumber,
            Modality,
            StudyDate,
            CallingAET,
            DestinationAET,
            Status,
            CreatedAt,
            CompletedAt,
            ImageCount
        FROM Jobs
        WHERE 1=1
        """
        
        params = [limit]
        
        if patient_id:
            query += " AND PatientID = ?"
            params.append(patient_id)
        
        if study_uid:
            query += " AND StudyInstanceUID = ?"
            params.append(study_uid)
        
        if start_date:
            query += " AND CreatedAt >= ?"
            params.append(start_date)
        
        if end_date:
            query += " AND CreatedAt <= ?"
            params.append(end_date)
        
        query += " ORDER BY CreatedAt DESC"
        
        return self.execute_query(query, tuple(params))
    
    def get_dicom_tags(self, job_id: int) -> List[Dict[str, Any]]:
        """
        Get DICOM tags for a specific job.
        
        NOTE: Table and column names are EXAMPLES - update based on actual schema.
        
        Args:
            job_id: Job ID to get tags for
            
        Returns:
            List of DICOM tag dictionaries
        """
        # EXAMPLE QUERY - Update based on actual schema
        query = """
        SELECT
            TagGroup,
            TagElement,
            TagName,
            VR,
            Value
        FROM DicomTags
        WHERE JobID = ?
        ORDER BY TagGroup, TagElement
        """
        
        return self.execute_query(query, (job_id,))
    
    def get_job_by_study_uid(self, study_uid: str, include_tags: bool = True) -> Optional[Dict[str, Any]]:
        """
        Get job information by Study Instance UID with all DICOM tags.
        
        Args:
            study_uid: Study Instance UID to search for
            include_tags: If True, includes all DICOM tags in response (default: True)
            
        Returns:
            Dictionary with job info and DICOM tags, or None if not found
        """
        # First, get the job record
        query = """
        SELECT TOP 1
            JobID,
            StudyInstanceUID,
            PatientID,
            PatientName,
            AccessionNumber,
            Modality,
            StudyDate,
            CallingAET,
            DestinationAET,
            Status,
            CreatedAt,
            CompletedAt,
            ImageCount
        FROM Jobs
        WHERE StudyInstanceUID = ?
        """
        
        results = self.execute_query(query, (study_uid,))
        if not results:
            return None
        
        job = results[0]
        
        # If include_tags is True, fetch DICOM tags and merge them into the result
        if include_tags:
            job_id = job.get('JobID')
            if job_id:
                tags = self.get_dicom_tags(job_id)
                # Convert tags list to dict with TagName as key and Value as value
                for tag in tags:
                    tag_name = tag.get('TagName')
                    tag_value = tag.get('Value')
                    if tag_name:
                        job[tag_name] = tag_value
        
        return job
    
    def test_connection(self) -> bool:
        """
        Test database connection and return True if successful.
        
        Returns:
            True if connection test successful, False otherwise
        """
        try:
            result = self.execute_query("SELECT @@VERSION as Version")
            if result:
                logger.info(f"Database version: {result[0]['Version'][:100]}...")
                return True
            return False
        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def discover_tables(self) -> List[str]:
        """
        Discover all tables in the database.
        
        Returns:
            List of table names
        """
        query = """
        SELECT TABLE_NAME 
        FROM INFORMATION_SCHEMA.TABLES 
        WHERE TABLE_TYPE = 'BASE TABLE'
        ORDER BY TABLE_NAME
        """
        results = self.execute_query(query)
        return [row['TABLE_NAME'] for row in results]
    
    def get_table_schema(self, table_name: str) -> List[Dict[str, Any]]:
        """
        Get schema information for a specific table.
        
        Args:
            table_name: Name of the table
            
        Returns:
            List of column information dictionaries
        """
        query = """
        SELECT 
            COLUMN_NAME,
            DATA_TYPE,
            CHARACTER_MAXIMUM_LENGTH,
            IS_NULLABLE,
            COLUMN_DEFAULT
        FROM INFORMATION_SCHEMA.COLUMNS
        WHERE TABLE_NAME = ?
        ORDER BY ORDINAL_POSITION
        """
        return self.execute_query(query, (table_name,))


# ============================================================================
# Example Usage
# ============================================================================

def main():
    """Example usage of the Compass database client."""
    
    # Load configuration from environment variables
    config = CompassDatabaseConfig.from_env()
    
    # Use context manager for automatic connection handling
    try:
        with CompassDatabaseClient(config) as client:
            # Test connection
            logger.info("Testing database connection...")
            if not client.test_connection():
                logger.error("Connection test failed")
                return
            
            # Discover tables
            logger.info("\nDiscovering tables...")
            tables = client.discover_tables()
            logger.info(f"Found {len(tables)} tables:")
            for table in tables[:10]:  # Show first 10
                logger.info(f"  - {table}")
            
            # Get table schema (update table name based on discovery)
            if tables:
                logger.info(f"\nGetting schema for table: {tables[0]}")
                schema = client.get_table_schema(tables[0])
                for col in schema[:5]:  # Show first 5 columns
                    logger.info(f"  - {col['COLUMN_NAME']} ({col['DATA_TYPE']})")
            
            # Example: Get recent jobs
            logger.info("\nGetting recent jobs...")
            jobs = client.get_jobs(limit=10)
            logger.info(f"Found {len(jobs)} jobs")
            for job in jobs[:3]:  # Show first 3
                logger.info(f"  Job: {job}")
            
    except ImportError as e:
        logger.error(str(e))
        logger.info("\nTo install pyodbc:")
        logger.info("  pip install pyodbc")
        
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.info("\nMake sure to set environment variables:")
        logger.info("  COMPASS_DB_SERVER")
        logger.info("  COMPASS_DB_NAME")
        logger.info("  COMPASS_DB_USER (if not using Windows auth)")
        logger.info("  COMPASS_DB_PASSWORD (if not using Windows auth)")
        logger.info("  COMPASS_DB_WINDOWS_AUTH=true (for Windows authentication)")


if __name__ == "__main__":
    main()

