import os
from dotenv import load_dotenv
import logging
import pandas as pd
import numpy as np
from fastapi import APIRouter, HTTPException
from models import SynthesisFieldsResponse, SynthesisUploadRequest, SynthesisUploadResponse

from crucible import CrucibleClient
from crucible.models import BaseDataset
from crucible.utils import get_tz_isoformat

# Chem Utils
from rdkit import Chem
from rdkit import RDLogger


def canonical(smi):
    """Return canonical SMILES, or None if parsing fails or input is empty."""
    if not isinstance(smi, str) or not smi.strip():
        return None
    mol = Chem.MolFromSmiles(smi)
    if mol is None:
        return None
    return Chem.MolToSmiles(mol)


logger = logging.getLogger(__name__)
router = APIRouter()

RUN_ENV = os.getenv('RUN_ENV')
if RUN_ENV != 'cloud':
    load_dotenv()

crucible_url = "https://crucible.lbl.gov/api/v2"
admin_apikey = os.environ.get('ADMIN_APIKEY')
client = CrucibleClient(crucible_url, admin_apikey)
logger.info(f"Crucible client initialized with URL: {crucible_url}")

# =============================================================================
# SYNTHESIS DATASET FIELD DEFINITIONS
# =============================================================================

SYNTHESIS_FIELDS = {
    "Solid Precursor": [
        "Sample Name", "Sample Description", "Notes", "CAS", "RFID", "Name", "SMILES", "Abbrev",
        "Vendor", "Opened Timestamp", "Storage Location", 'NMR_ID'
    ],
    "Stock Solution": [
        "Sample Name", "Sample Description", "Notes", "Organic Salt SP-ID", "Organic Salt Name",
        "Organic Cation Actual Weight mg", "Metal Salt SP-ID", "Metal Salt Name",
        "Metal Cation Actual Weight mg", "Solvent", "Solvent Volume ml",
        "Target Concentration mol", "Storage Location"
    ],
    "Precursor Solution": [
        "Sample Name", "Sample Description", "Notes", "Target Stoichiometry", "Component A SS-ID",
        "Component B SS-ID", "SMILES_Organic", "SMILES_Metal", "Mixing Ratio", "Target Concentration (M)",
        "Storage Location", "PS Autobot Recipe Filename"
    ],
}


def add_sample(orcid, project, sample_name, description, sample_type=None):
    logger.debug(f"Adding sample to database: name={sample_name}, project={project}, orcid={orcid}")
    today_date = get_tz_isoformat()
    new_samp = client.add_sample(sample_name=sample_name, sample_type=sample_type, description=description,
                                 creation_date=today_date, owner_orcid=orcid, project_id=project)
    logger.debug(f"Sample added to Crucible: {new_samp}")
    return {
        'sample_name': sample_name,
        'description': description,
        'project': project,
        'unique_id': new_samp['unique_id'],
        'timestamp': today_date
    }


def add_synthesis_dataset(orcid, project, ds_record, synthesis_type, user_name, session_name=None):
    sample_name = ds_record['sample_name']
    dataset_name = f'{synthesis_type} recipe for {sample_name}'
    ds_obj = BaseDataset(dataset_name=dataset_name,
                         public=False,
                         owner_orcid=orcid,
                         project_id=project,
                         measurement=f"{synthesis_type} synthesis",
                         session_name=session_name,
                         creation_time=ds_record['timestamp'])
    keywords = [k for k in [synthesis_type, sample_name, session_name] if k is not None]
    new_ds = client.create_new_dataset(ds_obj, scientific_metadata=ds_record, keywords=keywords)
    found_samples = client.list_samples(sample_name=sample_name, project_id=project)
    if len(found_samples) == 0:
        raise Exception(f'Sample with name {sample_name} not found')
    elif len(found_samples) > 1:
        raise Exception(f'Multiple samples with name {sample_name} were found: {found_samples}')
    else:
        sample = found_samples[-1]
    client.add_dataset_to_sample(dataset_id=new_ds['created_record']['unique_id'], sample_id=sample['unique_id'])


