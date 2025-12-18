import os
from dotenv import load_dotenv
import logging
import pandas as pd
import numpy as np
import gspread
from google.auth import default
from google.oauth2.service_account import Credentials
from fastapi import APIRouter, HTTPException
from models import SynthesisFieldsResponse, SynthesisUploadRequest, SynthesisUploadResponse

from pycrucible import CrucibleClient
from pycrucible.models import BaseDataset
from pycrucible.utils import get_tz_isoformat


logger = logging.getLogger(__name__)
router = APIRouter()

# For now we use admin client, but future have ORCID login and set up client that way
RUN_ENV = os.getenv('RUN_ENV')
if RUN_ENV != 'cloud':
    load_dotenv()

crucible_url = "https://crucible.lbl.gov/testapi"
admin_apikey = os.environ.get('ADMIN_APIKEY')
client = CrucibleClient(crucible_url, admin_apikey)
logger.info(f"Crucible client initialized with URL: {crucible_url}")

# Google Sheets configuration
GOOGLE_SHEETS_ID = os.environ.get('GOOGLE_SHEETS_ID')
GOOGLE_SERVICE_ACCOUNT_FILE = os.environ.get('GOOGLE_SERVICE_ACCOUNT_FILE')

# =============================================================================
# SYNTHESIS DATASET FIELD DEFINITIONS
# =============================================================================

SYNTHESIS_FIELDS = {
    "Solid Precursor": [
        "Sample Name", "Sample Description", "Notes", "CAS", "RFID", "Name", "Abbrev",
        "Vendor", "Opened Timestamp", "Storage Location"
    ],
        "Stock Solution": [
        "Sample Name", "Sample Description", "Notes", "Organic Salt SP-ID", "Organic Salt Name",
        "Organic Cation Actual Weight mg", "Metal Salt SP-ID", "Metal Salt Name",
        "Metal Cation Actual Weight mg", "Solvent", "Solvent Volume ml",
        "Target Concentration mol", "Storage Location"
    ],
    
    "Precursor Solution": [
        "Sample Name", "Sample Description", "Notes", "Target Stoichiometry", "Component A SS-ID",
        "Component B SS-ID", "Mixing Ratio", "Target Concentration (M)",
        "Storage Location", "PS Autobot Recipe Filename"
    ],

    "Thin Film": [
        "Sample Name", "Sample Description", "Substrate Cleaning Operator", "Substrate", "Scribed", "Substrate Cleaning",
        "Substrate Cleaning Timestamp", "Substrate Prep", "Substrate Prep Timestamp",
        "PS ID", "Spin Atmosphere", "Annealing Atmosphere"
    ]
}

# =============================================================================
# GOOGLE SHEETS CONFIGURATION (Based on SampleOverview.xlsx format)
# =============================================================================

SHEET_CONFIG = {
    "Solid Precursor": {
        "sheet_name": "SolidPrecursors",
        "section_header": "Solid Precursor Synthesis Dataset",
        "columns": [
            "SolidPrecursorID", "OperatorName", "TimeStamp", "Notes", "CAS", "RFID",
            "Name", "Abbrev", "Vendor", "OpenedTimestamp", "StorageLocation",
            "NMR_ID", "PhotoID"
        ]
    },
    "Stock Solution": {
        "sheet_name": "StockSolutions",
        "section_header": "Stock Solution Synthesis Dataset",
        "columns": [
            "StockSolutionID", "OperatorName", "TimeStamp", "Notes",
            "OrganicSalt_SP-ID", "OrganicSalt_Name", "OrganicCation_ActualWeight_mg",
            "MetalSalt_SP-ID", "MetalSalt_Name", "MetalCation_ActualWeight_mg",
            "Solvent", "SolventVolume_ml", "TargetConcentration_mol",
            "StorageLocation", "Photo_ID"
        ]
    },
    "Precursor Solution": {
        "sheet_name": "PrecursorSolutions",
        "section_header": "Precursor Solution Synthesis Dataset",
        "columns": [
            "PrecursorSolutionID", "OperatorName", "TimeStamp", "Notes",
            "TargetStoichiometry", "ComponentA_SS-ID", "ComponentB_SS-ID",
            "MixingRatio", "TargetConcentration (M)", "StorageLocation",
            "PSAutobotRecipeFilename", "Photo_ID"
        ]
    },
    "Thin Film": {
        "sheet_name": "ThinFilms",
        "section_headers": ["Substrate Dataset", "Thin Film Deposition Dataset"],
        "columns": [
            "ThinFilmID", "SubstrateCleaningOperator", "Substrate", "Scribed",
            "SubstrateCleaning", "SubstrateCleaning_Timestamp", "DepositionOperatorName",
            "SubstratePrep", "SubstratePrepTimestamp", "SampleDescription",
            "BatchID", "BatchUUID", "PS_ID", "SpinAtmosphere", "AnnealingAtmosphere",
            "SpinHumidity", "AnnealingHumidity", "SolutionVolume", "SpinSpeed",
            "SpinAcceleration", "SpinDuration", "AnnealingTemp", "AnnealingDuration",
            "DepositionRecipe", "DepositionLogfile", "HumidityLog", "Photo_File",
            "Photo_ID", "XRD_File", "XRD_ID", "UV-Vis_File", "UV-Vis_ID",
            "GIWAXS_ID", "GIWAXS_TFChildID", "RGA_ID", "RGA_TFChildID"
        ]
    }
}

