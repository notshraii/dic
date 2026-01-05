# Test Plan
## HTM Compass Release 1.00.00

**Template Reference:** [DLMPIM.F-7683]  
**Parent Document:** SQA Test Procedure [DLMPIM.PROC-19017]

---

## 1.0 Introduction

Laurel Bridge Compass is a routing solution that manages the workflow of DICOM images and HL7 messages. It functions as a traffic manager, receiving data from various sources (modalities, VPNs), evaluating specific rules (DICOM tags, time of day, source AE Titles), and routing that data to specific destinations.

Messages originate from scanners and other modalities or PACs (list of sources to be provided). In this document they are referred to as Sources. These messages contain SOP Instance UIDs (Service Object Pair Instance Unique Identifiers) that uniquely identify each individual image or object within a study. Compass is configured to process objects with specific UIDs that are accepted as they come from recognized sources. The system expects certain specific DICOM tags (attributes) to be present within the incoming DICOM object, and to conform to a pre-established format. Upon receiving the messages from the Source certain transformations are applied to DICOM objects, such as changing Series Description. These transformations are rule-based and performed automatically. For instance, if the incoming Series Description (X) is "BRAIN_MR_AXIAL", the system might be configured to change it (Y) to "Brain MRI Axial". The destination of the messages depends on the routing rules applied to it. Destinations include InfinityView, which is a viewing software for DICOM images, and MIDIA, that is a PACS archive for Mayo.

The infrastructure is supported by a load balancer that determines which server cluster to send the message to, based on availability. The server that is less busy is chosen to route the images through.

Mayo Clinic is switching its routing solution from UltraGateway to Compass due to the following reasons: UltraRAD, the vendor for UltraGateway, has been unable to resolve issues that arose after an upgrade in late 2023. This has led to increased routing problem tickets. Additionally, it became too difficult to support the system with the numerous customizations that were made to it to serve Mayo Clinic's needs. Compass provides solutions that generally don't require any code. Additionally, the number of incidents is expected to drop after the transition, while the speed of transmission is to be maintained within the established latency range baseline. Compass is not a new software and is being utilized already for certain cases, the project is about transitioning the departments over to an existing system. Therefore, software release is not expected. However, due to an increasing number of devices, new servers will be added to the infrastructure.

Below is a system architecture diagram for Laurel Bridge Compass implementation. Imaging data enters via the Mayo Standard VPN from Laurel Bridge Support and EISS Support nodes. Data is directed to a central Compass Load Balancer/Gateway (Port 104/11112) that routes data to InfinityView and MIDIA. All nodes report to a Lighthouse centralized monitoring server.

This Test Plan documents the strategy, scope, and approach for validating the migration of Mayo Clinic's medical imaging routing infrastructure from UltraGateway to Laurel Bridge Compass.

---

## 2.0 Test Scope

The scope of this testing effort focuses on the functional parity between the legacy UltraGateway rules engine and the new Compass rules engine, as well as the non-functional requirements regarding throughput and stability. Each of the custom rules will be covered by a test case and all the standard rules will be covered as part of the smoke suite.

The team is moving forward with the process of reconfiguring ophthalmology department devices to be routed through Compass, before any changes to the infrastructure are made. In the initial stages a sanity test suite will be executed to ensure that the images that are sent by the devices are routed properly and that the latency is within pre-established baseline limits (10-11 mins) for the image to appear in InfinityView. The latency will be measured by examining the timestamps in Lighthouse, the monitoring server. This sanity suite will be executed for each converted device as a step in the transition process.

As the infrastructure is updated with the new servers the scope of testing will increase. The overall system will be tested in a regression suite. The following data permutations will be considered: source type (modality), source address (where the message is sent from to the router), file type (x-rays, CT scans, etc), DICOM tags, destinations, job actions, listeners and filters. For each of the possible paths there will be a test case designed to verify that if all the variables are valid the message can reach its destination successfully. Negative testing will be performed for all the paths to ensure that if one of the variables contains an invalid value the message is not received, and proper notifications are triggered.

Performance testing will be conducted to ensure the system can support current and future clinical workflows under peak load conditions. Testing will simulate multiple scanners concurrently transmitting digital pathology images to assess the Compass routers' bandwidth handling during sustained high-volume periods. End-to-end image ingestion time will be measured by analyzing Compass logs, and potentially automation script logs.

