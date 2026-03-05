# ADO Test Case Uploader

Command-line tool that reads test cases from a CSV or Excel file and creates
Test Case work items in Azure DevOps via the REST API.

## Quick Start

```bash
# 1. Preview what will be uploaded (no API calls)
python3 upload_to_ado.py my_tests.xlsx --dry-run

# 2. Upload for real
python3 upload_to_ado.py my_tests.xlsx \
    --org https://dev.azure.com/your-org \
    --project YourProject \
    --pat YOUR_PERSONAL_ACCESS_TOKEN
```

## Prerequisites

- Python 3.10+
- Packages (already in `requirements.txt`):
  - `requests` -- ADO REST API calls
  - `openpyxl` -- Excel file reading
  - `python-dotenv` -- `.env` file loading (optional)

Install if needed:

```bash
pip install requests openpyxl python-dotenv
```

## Authentication

You need a **Personal Access Token (PAT)** from Azure DevOps with
**Work Items (Read & Write)** scope.

To create one: Azure DevOps > User Settings (top-right) > Personal access tokens > New Token.

Provide credentials in one of two ways:

### Option A: Environment variables in `.env`

Add these to your `.env` file:

```
ADO_ORG_URL=https://dev.azure.com/your-org
ADO_PROJECT=YourProject
ADO_PAT=your_pat_here
ADO_AREA_PATH=YourProject\Testing
```

Then simply run:

```bash
python3 upload_to_ado.py my_tests.xlsx
```

### Option B: Command-line flags

```bash
python3 upload_to_ado.py my_tests.xlsx \
    --org https://dev.azure.com/your-org \
    --project YourProject \
    --pat YOUR_PAT
```

## Input File Formats

The script accepts `.csv`, `.xlsx`, and `.xls` files. It auto-detects which
layout your file uses based on the column headers.

### Format A -- One Row Per Test Case (flat)

Best for Excel sheets where each row is a complete test case.

| Column | Required | Description |
|--------|----------|-------------|
| Title | Yes | Test case name |
| Priority | No | 1--4 (defaults to 2) |
| Area / Area Path | No | ADO area path |
| Description | No | Test case description |
| TestSteps | No | Numbered steps in one cell (see below) |
| Prerequisites | No | Preconditions |
| ExpectedResult | No | Overall expected outcome |
| ID | No | Your own tracking ID |
| Notes | No | Additional notes |

The **TestSteps** cell should contain numbered lines:

```
1. Open login page
2. Enter credentials
3. Click submit
4. Verify dashboard loads
```

Example CSV:

```
ID,Title,Area,Priority,Description,TestSteps,ExpectedResult
TC-001,Verify Login,Auth,1,User can log in,"1. Open login page
2. Enter credentials
3. Click submit",Dashboard loads
```

### Format B -- One Row Per Step (expanded)

Best when each test step is its own row. Rows with the same Title are grouped
into a single test case.

| Column | Required | Description |
|--------|----------|-------------|
| Title | Yes (first row of group) | Test case name |
| Work Item Type | No | Should be "Test Case" |
| Test Step | No | Step number |
| Step Action | Yes | What the tester does |
| Step Expected | No | Expected result for this step |
| Priority | No | 1--4 |
| Area Path | No | ADO area path |

Example CSV:

```
Work Item Type,Title,Priority,Area Path,Test Step,Step Action,Step Expected
Test Case,Verify Login,1,Auth,1,Open login page,Page loads
Test Case,Verify Login,1,Auth,2,Enter credentials,Fields populated
Test Case,Verify Login,1,Auth,3,Click submit,Dashboard loads
Test Case,Verify Logout,2,Auth,1,Click profile icon,Menu opens
Test Case,Verify Logout,2,Auth,2,Click logout,Login page shown
```

Column names are matched case-insensitively and ignore spaces/punctuation,
so `Step Action`, `StepAction`, and `step_action` all work.

## Usage

