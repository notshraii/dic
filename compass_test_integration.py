"""
Example: Integrating Compass queries into test validation

This module supports THREE methods for querying Compass:
1. C-FIND (DICOM Query) - RECOMMENDED, uses standard DICOM protocol
2. REST API - Good if available
3. Direct Database - Fallback option

Usage in tests:
    from compass_test_integration import verify_study_in_compass
    
    # After sending DICOM files
    result = verify_study_in_compass(study_uid, expected_count=10, method='cfind')
    assert result.success, result.message
"""

from typing import Optional, List, Literal
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import time
import logging
import os

from dotenv import load_dotenv

# Load .env file from project root
project_root = Path(__file__).resolve().parent
dotenv_path = project_root / ".env"

if dotenv_path.exists():
    load_dotenv(dotenv_path)

logger = logging.getLogger(__name__)

# Import clients (handle missing imports gracefully)
try:
    from compass_cfind_client import CompassCFindClient, CompassCFindConfig
    CFIND_AVAILABLE = True
except ImportError:
    CFIND_AVAILABLE = False
    logger.warning("C-FIND client not available")

try:
    from compass_db_query import CompassDatabaseClient, CompassDatabaseConfig
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("Database client not available")

try:
    from compass_api_client import CompassAPIClient, CompassAPIConfig
    API_AVAILABLE = True
except ImportError:
    API_AVAILABLE = False
    logger.warning("API client not available")


@dataclass
class ValidationResult:
    """Result of a Compass validation check."""
    success: bool
    message: str
    data: Optional[dict] = None


