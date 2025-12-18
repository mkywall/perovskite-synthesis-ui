from fastapi import APIRouter, HTTPException
from models import (
    BatchResolveRequest,
    BatchResolveResponse,
    BatchCreateRequest,
    BatchCreateResponse,
    BatchMatch
)
import logging
import os
from dotenv import load_dotenv

from pycrucible import CrucibleClient
from pycrucible.models import BaseDataset
from pycrucible.utils import get_tz_isoformat


logger = logging.getLogger(__name__)
router = APIRouter()

load_dotenv()
crucible_url = "https://crucible.lbl.gov/testapi"
admin_apikey = os.environ.get('ADMIN_APIKEY')
client = CrucibleClient(crucible_url, admin_apikey)
logger.info(f"Crucible client initialized with URL: {crucible_url}")


def resolve_batch_id(batch_id_input, orcid, project):
    if not batch_id_input or not batch_id_input.strip():
        return {'status': 'resolved', 'batch_id': None}

    batch_id_input = batch_id_input.strip()
    logger.debug(f"Resolving batch ID: {batch_id_input}")

    # First try to get by unique_id
    try:
        batch = client.get_sample(batch_id_input)
        if batch:
            logger.debug(f"Batch found by unique_id: {batch}")
            return {'status': 'resolved', 'batch_id': batch_id_input}
    except:
        pass

    # If not found by unique_id, try by sample name
    batches_by_name = client.list_samples(sample_name=batch_id_input)

    if len(batches_by_name) == 0:
        logger.debug(f"No batch found with name: {batch_id_input}")
        return {'status': 'not_found', 'input': batch_id_input}
    elif len(batches_by_name) == 1:
        resolved_id = batches_by_name[0]['unique_id']
        logger.debug(f"Batch resolved to unique_id: {resolved_id}")
        return {'status': 'resolved', 'batch_id': resolved_id}
    else:
        logger.debug(f"Multiple batches found with name: {batch_id_input}")
        return {'status': 'multiple_matches', 'matches': batches_by_name, 'input': batch_id_input}


def create_batch_sample(batch_id, batch_name, description, orcid, project):
    """
    PLACEHOLDER: Replace with your actual batch creation logic

    Should:
    1. Call get_tz_isoformat() for timestamp
    2. Call client.add_sample() to create batch
    3. Return the created batch object with unique_id
    """
    today_date = get_tz_isoformat()
    new_batch = client.add_sample(
        sample_name=batch_id,
        description=description,
        creation_date=today_date,
        owner_orcid=orcid,
        project_id=project
    )
    return new_batch
    raise NotImplementedError("Replace with actual batch creation logic")


@router.post("/resolve", response_model=BatchResolveResponse)
async def resolve_batch(request: BatchResolveRequest):
    """
    Resolve a batch ID input to a unique_id.

    Flow:
    1. Receive batch_id input from frontend
    2. Call resolve_batch_id()
    3. Return resolution status:
       - 'resolved': Found unique batch
       - 'multiple_matches': Multiple batches found, user must choose
       - 'not_found': Batch doesn't exist, offer to create
    """
    try:
        logger.info(f"Resolving batch ID: {request.batch_id}")

        # TODO: Call your actual function here
        result = resolve_batch_id(request.batch_id, request.orcid, request.project)

        if result['status'] == 'resolved':
            return BatchResolveResponse(
                status='resolved',
                batch_id=result['batch_id'],
                message=f"Batch resolved to ID: {result['batch_id']}"
            )

        elif result['status'] == 'multiple_matches':
            matches = [
                BatchMatch(
                    unique_id=match['unique_id'],
                    sample_name=match.get('sample_name', ''),
                    description=match.get('description'),
                    creation_date=match.get('creation_date')
                )
                for match in result['matches']
            ]
            return BatchResolveResponse(
                status='multiple_matches',
                matches=matches,
                input=result['input'],
                message=f"Multiple batches found with name '{result['input']}'"
            )

        elif result['status'] == 'not_found':
            return BatchResolveResponse(
                status='not_found',
                input=result['input'],
                message=f"Batch '{result['input']}' not found"
            )

        else:
            raise ValueError(f"Unknown resolution status: {result['status']}")

    except Exception as e:
        logger.error(f"Batch resolution error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/create", response_model=BatchCreateResponse)
async def create_batch(request: BatchCreateRequest):
    """
    Create a new batch in the database.

    Flow:
    1. Receive batch details from frontend
    2. Call client.add_sample() to create batch
    3. Return created batch unique_id
    """
    try:
        logger.info(f"Creating new batch: {request.batch_name} (ID: {request.batch_id})")

        if not request.batch_name or not request.batch_id:
            raise ValueError("Batch name and ID are required")

        description = request.batch_description or f"Batch {request.batch_name}"

        # TODO: Call your actual function here
        new_batch = create_batch_sample(
            batch_id=request.batch_id,
            batch_name=request.batch_name,
            description=description,
            orcid=request.orcid,
            project=request.project
        )

        logger.info(f"Batch created with unique_id: {new_batch['unique_id']}")

        return BatchCreateResponse(
            success=True,
            unique_id=new_batch['unique_id'],
            message=f"Batch '{request.batch_name}' created successfully"
        )

    except Exception as e:
        logger.error(f"Batch creation error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