def initialize_google_sheet_tab(worksheet, dataset_type):
    """
    Initialize a Google Sheet tab with proper headers if empty.
    """
    # Check if sheet already has headers (more than 2 rows with data)
    all_values = worksheet.get_all_values()
    if len(all_values) > 2:
        logger.debug(f"Sheet '{dataset_type}' already initialized")
        return

    config = SHEET_CONFIG.get(dataset_type)
    if not config:
        logger.warning(f"No configuration found for dataset type: {dataset_type}")
        return

    # Clear the sheet first
    worksheet.clear()

    # Row 1: Section header(s) - will be merged
    section_row = ["", ""]  # Start with empty cells
    if "section_headers" in config:
        # For ThinFilms with multiple sections
        section_row.append(config["section_headers"][0])
        section_row.extend([""] * 4)  # Fill to column 7
        section_row.append(config["section_headers"][1])
    else:
        section_row.append(config["section_header"])

    worksheet.append_row(section_row)

    # Row 2: Column headers
    worksheet.append_row(config["columns"])

    # Merge cells for section headers
    if "section_headers" in config:
        # For ThinFilms: merge cells for both section headers
        worksheet.merge_cells(1, 3, 1, 7, merge_type='MERGE_ALL')
        worksheet.merge_cells(1, 8, 1, len(config["columns"]), merge_type='MERGE_ALL')
    else:
        # For other sheets: merge section header across all columns
        worksheet.merge_cells(1, 3, 1, len(config["columns"]), merge_type='MERGE_ALL')

    logger.info(f"Initialized Google Sheet tab '{config['sheet_name']}' with headers")

def add_sample(orcid, project, sample_name, description, batch_id):
    """
    Add a sample to the database and Google Sheet.

    Args:
        orcid: User's ORCID
        user_name: User's name
        project: Selected or new project name
        sample_name: Name of the sample
        description: Sample description
        batch_id: Optional batch ID

    Returns:
        dict: Sample information including uuid and timestamp
    """
    logger.debug(f"Adding sample to database: name={sample_name}, project={project}, orcid={orcid}")
    today_date = get_tz_isoformat()
    logger.debug(f"Adding sample via Crucible client...")
    new_samp = client.add_sample(sample_name = sample_name, description = description, creation_date = today_date, owner_orcid = orcid, project_id = project)
    logger.debug(f"Sample added to Crucible: {new_samp}")

    if batch_id:
        logger.debug(f"Linking sample to batch {batch_id}")
        client.link_samples(parent_id = batch_id, child_id = new_samp['unique_id'])

    return {
        'sample_name': sample_name,
        'description': description,
        'project': project,
        'batch_id': batch_id or "",
        'unique_id': new_samp['unique_id'],
        'timestamp': today_date
    }