class CompassTestValidator:
    """
    Helper class for validating test results in Compass.
    
    Supports three query methods:
    - 'cfind': DICOM C-FIND (recommended, uses standard DICOM protocol)
    - 'api': REST API
    - 'database': Direct SQL database access
    """
    
    def __init__(
        self, 
        method: Literal['cfind', 'api', 'database', 'auto'] = 'auto',
        config: Optional[any] = None
    ):
        """
        Initialize validator.
        
        Args:
            method: Query method ('cfind', 'api', 'database', or 'auto')
            config: Configuration object (type depends on method)
        """
        self.method = method
        
        # Auto-select method if not specified
        if method == 'auto':
            if CFIND_AVAILABLE:
                self.method = 'cfind'
                logger.info("Auto-selected C-FIND method")
            elif API_AVAILABLE:
                self.method = 'api'
                logger.info("Auto-selected API method")
            elif DB_AVAILABLE:
                self.method = 'database'
                logger.info("Auto-selected database method")
            else:
                raise ImportError("No query method available. Install dependencies.")
        
        # Initialize appropriate client
        if self.method == 'cfind':
            if not CFIND_AVAILABLE:
                raise ImportError("C-FIND client not available")
            self.config = config or CompassCFindConfig.from_env()
            self.client_class = CompassCFindClient
        elif self.method == 'api':
            if not API_AVAILABLE:
                raise ImportError("API client not available")
            self.config = config or CompassAPIConfig.from_env()
            self.client_class = CompassAPIClient
        elif self.method == 'database':
            if not DB_AVAILABLE:
                raise ImportError("Database client not available")
            self.config = config or CompassDatabaseConfig.from_env()
            self.client_class = CompassDatabaseClient
        else:
            raise ValueError(f"Unknown method: {method}")
    
    def verify_study_received(
        self,
        study_uid: str,
        timeout_seconds: int = 30,
        poll_interval: float = 1.0,
        expected_image_count: Optional[int] = None
    ) -> ValidationResult:
        """
        Verify that a study was received by Compass.
        
        Polls Compass until the study appears or timeout is reached.
        Works with all three query methods (C-FIND, API, database).
        
        Args:
            study_uid: Study Instance UID to look for
            timeout_seconds: Maximum time to wait for study
            poll_interval: Seconds between polls
            expected_image_count: Expected number of images (optional)
            
        Returns:
            ValidationResult with success status and details
        """
        start_time = time.time()
        
        logger.info(f"Waiting for study {study_uid} in Compass (method: {self.method})...")
        
        while time.time() - start_time < timeout_seconds:
            try:
                # Query using selected method
                if self.method == 'cfind':
                    study = self._cfind_get_study(study_uid)
                elif self.method == 'api':
                    study = self._api_get_study(study_uid)
                else:  # database
                    study = self._db_get_study(study_uid)
                
                if study:
                    logger.info(f"Study found in Compass: {study}")
                    
                    # Check image count if specified
                    if expected_image_count is not None:
                        actual_count = self._get_image_count(study)
                        if actual_count != expected_image_count:
                            return ValidationResult(
                                success=False,
                                message=(
                                    f"Study found but image count mismatch: "
                                    f"expected {expected_image_count}, got {actual_count}"
                                ),
                                data=study
                            )
                    
                    return ValidationResult(
                        success=True,
                        message=f"Study verified in Compass using {self.method}",
                        data=study
                    )
            
            except Exception as e:
                logger.warning(f"Error checking Compass: {e}")
            
            time.sleep(poll_interval)
        
        elapsed = time.time() - start_time
        return ValidationResult(
            success=False,
            message=f"Study not found in Compass after {elapsed:.1f} seconds (method: {self.method})"
        )
    
    def _cfind_get_study(self, study_uid: str) -> Optional[dict]:
        """Get study using C-FIND."""
        client = CompassCFindClient(self.config)
        result = client.find_study_by_uid(study_uid)
        if result:
            return client.dataset_to_dict(result)
        return None
    
    def _api_get_study(self, study_uid: str) -> Optional[dict]:
        """Get study using API."""
        client = CompassAPIClient(self.config)
        return client.get_job_by_study_uid(study_uid)
    
    def _db_get_study(self, study_uid: str) -> Optional[dict]:
        """Get study using database."""
        with CompassDatabaseClient(self.config) as client:
            return client.get_job_by_study_uid(study_uid)
    
    def _get_image_count(self, study: dict) -> int:
        """Extract image count from study (handles different field names)."""
        # Try different possible field names
        for field in ['NumberOfStudyRelatedInstances', 'ImageCount', 'InstanceCount']:
            if field in study and study[field]:
                try:
                    return int(study[field])
                except (ValueError, TypeError):
                    pass
        return 0
    
    def verify_routing(
        self,
        study_uid: str,
        expected_calling_aet: Optional[str] = None,
        expected_destination_aet: Optional[str] = None
    ) -> ValidationResult:
        """
        Verify that a study was routed correctly.
        
        Args:
            study_uid: Study Instance UID
            expected_calling_aet: Expected calling AE Title
            expected_destination_aet: Expected destination AE Title
            
        Returns:
            ValidationResult with routing verification details
        """
        try:
            with CompassDatabaseClient(self.config) as client:
                job = client.get_job_by_study_uid(study_uid)
                
                if not job:
                    return ValidationResult(
                        success=False,
                        message=f"Study {study_uid} not found in Compass"
                    )
                
                # Check calling AET
                if expected_calling_aet:
                    actual_calling = job.get('CallingAET', '')
                    if actual_calling != expected_calling_aet:
                        return ValidationResult(
                            success=False,
                            message=(
                                f"Calling AET mismatch: expected {expected_calling_aet}, "
                                f"got {actual_calling}"
                            ),
                            data=job
                        )
                
                # Check destination AET
                if expected_destination_aet:
                    actual_dest = job.get('DestinationAET', '')
                    if actual_dest != expected_destination_aet:
                        return ValidationResult(
                            success=False,
                            message=(
                                f"Destination AET mismatch: expected {expected_destination_aet}, "
                                f"got {actual_dest}"
                            ),
                            data=job
                        )
                
                return ValidationResult(
                    success=True,
                    message="Routing verified successfully",
                    data=job
                )
                
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"Error verifying routing: {e}"
            )
    
    def verify_dicom_tag(
        self,
        study_uid: str,
        tag_name: str,
        expected_value: str
    ) -> ValidationResult:
        """
        Verify a specific DICOM tag value in Compass.
        
        Args:
            study_uid: Study Instance UID
            tag_name: DICOM tag name (e.g., 'PatientName')
            expected_value: Expected tag value
            
        Returns:
            ValidationResult with tag verification details
        """
        try:
            with CompassDatabaseClient(self.config) as client:
                # First get the job
                job = client.get_job_by_study_uid(study_uid)
                
                if not job:
                    return ValidationResult(
                        success=False,
                        message=f"Study {study_uid} not found in Compass"
                    )
                
                job_id = job.get('JobID')
                if not job_id:
                    return ValidationResult(
                        success=False,
                        message="Job ID not found"
                    )
                
                # Get DICOM tags
                tags = client.get_dicom_tags(job_id)
                
                # Find the specific tag
                tag_value = None
                for tag in tags:
                    if tag.get('TagName') == tag_name:
                        tag_value = tag.get('Value')
                        break
                
                if tag_value is None:
                    return ValidationResult(
                        success=False,
                        message=f"Tag {tag_name} not found in Compass"
                    )
                
                if tag_value != expected_value:
                    return ValidationResult(
                        success=False,
                        message=(
                            f"Tag {tag_name} value mismatch: "
                            f"expected '{expected_value}', got '{tag_value}'"
                        ),
                        data={'tag_name': tag_name, 'actual_value': tag_value}
                    )
                
                return ValidationResult(
                    success=True,
                    message=f"Tag {tag_name} verified: {tag_value}",
                    data={'tag_name': tag_name, 'value': tag_value}
                )
                
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"Error verifying tag: {e}"
            )
    
    def verify_phi_removed(
        self,
        study_uid: str,
        phi_tags: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Verify that PHI has been removed from a study.
        
        Args:
            study_uid: Study Instance UID
            phi_tags: List of PHI tag names to check (or default list)
            
        Returns:
            ValidationResult indicating if PHI is present
        """
        if phi_tags is None:
            phi_tags = [
                'PatientName',
                'PatientID', 
                'PatientBirthDate',
                'PatientAddress',
                'PatientTelephoneNumbers'
            ]
        
        try:
            with CompassDatabaseClient(self.config) as client:
                job = client.get_job_by_study_uid(study_uid)
                
                if not job:
                    return ValidationResult(
                        success=False,
                        message=f"Study {study_uid} not found in Compass"
                    )
                
                job_id = job.get('JobID')
                tags = client.get_dicom_tags(job_id)
                
                # Check for PHI
                phi_found = []
                for tag in tags:
                    tag_name = tag.get('TagName')
                    if tag_name in phi_tags:
                        tag_value = tag.get('Value', '')
                        # Check if value is not empty/anonymized
                        if tag_value and tag_value not in ['ANONYMOUS', 'ANON', '']:
                            phi_found.append({
                                'tag': tag_name,
                                'value': tag_value
                            })
                
                if phi_found:
                    return ValidationResult(
                        success=False,
                        message=f"PHI found in {len(phi_found)} tags",
                        data={'phi_tags': phi_found}
                    )
                
                return ValidationResult(
                    success=True,
                    message="No PHI found - anonymization successful"
                )
                
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"Error checking PHI: {e}"
            )
    
    def get_study_metrics(
        self,
        start_date: datetime,
        end_date: Optional[datetime] = None
    ) -> ValidationResult:
        """
        Get metrics for studies in a time range.
        
        Args:
            start_date: Start of time range
            end_date: End of time range (defaults to now)
            
        Returns:
            ValidationResult with metrics data
        """
        if end_date is None:
            end_date = datetime.now()
        
        try:
            with CompassDatabaseClient(self.config) as client:
                # Get all jobs in date range
                query = """
                SELECT 
                    COUNT(*) as TotalJobs,
                    SUM(ImageCount) as TotalImages,
                    COUNT(DISTINCT PatientID) as UniquePatients,
                    COUNT(DISTINCT Modality) as UniqueModalities,
                    AVG(DATEDIFF(SECOND, CreatedAt, CompletedAt)) as AvgDurationSeconds
                FROM Jobs
                WHERE CreatedAt >= ? AND CreatedAt <= ?
                """
                
                results = client.execute_query(query, (start_date, end_date))
                
                if results:
                    return ValidationResult(
                        success=True,
                        message="Metrics retrieved successfully",
                        data=results[0]
                    )
                else:
                    return ValidationResult(
                        success=False,
                        message="No data found for date range"
                    )
                
        except Exception as e:
            return ValidationResult(
                success=False,
                message=f"Error retrieving metrics: {e}"
            )


# Convenience functions for use in tests
def verify_study_in_compass(
    study_uid: str,
    timeout: int = 30,
    expected_count: Optional[int] = None,
    method: Literal['cfind', 'api', 'database', 'auto'] = 'auto'
) -> ValidationResult:
    """
    Convenience function to verify a study in Compass.
    
    Args:
        study_uid: Study Instance UID to search for
        timeout: Maximum seconds to wait
        expected_count: Expected image count (optional)
        method: Query method ('cfind' recommended, 'api', 'database', or 'auto')
    
    Usage in tests:
        # Auto-select method (tries C-FIND first)
        result = verify_study_in_compass(study_uid, expected_count=10)
        assert result.success, result.message
        
        # Force specific method
        result = verify_study_in_compass(study_uid, method='cfind')
        assert result.success, result.message
    """
    validator = CompassTestValidator(method=method)
    return validator.verify_study_received(
        study_uid,
        timeout_seconds=timeout,
        expected_image_count=expected_count
    )


def verify_routing_in_compass(
    study_uid: str,
    calling_aet: Optional[str] = None,
    destination_aet: Optional[str] = None
) -> ValidationResult:
    """
    Convenience function to verify routing in Compass.
    
    Usage in tests:
        result = verify_routing_in_compass(
            study_uid,
            calling_aet="OPV_GPA",
            destination_aet="OPHTHALMOLOGY_PACS"
        )
        assert result.success, result.message
    """
    validator = CompassTestValidator()
    return validator.verify_routing(study_uid, calling_aet, destination_aet)


def verify_anonymization_in_compass(study_uid: str) -> ValidationResult:
    """
    Convenience function to verify anonymization in Compass.
    
    Usage in tests:
        result = verify_anonymization_in_compass(study_uid)
        assert result.success, result.message
    """
    validator = CompassTestValidator()
    return validator.verify_phi_removed(study_uid)


# Example pytest integration
if __name__ == "__main__":
    # Example usage
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python compass_test_integration.py <study_uid>")
        sys.exit(1)
    
    study_uid = sys.argv[1]
    
    # Test verification
    print(f"Verifying study: {study_uid}")
    result = verify_study_in_compass(study_uid, timeout=10)
    
    if result.success:
        print(f"SUCCESS: {result.message}")
        if result.data:
            print(f"Job Details: {result.data}")
    else:
        print(f"FAILED: {result.message}")
        sys.exit(1)

