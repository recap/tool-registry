import time
import asyncio

from fastapi import APIRouter, HTTPException
from typing import Dict
# In-memory job store for background tasks (if needed in future extensions)
# replace for production with a persistent store as needed
JOB_STORE: Dict[str, Dict] = {}

router = APIRouter()


async def clean_db():
    """Cleans up old jobs from the JOB_STORE."""
    now = time.time()
    to_delete = []
    for job_id, job in JOB_STORE.items():
        if now - job["timestamp"] > 3600:  # 1 hour expiration
            to_delete.append(job_id)
    for job_id in to_delete:
        del JOB_STORE[job_id]

async def periodic_housekeeping():
    while True:
        await clean_db()
        await asyncio.sleep(60)

# Start the periodic housekeeping task
asyncio.get_running_loop().create_task(periodic_housekeeping())



@router.get("/{job_id}", description="Check the status of a search job.")
async def get_job_status(job_id: str) -> dict:
    job = JOB_STORE.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job