```
python3 upload_to_ado.py <file> [options]
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `<file>` | (required) | Path to CSV or Excel file |
| `--sheet NAME` | active sheet | Excel sheet name to read |
| `--org URL` | `ADO_ORG_URL` env | Azure DevOps organization URL |
| `--project NAME` | `ADO_PROJECT` env | Project name |
| `--pat TOKEN` | `ADO_PAT` env | Personal Access Token |
| `--area PATH` | `ADO_AREA_PATH` env | Default area path for test cases |
| `--plan-id ID` | none | Add created cases to this Test Plan |
| `--suite-id ID` | none | Add created cases to this Test Suite |
| `--dry-run` | off | Parse and print without calling the API |
| `--delay SECS` | 0.5 | Pause between API calls (rate limiting) |

### Examples

```bash
# Dry-run from Excel (preview only)
python3 upload_to_ado.py test_cases.xlsx --dry-run

# Read a specific sheet
python3 upload_to_ado.py test_cases.xlsx --sheet "Regression" --dry-run

# Upload from CSV
python3 upload_to_ado.py ADO_TEST_CASES_IMPORT_FIXED.csv

# Upload and add to a specific test suite
python3 upload_to_ado.py test_cases.xlsx \
    --plan-id 12345 \
    --suite-id 67890

# Set area path for all test cases
python3 upload_to_ado.py test_cases.xlsx --area "MyProject\QA\Routing"

# Faster uploads (reduce delay between API calls)
python3 upload_to_ado.py test_cases.xlsx --delay 0.2
```

## Environment Variables

All configuration can be set via environment variables or a `.env` file in the
project root. CLI flags override environment variables.

| Variable | Description |
|----------|-------------|
| `ADO_ORG_URL` | Organization URL, e.g. `https://dev.azure.com/myorg` |
| `ADO_PROJECT` | Project name |
| `ADO_PAT` | Personal Access Token |
| `ADO_AREA_PATH` | Default area path for new test cases |
| `ADO_TEST_PLAN_ID` | Test Plan ID (optional) |
| `ADO_TEST_SUITE_ID` | Test Suite ID (optional) |

See `env_template.txt` for a full template.

## What Gets Created in ADO

Each test case becomes an ADO work item of type **Test Case** with:

- **Title** -- from the Title column
- **Priority** -- from the Priority column (1-4)
- **Area Path** -- from the Area column or `--area` flag
- **Description** -- from the Description column
- **Steps** -- structured test steps with Action and Expected Result,
  visible in the ADO Test Case "Steps" tab

If `--plan-id` and `--suite-id` are provided, created test cases are
automatically added to the specified test suite.

## Dry-Run Output

The `--dry-run` flag parses the file and prints a summary without making any
API calls:

```
Reading sheet: 'Test Cases'
Detected format: A (flat, one row per test case)
Loaded 21 test case(s) from test_cases.xlsx

=== DRY RUN (no API calls) ===

  [1] Verify OPV GPA Visual Fields Routing
      Priority: 1  |  Area: Routing - Ophthalmology
      Description: Verify DICOM images with OPV modality...
      Steps: 12
        1. Open DICOM test file or create new DICOM file
        2. Set Modality tag to OPV
        ...

Total: 21 test cases with 260 steps.
```

Always run with `--dry-run` first to verify your file parses correctly
before uploading.

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `ModuleNotFoundError: openpyxl` | `pip install openpyxl` |
| `ModuleNotFoundError: requests` | `pip install requests` |
| 401 Unauthorized | Check PAT is valid and has Work Items scope |
| 404 Not Found | Verify `--org` URL and `--project` name |
| "Cannot detect CSV format" | Ensure header row contains `Title` and either `Description`/`TestSteps` (format A) or `Step Action` (format B) |
| Wrong sheet read from Excel | Use `--sheet "Sheet Name"` to specify |
| Area path errors | Use full path like `ProjectName\Area\SubArea` |