def add_synthesis_dataset(orcid, project, ds_record, synthesis_type, user_name, session_name = None):
    """
    Add synthesis dataset to the database and Google Sheet.

    Args:
        orcid: User's ORCID
        project: Selected or new project name
        ds_record: Dictionary with synthesis data and sample info
        today_date: Timestamp string
        synthesis_type: Type of synthesis dataset
        user_name: User's full name
        session_name: Optional session name

    Returns:
        str: Success or error message
    """
    sample_name = ds_record['sample_name']
    dataset_name = f'{synthesis_type} recipe for {sample_name}'
    ds_obj = BaseDataset(dataset_name = dataset_name,
                        public = False,
                        owner_orcid = orcid,
                        project_id = project,
                        measurement = f"{synthesis_type} synthesis",
                        session_name = session_name,
                        creation_time = ds_record['timestamp'])

    # Create keywords list, filtering out None values
    keywords = [k for k in [synthesis_type, sample_name, session_name] if k is not None]
    new_ds = client.create_new_dataset(ds_obj, scientific_metadata = ds_record, keywords = keywords)
    found_samples = client.list_samples(sample_name = sample_name)
    if len(found_samples) == 0:
        raise Exception(f'Sample with name {sample_name} not found')
    elif len(found_samples) > 1:
        raise Exception(f'Multiple samples with name {sample_name} were found: {found_samples}')
    else:
        sample = found_samples[-1]

    client.add_dataset_to_sample(dataset_id = new_ds['created_record']['unique_id'], sample_id = sample['unique_id'])

    # update spreadsheet
    ds_record['dsid'] = new_ds['created_record']['unique_id']
    add_dataset_to_google_sheet(synthesis_type, ds_record, user_name)

    return 

