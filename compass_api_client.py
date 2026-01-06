"""
Compass REST API Client (Alternative to Direct Database Access)

This module provides a client for the Compass web API.
This is often preferred over direct database access.

Author: DICOM Automation Team
"""

import os
from pathlib import Path
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from datetime import datetime

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
class CompassAPIConfig:
    """Configuration for Compass API connection."""
    base_url: str
    username: Optional[str] = None
    password: Optional[str] = None
    api_key: Optional[str] = None
    timeout: int = 30
    verify_ssl: bool = True
    
    @classmethod
    def from_env(cls) -> "CompassAPIConfig":
        """Load API configuration from environment variables."""
        return cls(
            base_url=os.getenv("COMPASS_API_URL", "http://roelbc200a.mayo.edu:10400"),
            username=os.getenv("COMPASS_API_USER"),
            password=os.getenv("COMPASS_API_PASSWORD"),
            api_key=os.getenv("COMPASS_API_KEY"),
            timeout=int(os.getenv("COMPASS_API_TIMEOUT", "30")),
            verify_ssl=os.getenv("COMPASS_API_VERIFY_SSL", "true").lower() == "true",
        )


class CompassAPIClient:
    """Client for querying Compass via REST API."""
    
    def __init__(self, config: CompassAPIConfig):
        self.config = config
        self.session = requests.Session()
        self.session.verify = config.verify_ssl
        
        # Set up authentication
        if config.api_key:
            self.session.headers.update({
                "Authorization": f"Bearer {config.api_key}"
            })
        elif config.username and config.password:
            self.session.auth = (config.username, config.password)
        
        logger.info(f"Compass API Client initialized for {config.base_url}")
    
    def _request(
        self, 
        method: str, 
        endpoint: str, 
        params: Optional[Dict] = None,
        json: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Make an API request.
        
        Args:
            method: HTTP method (GET, POST, etc.)
            endpoint: API endpoint (without base URL)
            params: Query parameters
            json: JSON body for POST/PUT requests
            
        Returns:
            Response JSON as dictionary
        """
        url = f"{self.config.base_url}{endpoint}"
        
        try:
            response = self.session.request(
                method=method,
                url=url,
                params=params,
                json=json,
                timeout=self.config.timeout
            )
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            raise
    
    # ========================================================================
    # API Methods (Update endpoints based on actual Compass API)
    # ========================================================================
    
    def discover_endpoints(self) -> Dict[str, Any]:
        """
        Attempt to discover available API endpoints.
        
        Try common API documentation endpoints.
        
        Returns:
            API documentation or error message
        """
        doc_endpoints = [
            "/api",
            "/api/docs",
            "/swagger",
            "/swagger.json",
            "/api/swagger.json",
            "/openapi.json",
            "/api/v1",
        ]
        
        for endpoint in doc_endpoints:
            try:
                logger.info(f"Trying {endpoint}...")
                result = self._request("GET", endpoint)
                logger.info(f"Found API documentation at {endpoint}")
                return result
            except Exception:
                continue
        
        logger.warning("Could not find API documentation endpoint")
        return {"error": "API documentation not found"}
    
    def get_jobs(
        self,
        limit: int = 100,
        offset: int = 0,
        patient_id: Optional[str] = None,
        study_uid: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get jobs from Compass API.
        
        NOTE: Endpoint and parameters are EXAMPLES - update based on actual API.
        
        Args:
            limit: Maximum number of jobs to return
            offset: Offset for pagination
            patient_id: Filter by patient ID
            study_uid: Filter by study instance UID
            start_date: Filter jobs after this date (ISO format)
            end_date: Filter jobs before this date (ISO format)
            status: Filter by job status
            
        Returns:
            List of job dictionaries
        """
        params = {
            "limit": limit,
            "offset": offset,
        }
        
        if patient_id:
            params["patientId"] = patient_id
        if study_uid:
            params["studyInstanceUid"] = study_uid
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if status:
            params["status"] = status
        
        # EXAMPLE ENDPOINT - Update based on actual API
        result = self._request("GET", "/api/dicom/jobs", params=params)
        
        # Response format depends on actual API
        if isinstance(result, list):
            return result
        elif isinstance(result, dict) and "jobs" in result:
            return result["jobs"]
        else:
            return [result]
    
    def get_job_details(self, job_id: str) -> Dict[str, Any]:
        """
        Get detailed information for a specific job.
        
        Args:
            job_id: Job ID to get details for
            
        Returns:
            Job details dictionary including DICOM tags
        """
        # EXAMPLE ENDPOINT - Update based on actual API
        return self._request("GET", f"/api/dicom/jobs/{job_id}")
    
    def get_job_by_study_uid(self, study_uid: str) -> Optional[Dict[str, Any]]:
        """
        Get job by Study Instance UID.
        
        Args:
            study_uid: Study Instance UID to search for
            
        Returns:
            Job dictionary or None if not found
        """
        results = self.get_jobs(study_uid=study_uid, limit=1)
        return results[0] if results else None
    
    def get_dicom_tags(self, job_id: str) -> Dict[str, Any]:
        """
        Get DICOM tags for a specific job.
        
        Args:
            job_id: Job ID to get tags for
            
        Returns:
            Dictionary of DICOM tags
        """
        # EXAMPLE ENDPOINT - Update based on actual API
        return self._request("GET", f"/api/dicom/jobs/{job_id}/tags")
    
    def test_connection(self) -> bool:
        """
        Test API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to get jobs with limit=1 as a connection test
            self.get_jobs(limit=1)
            logger.info("API connection test successful")
            return True
        except Exception as e:
            logger.error(f"API connection test failed: {e}")
            return False


# ============================================================================
# Web Interface Inspector
# ============================================================================

class CompassWebInspector:
    """Helper to inspect the Compass web interface for API details."""
    
    @staticmethod
    def inspect_browser_network() -> str:
        """
        Instructions for inspecting the web interface.
        
        Returns:
            Instructions as a string
        """
        return """
        To discover the actual API endpoints used by Compass web interface:
        
        1. Open the Compass web interface in your browser:
           http://roelbc200a.mayo.edu:10400/#/app/dicom/jobs
        
        2. Open Browser Developer Tools:
           - Chrome/Edge: Press F12 or Ctrl+Shift+I (Cmd+Option+I on Mac)
           - Firefox: Press F12 or Ctrl+Shift+I (Cmd+Option+I on Mac)
        
        3. Go to the "Network" tab in Developer Tools
        
        4. Refresh the page or navigate to view jobs
        
        5. Look for API calls in the Network tab:
           - Filter by "XHR" or "Fetch" to see AJAX requests
           - Look for calls to endpoints like:
             * /api/...
             * /rest/...
             * /v1/...
             * Anything returning JSON data
        
        6. Click on interesting requests to see:
           - Request URL (full endpoint path)
           - Request Method (GET, POST, etc.)
           - Query Parameters
           - Request Headers (look for authentication)
           - Response (JSON structure)
        
        7. Document the following:
           - Base API URL (e.g., http://roelbc200a.mayo.edu:10400/api)
           - Endpoints for jobs/studies (e.g., /api/dicom/jobs)
           - Authentication method (headers, cookies, etc.)
           - Request/response structure
        
        This will tell you exactly how to query the system programmatically!
        """


# ============================================================================
# Example Usage
# ============================================================================

def main():
    """Example usage of the Compass API client."""
    
    # Print inspection instructions
    inspector = CompassWebInspector()
    print(inspector.inspect_browser_network())
    print("\n" + "="*80 + "\n")
    
    # Try to connect to API
    config = CompassAPIConfig.from_env()
    client = CompassAPIClient(config)
    
    try:
        # Attempt to discover API
        logger.info("Attempting to discover API endpoints...")
        api_info = client.discover_endpoints()
        logger.info(f"API Info: {api_info}")
        
        # Test connection
        if client.test_connection():
            # Try to get jobs
            jobs = client.get_jobs(limit=5)
            logger.info(f"Retrieved {len(jobs)} jobs")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        logger.info("\nAPI connection failed. This could mean:")
        logger.info("1. Authentication is required (set COMPASS_API_USER/PASSWORD or API_KEY)")
        logger.info("2. The API endpoint is different")
        logger.info("3. API is not available (use database connection instead)")
        logger.info("\nFollow the browser inspection instructions above to discover the API!")


if __name__ == "__main__":
    main()