Additionally, tests will be executed to determine that the system rebalances the workload as expected. If one or more of the servers becomes unavailable the overall behavior of the routing system will be evaluated as well as Compass Service crash recovery process.

Lighthouse integration will be tested to ensure that notifications are triggered and metrics are delivered as expected.

---

**Scope for Release 1.00.00 will contain the following user stories from Azure Dev Ops:**

| ID | Work Item Type | Title |
|---|---|---|
| 0000001 | User Story | |

### 2.1 Features to be Tested

**Verification:**

- **Compass Router**
  - **Basic Flow**
    - Receive DICOM Image via C-STORE from Recognized Source
    - Route Image to Correct Destination Based on AE Title
    - Route Image to Correct Destination Based on Modality
    - Route Image to Correct Destination Based on DICOM Tags
    - Route Image to Correct Destination Based on Time Schedule
    - Association Acceptance from Known Calling AE Title
    - Association Rejection from Unknown Calling AE Title
  - **Calling AE Title Routing**
    - CT_SCANNER_1 Routes to Correct Destination
    - MR_SCANNER_A Routes to Correct Destination
    - CR_ROOM_1 Routes to Correct Destination
    - US_PORTABLE Routes to Correct Destination
    - ULTRA_MCR_FORUM Routes to Correct Destination
    - Unknown AE Title Handling (Accept/Reject Behavior)
    - Multiple AE Titles Batch Send
  - **Modality-Based Routing**
    - CT Modality Routing
    - MR Modality Routing
    - CR Modality Routing
    - US Modality Routing
    - OPV Modality Routing (Ophthalmology Visual Fields)
    - OPT Modality Routing (Optical Coherence Tomography)
    - OT Modality Routing (IOL Master)
    - DOC Modality Routing (Combined Reports)
  - **Destinations**
    - Route to InfinityView
    - Route to MIDIA
    - Route to Multiple Destinations Simultaneously

- **Tag Morphing (Composer/Filter Actions)**
  - **Study Description Transformations**
    - OPV with GPA Series Description Sets "Visual Fields (VF) GPA"
    - OPV with SFA Series Description Sets "Visual Fields (VF) SFA"
    - OPV with Mixed Series Description Sets "Visual Fields (VF)"
    - OPT Modality Sets "Optical Coherence Tomography (OCT)"
    - OT Modality Sets "IOL Master (OT)"
    - DOC Modality Sets "OCT and VF Combined Report"
  - **Patient ID Normalization**
    - De-identification of Patient Name
    - De-identification of Patient ID
    - De-identification of Patient Birth Date
    - Re-identification of Tags
  - **Accession Number Handling**
    - Preserve Device-Provided Accession Number
    - Generate Accession Number via IIMS Web Service (Blank Accession)
    - Accession Number Edge Cases (Missing Tag, Long Value, Special Characters)
  - **UID Generation**
    - Generate and Populate Study Instance UID
    - Generate and Populate Series Instance UID
    - Generate and Populate SOP Instance UID

- **Data Validation**
  - **Study Date/Time Handling**
    - Populate Blank Study Date from Acquisition Date
    - Populate Blank Study Time from Acquisition Time
    - Preserve Existing Study Date/Time When Present
  - **Patient Demographics**
    - Handle Blank Patient Name
    - Handle Special Characters in Patient Name (Apostrophe, Hyphen)
    - Handle Accented Characters in Patient Name
    - Handle Patient Name with Suffix
  - **Required Tags**
    - Handle Missing Modality Tag
    - Handle Missing SOP Class UID
    - Handle Missing Transfer Syntax

- **Failure Mode Handling**
  - **Delay Tolerance**
    - Accept Images with 2-Minute Pause Between Files
    - Accept Images with 30-Second Delays (MCIE Slow Send)
    - Accept Images with Variable Delays (5-60 Seconds)
  - **Duplicate Handling**
    - Accept Duplicate Study (Same Study Instance UID)
    - Handle Modified Duplicate (Same Study UID, Different Patient Data)
    - Track Multiple Entries for Duplicate Sends
  - **Network Resilience**
    - Recover from Temporary Connection Loss
    - Handle Association Timeout Gracefully