def link_to_parent_by_name(ds_record, parent_field, project, sample_id):
    parent_sample = ds_record[parent_field]
    if parent_sample is None:
        return
    samples_with_parent_name = client.list_samples(sample_name=parent_sample, project_id=project)
    if len(samples_with_parent_name) == 1:
        parent_sample_id = samples_with_parent_name[-1]['unique_id']
        client.link_samples(parent_sample_id, sample_id)
        return 'Success'
    elif len(samples_with_parent_name) > 1:
        return 'Multiple parents found'
    else:
        return 'Parent not found'


def upload_all_sample_synthesis_info(orcid, project, dataset_df, synthesis_type, user_name, session_name=None):
    logger.debug(f"Adding {len(dataset_df)} rows of {synthesis_type} dataset to project {project}")

    dataset_df = dataset_df.replace('', np.nan).dropna(how='all')
    dataset_df = dataset_df.replace(np.nan, None)
    dataset_df.columns = [x.lower().replace(' ', '_') for x in dataset_df.columns]
    ds_dictionaries = dataset_df.to_dict('records')

    success_count = 0
    failed_count = 0
    error_messages = []
    created_samples = []

    for record in ds_dictionaries:
        try:
            new_samp = add_sample(orcid=orcid, project=project,
                                  sample_name=record['sample_name'],
                                  description=record['sample_description'],
                                  sample_type=synthesis_type.lower())
            sample_uuid = new_samp['unique_id']
            created_samples.append({'sample_name': record['sample_name'], 'unique_id': sample_uuid})

            if synthesis_type == 'Stock Solution':
                link_to_parent_by_name(record, 'organic_salt_sp-id', project, sample_uuid)
                link_to_parent_by_name(record, 'metal_salt_sp-id', project, sample_uuid)

            if synthesis_type == 'Precursor Solution':
                link_to_parent_by_name(record, 'component_a_ss-id', project, sample_uuid)
                link_to_parent_by_name(record, 'component_b_ss-id', project, sample_uuid)

            canonical_updates = {f'{k}_canonical': canonical(v) for k,v in record.items() if 'smiles' in k.lower()}
            record.update(canonical_updates)
                
            add_synthesis_dataset(orcid, project, record, synthesis_type, user_name, session_name)
            success_count += 1

        except Exception as err:
            failed_count += 1
            sample_name = record.get('sample_name', 'Unknown')
            error_messages.append(f"Sample '{sample_name}': {str(err)}")
            logger.error(f"dataset upload failed for {record} with error: {err}")

    summary = {
        "Project": project,
        "Synthesis Type": synthesis_type,
        "Samples Uploaded": success_count,
        "Failed": failed_count,
        "Total Rows": len(ds_dictionaries),
        "Created Samples": created_samples
    }
    if error_messages:
        summary["Errors"] = error_messages

    if failed_count == 0 and success_count > 0:
        status_msg = f"Successfully uploaded {success_count} samples to project '{project}'"
    elif success_count == 0 and failed_count > 0:
        status_msg = f"Upload failed: All {failed_count} samples failed to upload"
    elif success_count > 0 and failed_count > 0:
        status_msg = f"Partial upload: {success_count} samples uploaded successfully, {failed_count} failed"
    else:
        status_msg = "No samples to upload"

    return status_msg, summary


@router.get("/fields", response_model=SynthesisFieldsResponse)
async def get_synthesis_fields():
    try:
        logger.info("Fetching synthesis fields")
        return SynthesisFieldsResponse(fields=SYNTHESIS_FIELDS)
    except Exception as e:
        logger.error(f"Error fetching synthesis fields: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload", response_model=SynthesisUploadResponse)
async def upload_synthesis_data(request: SynthesisUploadRequest):
    try:
        logger.info(f"Upload request: {request.synthesis_type} for project {request.project}")
        logger.info(f"Data rows: {len(request.data)}")

        if not request.data or len(request.data) == 0:
            return SynthesisUploadResponse(success=False, message="No data provided for upload")

        df = pd.DataFrame(request.data)
        status_msg, summary = upload_all_sample_synthesis_info(
            orcid=request.orcid,
            project=request.project,
            dataset_df=df,
            synthesis_type=request.synthesis_type,
            user_name=request.user_name,
            session_name=request.session_name
        )

        logger.info(f"Upload completed: {status_msg}")
        return SynthesisUploadResponse(success=True, message=status_msg, summary=summary)

    except Exception as e:
        logger.error(f"Upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