def add_dataset_to_google_sheet(dataset_type, ds_record, user_name):
    """
    Add dataset rows to the appropriate Google Sheet tab with SampleOverview.xlsx format.
    Creates the sheet and initializes headers if it doesn't exist.

    Args:
        dataset_type: Type of dataset (Solid Precursor, Precursor Solution, etc.)
        ds_record: Dictionary with dataset record to add
        user_name: User's full name
        today_date: ISO format timestamp

    Returns:
        None

    Raises:
        Exception: If Google Sheets configuration is missing or API call fails
    """
    logger.debug(f"Adding synthesis info to Google Sheet: {dataset_type} for {ds_record}")
    if not GOOGLE_SHEETS_ID or (not GOOGLE_SERVICE_ACCOUNT_FILE and RUN_ENV != 'cloud'):
        error_msg = "Google Sheets configuration missing. Please set GOOGLE_SHEETS_ID and GOOGLE_SERVICE_ACCOUNT_FILE in .env file"
        logger.error(error_msg)
        raise Exception(error_msg)

    # Set up credentials and authorize
    logger.debug(f"Authorizing with Google Sheets API using service account")
    scopes = ['https://www.googleapis.com/auth/spreadsheets']
    if RUN_ENV != 'cloud':
        credentials = Credentials.from_service_account_file(GOOGLE_SERVICE_ACCOUNT_FILE, scopes=scopes)
    else:
        credentials, project = default(scopes=scopes)
    gc = gspread.authorize(credentials)

    # Open the spreadsheet
    logger.debug(f"Opening spreadsheet with ID: {GOOGLE_SHEETS_ID}")
    spreadsheet = gc.open_by_key(GOOGLE_SHEETS_ID)

    # Get configuration for this dataset type
    config = SHEET_CONFIG.get(dataset_type)
    if not config:
        raise ValueError(f"Unknown dataset type: {dataset_type}")

    sheet_name = config["sheet_name"]

    # Get or create the worksheet
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
        logger.debug(f"Found worksheet: {sheet_name}")
    except gspread.exceptions.WorksheetNotFound:
        logger.info(f"Creating new worksheet: {sheet_name}")
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=100, cols=len(config["columns"]))

    # Initialize headers if needed
    initialize_google_sheet_tab(worksheet, dataset_type)

    # Helper function to safely get values
    def get_val(key):
        # Try lowercase version of the key
        val = ds_record.get(key.lower().replace(' ', '_').replace('-', '-'))
        if val is None:
            # Try exact key match
            val = ds_record.get(key)
        return str(val) if val is not None and val != '' else ""

    # Build row data based on dataset type and column order
    row_data = []

    if dataset_type == "Solid Precursor":
        row_data = [
            get_val('sample_name'),
            user_name,
            get_val('timestamp'),
            get_val('notes'),
            get_val('cas'),
            get_val('rfid'),
            get_val('name'),
            get_val('abbrev'),
            get_val('vendor'),
            get_val('opened_timestamp'),
            get_val('storage_location'),
            "",  # NMR_ID
            ""   # PhotoID
        ]
    elif dataset_type == "Stock Solution":
        row_data = [
            get_val('sample_name'),
            user_name,
            get_val('timestamp'),
            get_val('notes'),
            get_val('organic_salt_sp-id'),
            get_val('organic_salt_name'),
            get_val('organic_cation_actual_weight_mg'),
            get_val('metal_salt_sp-id'),
            get_val('metal_salt_name'),
            get_val('metal_cation_actual_weight_mg'),
            get_val('solvent'),
            get_val('solvent_volume_ml'),
            get_val('target_concentration_mol'),
            get_val('storage_location'),
            ""  # Photo_ID
        ]
    elif dataset_type == "Precursor Solution":
        row_data = [
            get_val('sample_name'),
            user_name,
            get_val('timestamp'),
            get_val('notes'),
            get_val('target_stoichiometry'),
            get_val('component_a_ss-id'),
            get_val('component_b_ss-id'),
            get_val('mixing_ratio'),
            get_val('target_concentration_(m)'),
            get_val('storage_location'),
            get_val('ps_autobot_recipe_filename'),
            ""  # Photo_ID
        ]
    elif dataset_type == "Thin Film":
        row_data = [
            get_val('sample_name'),
            get_val('substrate_cleaning_operator'),
            get_val('substrate'),
            get_val('scribed'),
            get_val('substrate_cleaning'),
            get_val('substrate_cleaning_timestamp'),
            user_name,  # DepositionOperatorName
            get_val('substrate_prep'),
            get_val('substrate_prep_timestamp'),
            get_val('sample_description'),
            "",  # BatchID
            "",  # BatchUUID
            get_val('ps_id'),
            get_val('spin_atmosphere'),
            get_val('annealing_atmosphere'),
            "",  # SpinHumidity
            "",  # AnnealingHumidity
            "",  # SolutionVolume
            "",  # SpinSpeed
            "",  # SpinAcceleration
            "",  # SpinDuration
            "",  # AnnealingTemp
            "",  # AnnealingDuration
            "",  # DepositionRecipe
            "",  # DepositionLogfile
            "",  # HumidityLog
            "",  # Photo_File
            "",  # Photo_ID
            "",  # XRD_File
            "",  # XRD_ID
            "",  # UV-Vis_File
            "",  # UV-Vis_ID
            "",  # GIWAXS_ID
            "",  # GIWAXS_TFChildID
            "",  # RGA_ID
            ""   # RGA_TFChildID
        ]
    else:
        raise ValueError(f"Unsupported dataset type: {dataset_type}")

    worksheet.append_row(row_data)

    logger.info(f"Successfully added {ds_record.get('sample_name', 'unknown')} to Google Sheet tab '{sheet_name}'")


def link_to_parent_by_name(ds_record, parent_field, project, sample_id):
    parent_sample = ds_record[parent_field]
    if parent_sample is None:
        return
    else:
        print(parent_sample)
    samples_with_parent_name = client.list_samples(sample_name = parent_sample, project_id = project)
    
    if len(samples_with_parent_name) == 1:
        parent_sample_id = samples_with_parent_name[-1]['unique_id']
        client.link_samples(parent_sample_id, sample_id)
        status = 'Success'
    elif len(samples_with_parent_name) > 1:
        # TODO: prompt user to select sample they meant
        status = 'Multiple parents found'
    else:
        # TODO: prompt user to create parent
        status = 'Parent not found'
    return status