- **Load Balancer**
  - **Failover**
    - Traffic Reroutes to Backup Node When Primary Unavailable
    - Compass Service Crash Recovery
    - Workload Rebalancing After Node Recovery
  - **Load Distribution**
    - Distribute Traffic Based on Server Availability
    - Route to Less Busy Server

- **Lighthouse Integration**
  - **Monitoring**
    - Heartbeat Reporting to Lighthouse
    - Status Updates to Lighthouse
    - Error Log Reporting to Lighthouse
  - **Notifications**
    - Alert Triggered on Routing Failure
    - Alert Triggered on High Error Rate
    - Alert Triggered on Latency Threshold Exceeded

- **Performance**
  - Simulate Multiple Scanners and Verify Desired Throughput at Peak Hour
  - Load Stability at 3x Peak Load for Extended Duration
  - Throughput at 150% of Peak Images Per Second
  - Throughput at 200% of Peak Images Per Second
  - P95 Latency Within Threshold (2000ms for Stability, 1500ms for Throughput)
  - Error Rate Below Threshold (2%)
  - 48-Hour Soak Test at 3x Peak Load

**Validation:**
- User Acceptance - validate User & Training guides, work instructions and procedures

### 2.2 Features NOT Tested

- **PACS/VNA Functionality.** We are testing the delivery of images to these systems, not the internal functionality of the PACS/VNA itself.

- **Network Hardware.** The physical VPN and firewalls are assumed to be configured by the Network team; testing is limited to application connectivity through these pipes.

- **Legacy UltraGateway Decommissioning.**

---

## 3.0 Test Approach

### 3.1 High-Level Test Approach

- **Rules Verification:**  
  Mirroring Compass test server with a Rochester server configuration, UltraGateway rules and passing DICOM data to verify routing logic. DICOM images with various valid parameters will be routed to MIDIA test environment server via Compass and ensure that they reach their destinations as expected. Behavior of the system when encountering faulty tags will be evaluated as part of negative testing. The automation framework uses pynetdicom C-STORE operations with configurable Calling AE Titles to simulate different source devices.

- **Tag Morphing:**  
  Tags will be modified on the way to their destinations to ensure that they are updating as expected at the proper time. The test framework creates DICOM files with specific input attributes (modality, series description, institution name) and sends them through Compass. C-FIND queries verify that expected transformations (e.g., StudyDescription changes) were applied correctly.

- **Performance:**  
  Performance testing will simulate peak loads on Laurel Bridge using Python scripts and the PyDICOM library to generate diverse DICOM input files from simulated scanners and lab automation machines. The automation framework supports:
  - Configurable peak images per second (default: 50 img/s)
  - Load multiplier for stress testing (default: 3.0x for stability tests)
  - Concurrent worker threads (default: 8)
  - Configurable test duration (default: 300 seconds, scalable to 48-hour soak tests)
  - Thread-safe metrics collection for latency, throughput, and error rates
  - Automatic DICOM decompression for JPEG/JPEG2000/RLE compressed files

- **Metrics:**  
  The system will be tested for generating the appropriate Lighthouse data: status, heartbeats, and error logs.

---

### 3.2 System Test Strategy

#### 3.2.1 Development approach

There are DEV, TEST and PROD environments. Functional testing will be done in the TEST environment, with a Waterfall approach being used in testing. The rules are already defined in the legacy system; the development activity involves translating these into Compass "Conditions" and "Actions."

#### 3.2.2 Test Data

- A subset of production studies (CR, CT, MR, US) stripped of PHI will be used to ensure vendor-specific private tags are handled correctly.
- Metadata will be defined in the DICOM Headers as hydrated by the scanner
- The automation framework generates diverse synthetic DICOM samples covering:
  - 7 modalities: CR, CT, MR, US, PET, MG, NM
  - Multiple image sizes: 128x128, 256x256, 512x512, 1024x1024, 2048x2048, 4096x4096
  - Bit depths: 8-bit, 12-bit, 14-bit, 16-bit
  - Photometric interpretations: MONOCHROME1, MONOCHROME2
  - Size categories: small (<1MB), medium (1-10MB), large (>10MB)
