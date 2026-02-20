"""
Compass C-FIND Query Client (DICOM Query/Retrieve)

This module provides a DICOM-native way to query Compass using C-FIND.
This is often the BEST option because:
- Uses standard DICOM protocol (no special credentials needed)
- If you can send to Compass, you can likely query it
- No database or REST API access required
- Supported by all DICOM routers

Author: DICOM Automation Team
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging
from datetime import datetime

from dotenv import load_dotenv
from pynetdicom import AE, evt, debug_logger
from pynetdicom.sop_class import (
    StudyRootQueryRetrieveInformationModelFind,
    PatientRootQueryRetrieveInformationModelFind,
)
from pydicom.dataset import Dataset

# Load .env file from project root
project_root = Path(__file__).resolve().parent
dotenv_path = project_root / ".env"

if dotenv_path.exists():
    load_dotenv(dotenv_path)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class CompassCFindConfig:
    """Configuration for Compass C-FIND queries."""
    host: str
    port: int
    remote_ae_title: str
    local_ae_title: str
    query_model: str = "STUDY"  # STUDY or PATIENT
    timeout: int = 30
    
    @classmethod
    def from_env(cls) -> "CompassCFindConfig":
        """Load configuration from environment variables.
        C-FIND uses CFIND_HOST, CFIND_PORT, CFIND_AE_TITLE when set (separate from
        Compass C-STORE). Local AE for C-FIND is the same as the active route:
        COMPASS_ROUTE (HTM_GI/HTM_OPH/HTM_ORTHO) -> LOCAL_AE_HTM_*. Set
        CFIND_LOCAL_AE_TITLE only to override (e.g. a dedicated query AE).
        """
        host = os.getenv("CFIND_HOST") or os.getenv("COMPASS_HOST", "roelbc200a.mayo.edu")
        port = int(os.getenv("CFIND_PORT") or os.getenv("COMPASS_PORT", "11112"))
        remote_ae = os.getenv("CFIND_AE_TITLE") or os.getenv("COMPASS_AE_TITLE", "COMPASS")
        local_ae = os.getenv("CFIND_LOCAL_AE_TITLE")
        if not local_ae:
            # Use the Compass route AE (REMOTE_AE_HTM_*) as the C-FIND calling AE.
            # The IM server sees studies as arriving from Compass (e.g. LB-HTM-GI),
            # so querying with that same AE title is required to get results back.
            route = os.getenv("COMPASS_ROUTE")
            if route == "HTM_GI":
                local_ae = os.getenv("REMOTE_AE_HTM_GI")
            elif route == "HTM_OPH":
                local_ae = os.getenv("REMOTE_AE_HTM_OPH")
            elif route == "HTM_ORTHO":
                local_ae = os.getenv("REMOTE_AE_HTM_ORTHO")
            local_ae = local_ae or os.getenv("LOCAL_AE_TITLE", "QUERY_SCU")
        return cls(
            host=host,
            port=port,
            remote_ae_title=remote_ae,
            local_ae_title=local_ae,
            query_model=os.getenv("COMPASS_QUERY_MODEL", "PATIENT"),
            timeout=int(os.getenv("COMPASS_QUERY_TIMEOUT", "30")),
        )


class CompassCFindClient:
    """Client for querying Compass using DICOM C-FIND."""
    
    def __init__(self, config: CompassCFindConfig):
        self.config = config
        self.ae = AE(ae_title=config.local_ae_title)
        
        # Add presentation contexts for C-FIND
        self.ae.add_requested_context(StudyRootQueryRetrieveInformationModelFind)
        self.ae.add_requested_context(PatientRootQueryRetrieveInformationModelFind)
        
        logger.info(f"C-FIND Client initialized: {config.local_ae_title} -> {config.remote_ae_title}")
    
    def _execute_find(self, query_dataset: Dataset) -> List[Dataset]:
        """
        Execute a C-FIND query and return all matching datasets.
        
        Args:
            query_dataset: DICOM dataset with query parameters
            
        Returns:
            List of matching DICOM datasets
        """
        results = []
        
        # Choose query model
        if self.config.query_model.upper() == "STUDY":
            query_model = StudyRootQueryRetrieveInformationModelFind
        else:
            query_model = PatientRootQueryRetrieveInformationModelFind
        
        # Associate with Compass
        assoc = self.ae.associate(
            self.config.host,
            self.config.port,
            ae_title=self.config.remote_ae_title,
        )
        
        if not assoc.is_established:
            raise ConnectionError(
                f"Failed to establish association with {self.config.host}:{self.config.port}"
            )
        
        try:
            # Send C-FIND request
            responses = assoc.send_c_find(query_dataset, query_model)
            
            for (status, identifier) in responses:
                if status:
                    # If status is pending, we have a match
                    if status.Status in (0xFF00, 0xFF01):
                        if identifier:
                            results.append(identifier)
                    # Success or no more matches
                    elif status.Status == 0x0000:
                        logger.info(f"C-FIND completed successfully, found {len(results)} matches")
                    else:
                        logger.warning(f"C-FIND status: 0x{status.Status:04X}")
                        raise RuntimeError(f"C-FIND failed with status 0x{status.Status:04X}")
                else:
                    logger.error("Connection timed out or was aborted")
                    break
                    
        finally:
            assoc.release()
        
        return results
    
    def find_study_by_uid(self, study_uid: str) -> Optional[Dataset]:
        """
        Find a study by Study Instance UID.
        Tries Study Root then Patient Root with a minimal query (StudyInstanceUID only).
        Wildcards like PatientID='*' are intentionally omitted because many IM servers
        reject or ignore them when a specific StudyInstanceUID is provided.
        """
        original_model = self.config.query_model

        for model in ("PATIENT", "STUDY"):
            self.config.query_model = model
            ds = Dataset()
            ds.QueryRetrieveLevel = "STUDY"
            ds.StudyInstanceUID = study_uid
            ds.PatientID = ""
            ds.PatientName = ""
            ds.StudyDate = ""
            ds.AccessionNumber = ""
            ds.NumberOfStudyRelatedInstances = ""

            logger.info(f"Querying for study (model={model}): {study_uid}")
            try:
                results = self._execute_find(ds)
                if results:
                    self.config.query_model = original_model
                    return results[0]
            except Exception as e:
                logger.warning(f"C-FIND with model={model} failed: {e}")

        self.config.query_model = original_model
        return None
    
    def find_studies_by_patient_id(
        self,
        patient_id: str,
        study_date: Optional[str] = None
    ) -> List[Dataset]:
        """
        Find studies by Patient ID.
        
        Args:
            patient_id: Patient ID to search for
            study_date: Optional study date (YYYYMMDD format or range like "20240101-20240131")
            
        Returns:
            List of DICOM datasets with study information
        """
        ds = Dataset()
        ds.QueryRetrieveLevel = "STUDY"
        ds.PatientID = patient_id
        ds.StudyDate = study_date if study_date else ""
        ds.StudyInstanceUID = ""
        ds.PatientName = ""
        ds.AccessionNumber = ""
        ds.StudyDescription = ""

        logger.info(f"Querying for patient: {patient_id}")
        return self._execute_find(ds)
    
    def find_studies_by_accession(self, accession_number: str) -> List[Dataset]:
        """
        Find studies by Accession Number.
        
        Args:
            accession_number: Accession number to search for
            
        Returns:
            List of DICOM datasets with study information
        """
        ds = Dataset()
        ds.QueryRetrieveLevel = "STUDY"
        ds.AccessionNumber = accession_number
        ds.PatientID = "*"
        ds.StudyInstanceUID = ""
        ds.PatientName = ""
        ds.StudyDate = ""
        ds.StudyDescription = ""

        logger.info(f"Querying for accession: {accession_number}")
        return self._execute_find(ds)
    
    def find_studies_by_date_range(
        self,
        start_date: str,
        end_date: Optional[str] = None
    ) -> List[Dataset]:
        """
        Find studies within a date range.
        
        Args:
            start_date: Start date in YYYYMMDD format
            end_date: End date in YYYYMMDD format (optional, defaults to start_date)
            
        Returns:
            List of DICOM datasets with study information
        """
        ds = Dataset()
        ds.QueryRetrieveLevel = "STUDY"
        ds.StudyDate = f"{start_date}-{end_date}" if end_date else start_date
        ds.PatientID = "*"
        ds.StudyInstanceUID = ""
        ds.PatientName = ""
        ds.AccessionNumber = ""
        ds.StudyDescription = ""

        logger.info(f"Querying for date range: {ds.StudyDate}")
        return self._execute_find(ds)
    
    def find_studies_by_modality(
        self,
        modality: str,
        study_date: Optional[str] = None
    ) -> List[Dataset]:
        """
        Find studies by modality.
        
        Args:
            modality: Modality to search for (e.g., "CT", "MR", "CR")
            study_date: Optional study date filter
            
        Returns:
            List of DICOM datasets with study information
        """
        ds = Dataset()
        ds.QueryRetrieveLevel = "STUDY"
        ds.ModalitiesInStudy = modality
        ds.StudyDate = study_date if study_date else ""
        ds.PatientID = "*"
        ds.StudyInstanceUID = ""
        ds.PatientName = ""
        ds.AccessionNumber = ""
        ds.StudyDescription = ""

        logger.info(f"Querying for modality: {modality}")
        return self._execute_find(ds)
    
    def test_connection(self) -> bool:
        """
        Test C-FIND connection by performing a simple query.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            today = datetime.now().strftime("%Y%m%d")

            # Try multiple query strategies — some servers are picky
            strategies = [
                {
                    'name': 'Patient Root + PatientID wildcard',
                    'model': 'PATIENT',
                    'attrs': {'QueryRetrieveLevel': 'STUDY', 'PatientID': '*', 'StudyDate': today, 'StudyInstanceUID': ''},
                },
                {
                    'name': 'Study Root minimal (date only)',
                    'model': 'STUDY',
                    'attrs': {'QueryRetrieveLevel': 'STUDY', 'StudyDate': today, 'StudyInstanceUID': ''},
                },
                {
                    'name': 'Study Root with PatientID wildcard',
                    'model': 'STUDY',
                    'attrs': {'QueryRetrieveLevel': 'STUDY', 'PatientID': '*', 'StudyDate': today, 'StudyInstanceUID': ''},
                },
                {
                    'name': 'Patient Root minimal',
                    'model': 'PATIENT',
                    'attrs': {'QueryRetrieveLevel': 'STUDY', 'PatientID': '*', 'StudyInstanceUID': ''},
                },
            ]

            for strategy in strategies:
                logger.info(f"Trying: {strategy['name']}...")
                ds = Dataset()
                for attr, val in strategy['attrs'].items():
                    setattr(ds, attr, val)

                # Temporarily override query model
                original_model = self.config.query_model
                self.config.query_model = strategy['model']
                try:
                    results = self._execute_find(ds)
                    logger.info(f"SUCCESS with '{strategy['name']}' (found {len(results)} studies)")
                    return True
                except Exception as e:
                    logger.warning(f"Failed with '{strategy['name']}': {e}")
                finally:
                    self.config.query_model = original_model

            logger.error("All C-FIND strategies failed")
            return False

        except Exception as e:
            logger.error(f"Connection test failed: {e}")
            return False
    
    def get_series_for_study(self, study_uid: str) -> List[Dataset]:
        """
        Get all series for a specific study.
        
        Args:
            study_uid: Study Instance UID
            
        Returns:
            List of series datasets
        """
        ds = Dataset()
        ds.QueryRetrieveLevel = "SERIES"
        ds.StudyInstanceUID = study_uid
        
        # Request series attributes
        ds.SeriesInstanceUID = ""
        ds.SeriesNumber = ""
        ds.SeriesDescription = ""
        ds.Modality = ""
        ds.NumberOfSeriesRelatedInstances = ""
        
        logger.info(f"Querying series for study: {study_uid}")
        return self._execute_find(ds)
    
    def dataset_to_dict(self, ds: Dataset) -> Dict[str, Any]:
        """
        Convert DICOM dataset to dictionary for easier handling.
        
        Args:
            ds: DICOM dataset
            
        Returns:
            Dictionary with DICOM attributes
        """
        result = {}
        
        # Common study attributes
        attrs = [
            'StudyInstanceUID',
            'PatientID',
            'PatientName',
            'PatientBirthDate',
            'PatientSex',
            'StudyDate',
            'StudyTime',
            'AccessionNumber',
            'StudyDescription',
            'ModalitiesInStudy',
            'NumberOfStudyRelatedSeries',
            'NumberOfStudyRelatedInstances',
            'SeriesInstanceUID',
            'SeriesNumber',
            'SeriesDescription',
            'Modality',
            'NumberOfSeriesRelatedInstances',
        ]
        
        for attr in attrs:
            if hasattr(ds, attr):
                value = getattr(ds, attr)
                # Convert to string for consistency
                result[attr] = str(value) if value is not None else None
        
        return result