def upload_all_sample_synthesis_info(orcid, project, dataset_df, synthesis_type, batch_id, user_name, session_name=None):
    logger.debug(f"Adding {len(dataset_df)} rows of {synthesis_type} dataset to project {project}")
    today_date = get_tz_isoformat()

    # Add to Crucible database
    dataset_df = dataset_df.replace('', np.nan).dropna(how = 'all')
    dataset_df = dataset_df.replace(np.nan, None)
    dataset_df.columns = [x.lower().replace(' ', '_') for x in dataset_df.columns]
    ds_dictionaries = dataset_df.to_dict('records')

    success_count = 0
    failed_count = 0
    error_messages = []

    for record in ds_dictionaries:
        try:
            new_samp = add_sample( orcid = orcid,
                                   project = project,
                                   sample_name = record['sample_name'],
                                   description = record['sample_description'],
                                   batch_id = batch_id)
            sample_uuid = new_samp['unique_id']

            if synthesis_type == 'Stock Solution':
                # link to SP
                print(record)
                link_to_parent_by_name(record, 'organic_salt_sp-id', project, sample_uuid)
                link_to_parent_by_name(record, 'metal_salt_sp-id', project, sample_uuid)


            if synthesis_type == 'Precursor Solution':
                # link to SS
                print(record)
                link_to_parent_by_name(record, 'component_a_ss-id', project, sample_uuid)
                link_to_parent_by_name(record, 'component_b_ss-id', project, sample_uuid)
                
            add_synthesis_dataset(orcid, project, record, synthesis_type, user_name, session_name)
            success_count += 1

        except Exception as err:
            failed_count += 1
            sample_name = record.get('sample_name', 'Unknown')
            error_msg = f"Sample '{sample_name}': {str(err)}"
            error_messages.append(error_msg)
            logger.error(f"dataset upload failed for {record} with error: {err}")

    summary = {
        "Project": project,
        "Synthesis Type": synthesis_type,
        "Samples Uploaded": success_count,
        "Failed": failed_count,
        "Total Rows": len(ds_dictionaries)
    }
    
    if error_messages:
        summary["Errors"] = error_messages

    # Generate appropriate status message based on results
    if failed_count == 0 and success_count > 0:
        status_msg = f"Successfully uploaded {success_count} samples to project '{project}'"
    elif success_count == 0 and failed_count > 0:
        status_msg = f"Upload failed: All {failed_count} samples failed to upload"
    elif success_count > 0 and failed_count > 0:
        status_msg = f"Partial upload: {success_count} samples uploaded successfully, {failed_count} failed"
    else:
        status_msg = f"No samples to upload"

    return status_msg, summary

@router.get("/fields", response_model=SynthesisFieldsResponse)
async def get_synthesis_fields():
    """
    Return the SYNTHESIS_FIELDS dictionary for the frontend.

    Flow:
    1. Frontend requests available synthesis types and their fields
    2. Return SYNTHESIS_FIELDS dictionary
    """
    try:
        logger.info("Fetching synthesis fields")
        return SynthesisFieldsResponse(fields=SYNTHESIS_FIELDS)
    except Exception as e:
        logger.error(f"Error fetching synthesis fields: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload", response_model=SynthesisUploadResponse)
async def upload_synthesis_data(request: SynthesisUploadRequest):
    """
    Upload synthesis data to database and Google Sheets.

    Flow:
    1. Receive synthesis data from frontend (array of row objects)
    2. Convert to DataFrame
    3. Call upload_all_sample_synthesis_info()
    4. Return success/failure summary
    """
    try:
        logger.info(f"Upload request: {request.synthesis_type} for project {request.project}")
        logger.info(f"Data rows: {len(request.data)}")

        # Convert array of objects to DataFrame
        if not request.data or len(request.data) == 0:
            return SynthesisUploadResponse(
                success=False,
                message="No data provided for upload"
            )

        # Create DataFrame from the data
        df = pd.DataFrame(request.data)

        # TODO: Call your actual function here
        status_msg, summary = upload_all_sample_synthesis_info(
                                    orcid=request.orcid,
                                    project=request.project,
                                    dataset_df=df,
                                    synthesis_type=request.synthesis_type,
                                    batch_id=request.batch_id,
                                    user_name=request.user_name,
                                    session_name=request.session_name
                                )

        logger.info(f"Upload completed: {status_msg}")

        return SynthesisUploadResponse(
            success=True,
            message=status_msg,
            summary=summary
        )

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