- Each test generates unique StudyInstanceUID, SeriesInstanceUID, and SOPInstanceUID to ensure test isolation
- Anonymization workflow replaces PHI with test values (PatientName: ZZTESTPATIENT^ANONYMIZED, PatientID: 11043207)

#### 3.2.3 Selected Test Suites

Each test suite listed below will follow the designated format:
- Test Suite Name
- Brief description of the function
- The type will be new, updated and/or unchanged
- Request ID and/or Feature associated to test suite/case(s)
- A table containing the Sub Test Suite and test cases if applicable

---

**Laurel Bridge Functional**

**Test Suite Name: Routing**  
**Function:** This suite will verify standard C-STORE operations and complex rules. Tests validate that Compass accepts connections from different Calling AE Titles and routes images based on configured rules. Includes connectivity verification via C-ECHO ping.  
**Type:** New  
**Automation:** `tests/test_calling_aet_routing.py`

| Sub Test Suite | Test Case(s) |
|---|---|
| Calling AET Routing | test_calling_aet_routing[ULTRA_MCR_FORUM], test_calling_aet_routing[CT_SCANNER_1], test_calling_aet_routing[MR_SCANNER_A], test_calling_aet_routing[CR_ROOM_1], test_calling_aet_routing[US_PORTABLE] |
| Batch AET Testing | test_multiple_aets_batch_send |
| Unknown AET Behavior | test_unknown_calling_aet |
| Modality Combinations | test_calling_aet_with_modality_combinations[CT], test_calling_aet_with_modality_combinations[MR], test_calling_aet_with_modality_combinations[CR], test_calling_aet_with_modality_combinations[US], test_calling_aet_with_modality_combinations[OPV] |

---

**Test Suite Name: Tag Coercion**  
**Function:** This suite will verify any changes made to the tags such as "De-Identify" and "Composer" filters correctly modify the tags (e.g., mapping Accession Numbers). Tests create DICOM files with specific input attributes and verify Compass applies expected transformations.  
**Type:** New  
**Automation:** `tests/test_routing_transformations.py`

| Sub Test Suite | Test Case(s) |
|---|---|
| Visual Fields Transformations | test_routing_transformation[OPV_GPA_VisualFields], test_routing_transformation[OPV_SFA_VisualFields], test_routing_transformation[OPV_Mixed_VisualFields] |
| OCT Transformations | test_routing_transformation[OPT_OCT] |
| IOL Master Transformations | test_routing_transformation[OT_IOLMaster] |
| Combined Report | test_routing_transformation[DOC_Combined] |
| Summary | test_all_transformations_summary |

---

**Test Suite Name: Data Validation**  
**Function:** This suite verifies Compass handling of edge cases in DICOM data including blank fields, missing tags, and special characters. Tests document expected behavior for IIMS accession number generation and study date population.  
**Type:** New  
**Automation:** `tests/test_data_validation.py`

| Sub Test Suite | Test Case(s) |
|---|---|
| Study Date Handling | test_populate_blank_study_date, test_preserve_existing_study_date |
| Accession Number | test_iims_accession_number_generation, test_pass_device_accession_number, test_accession_number_edge_cases |
| Patient Demographics | test_blank_patient_name_handling, test_special_characters_in_patient_data |
| Required Tags | test_missing_modality_tag |

---

**Test Suite Name: Regression**  
**Function:** This suite will ensure that the overall system is functioning. Includes anonymization workflow verification and end-to-end send validation.  
**Type:** New  
**Automation:** `tests/test_anonymize_and_send.py`

| Sub Test Suite | Test Case(s) |
|---|---|
| Anonymization Workflow | test_anonymize_and_send_single_file |
| Shared Drive Integration | test_anonymize_and_send_from_shared_drive |

---

**Test Suite Name: Performance**  
**Function:** This suite will include test cases that verify throughput and performance requirements of Laurel Bridge. Performance tests simulate multiple concurrent scanner connections using ThreadPoolExecutor with configurable concurrency. The automation script logs and Compass Router logs will be used to measure end-to-end ingestion times for image upload.  
**Type:** New  
**Automation:** `tests/test_load_stability.py`, `tests/test_routing_throughput.py`