# Convenience functions for use in tests
def cfind_study_in_compass(
    study_uid: str,
    timeout: int = 30,
    config: Optional[CompassCFindConfig] = None
) -> Optional[Dict[str, Any]]:
    """
    Convenience function to find a study using C-FIND.
    
    Args:
        study_uid: Study Instance UID to search for
        timeout: Query timeout in seconds
        config: Optional configuration (loads from env if not provided)
        
    Returns:
        Dictionary with study information, or None if not found
        
    Usage in tests:
        study = cfind_study_in_compass(study_uid)
        assert study is not None, "Study not found in Compass"
        assert int(study['NumberOfStudyRelatedInstances']) == 10
    """
    if config is None:
        config = CompassCFindConfig.from_env()
        config.timeout = timeout
    
    client = CompassCFindClient(config)
    result = client.find_study_by_uid(study_uid)
    
    if result:
        return client.dataset_to_dict(result)
    return None


# Example usage
if __name__ == "__main__":
    import sys
    
    # Enable pynetdicom debug logging
    # debug_logger()
    
    config = CompassCFindConfig.from_env()
    client = CompassCFindClient(config)
    
    try:
        # Test connection
        logger.info("Testing C-FIND connection...")
        if not client.test_connection():
            logger.error("Connection test failed")
            sys.exit(1)
        
        logger.info("Connection successful!")
        
        # Example queries
        if len(sys.argv) > 1:
            query_type = sys.argv[1]
            
            if query_type == "study" and len(sys.argv) > 2:
                # Find by Study UID
                study_uid = sys.argv[2]
                result = client.find_study_by_uid(study_uid)
                if result:
                    print("\nStudy found:")
                    print(client.dataset_to_dict(result))
                else:
                    print(f"Study not found: {study_uid}")
            
            elif query_type == "patient" and len(sys.argv) > 2:
                # Find by Patient ID
                patient_id = sys.argv[2]
                results = client.find_studies_by_patient_id(patient_id)
                print(f"\nFound {len(results)} studies for patient {patient_id}")
                for r in results[:5]:  # Show first 5
                    print(client.dataset_to_dict(r))
            
            elif query_type == "today":
                # Find today's studies
                today = datetime.now().strftime("%Y%m%d")
                results = client.find_studies_by_date_range(today)
                print(f"\nFound {len(results)} studies today")
                for r in results[:5]:  # Show first 5
                    print(client.dataset_to_dict(r))
            
            else:
                print("Usage:")
                print("  python compass_cfind_client.py study <study_uid>")
                print("  python compass_cfind_client.py patient <patient_id>")
                print("  python compass_cfind_client.py today")
        else:
            print("\nC-FIND client ready!")
            print("\nUsage:")
            print("  python compass_cfind_client.py study <study_uid>")
            print("  python compass_cfind_client.py patient <patient_id>")
            print("  python compass_cfind_client.py today")
            
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)

