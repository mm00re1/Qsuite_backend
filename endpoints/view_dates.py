from fastapi import APIRouter
from fastapi.responses import JSONResponse
from datetime import timedelta
import json
import time
import fcntl
import logging
import os
from models.models import SessionLocal, TestResult
from config.config import CACHE_PATH

logger = logging.getLogger(__name__)

router = APIRouter()

def write_cache_to_disk(cache):
    # Open the file and acquire an exclusive lock (blocking)
    with open(CACHE_PATH, 'w') as cache_file:
        fcntl.flock(cache_file, fcntl.LOCK_EX)  # Acquire an exclusive lock
        try:
            json.dump(cache, cache_file)  # Write cache to file
        finally:
            fcntl.flock(cache_file, fcntl.LOCK_UN)

def load_cache_from_disk():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH, 'r') as cache_file:
            return json.load(cache_file)
    return None

def initialize_cache():
    start_time = time.time()
    cache = {
        'start_date': None,
        'latest_date': None,
        'missing_dates': []
    }
    session = SessionLocal()
    try:
        unique_dates_query = session.query(TestResult.date_run.distinct().label('date_run')).order_by(TestResult.date_run)
        unique_dates = [date[0] for date in unique_dates_query]


        if unique_dates:
            cache['start_date'] = unique_dates[0]
            cache['latest_date'] = unique_dates[-1]
            
            all_dates = set(cache['start_date'] + timedelta(days=x) for x in range((cache['latest_date'] - cache['start_date']).days + 1))
            cache['missing_dates'] = sorted(all_dates - set(unique_dates))

            cache['start_date'] = cache['start_date'].strftime('%Y-%m-%d')
            cache['latest_date'] = cache['latest_date'].strftime('%Y-%m-%d')
            cache['missing_dates'] = [date.strftime('%Y-%m-%d') for date in cache['missing_dates']]
        
        write_cache_to_disk(cache)
    finally:
        session.close()
    
    print("Cache initialized in:", time.time() - start_time, "seconds")


@router.post("/refresh_cache/")
async def refresh_cache():
    logger.info("refreshing cache")
    initialize_cache()
    return {"message": "Cache refreshed successfully."}


@router.get("/get_unique_dates/")
async def get_unique_dates():
    logger.info("getting unique dates")
    disk_cache = load_cache_from_disk()

    if disk_cache:
        return JSONResponse(content={
            "start_date": disk_cache['start_date'],
            "latest_date": disk_cache['latest_date'],
            "missing_dates": disk_cache['missing_dates']
        })

    else:
        return JSONResponse(content={"start_date": None, "latest_date": None, "missing_dates": []})
    