| Sub Test Suite | Test Case(s) |
|---|---|
| Load Stability | test_load_stability_3x_peak (3x peak load for configurable duration) |
| Throughput | test_routing_throughput_under_peak_plus[1.5] (150% of peak), test_routing_throughput_under_peak_plus[2.0] (200% of peak) |

**Performance Thresholds (configurable via environment):**
- MAX_ERROR_RATE: 2% (default)
- MAX_P95_LATENCY_MS: 2000ms for stability tests
- MAX_P95_LATENCY_MS_SHORT: 1500ms for throughput tests
- TEST_DURATION_SECONDS: 300s default, scalable to 172800s (48 hours) for soak tests

---

**Test Suite Name: Failover**  
**Function:** This suite will verify that stopping the Compass Service on a node causes traffic to reroute to backup nodes. Tests validate system behavior under failure conditions including delays, duplicates, and network variability.  
**Type:** New  
**Automation:** `tests/test_failure_modes.py`

| Sub Test Suite | Test Case(s) |
|---|---|
| Delay Tolerance | test_send_with_2min_pause_between_files, test_mcie_slow_send_one_at_a_time |
| Duplicate Handling | test_send_duplicate_study_multiple_times, test_resend_after_modifications |
| Network Resilience | test_send_with_variable_delays |
| Connectivity Check | test_connectivity_before_failure_tests |

---

## 4.0 Test Environment

### 4.1 Tools

- Google Chrome
- Azure DevOps (ADO)
  - https://dev.azure.com/mclm
  - Project: Digital Pathology - PACS
  - Area Path: Digital Pathology - PACS\Laurel Bridge DP
- MicroDICOM Viewer
  - Version (Build) 64-Bit ()
- **Python-based Test Automation Framework:**
  - **pynetdicom**: DICOM networking (C-STORE, C-ECHO, C-FIND)
  - **pydicom**: DICOM file parsing and manipulation
  - **pytest**: Test framework with markers and fixtures
  - **python-dotenv**: Environment variable management
  - **pylibjpeg + pillow**: Automatic DICOM decompression (JPEG, JPEG 2000, RLE)
  - For functional, integration, and performance testing
  - Multi-threaded transmission via ThreadPoolExecutor
  - Thread-safe metrics collection (latency, throughput, error rates)
- Compass Client (Thick Client)

### 4.2 Test Environment

- Laurel Bridge TEST (QA) Environment will be used for SQA testing
- Lighthouse Application Login:
- Compass Routers:
  - [Placeholders for specific server addresses]
- Software Versions
  - Laurel Bridge
    - Compass is
    - Lighthouse is

**Automation Framework Configuration (via .env or environment variables):**

| Variable | Description | Default |
|---|---|---|
| COMPASS_HOST | Hostname or IP of Compass DICOM listener | 127.0.0.1 |
| COMPASS_PORT | DICOM port | 11112 |
| COMPASS_AE_TITLE | AE Title of Compass (called AET) | COMPASS |
| LOCAL_AE_TITLE | AE Title used by load generator (calling AET) | PERF_SENDER |
| DICOM_ROOT_DIR | Directory containing DICOM files to replay | ./dicom_samples |
| PEAK_IMAGES_PER_SECOND | Historical peak rate (images per second) | 50 |
| LOAD_MULTIPLIER | Multiplicative factor for stress testing | 3.0 |
| LOAD_CONCURRENCY | Number of worker threads | 8 |
| TEST_DURATION_SECONDS | Duration of each test in seconds | 300 |
| MAX_ERROR_RATE | Allowed error rate fraction | 0.02 |
| MAX_P95_LATENCY_MS | p95 latency bound for stability tests (ms) | 2000 |
| MAX_P95_LATENCY_MS_SHORT | p95 latency bound for throughput tests (ms) | 1500 |

**PC used for testing ()**
- Windows 11 Enterprise
- Python 3.9 or later

### 4.3 Test Environment vs. Production Environment

| Aspect | Test Environment | Production Environment |
|---|---|---|
| Compass Servers | TEST cluster | PROD cluster with load balancer |
| Destinations | MIDIA-TEST, InfinityView-TEST | MIDIA, InfinityView |
| Data | Anonymized/Synthetic DICOM | Real patient data |
| Load Profile | Simulated peak loads | Actual clinical workflow |
| Monitoring | Lighthouse TEST | Lighthouse PROD |

---
