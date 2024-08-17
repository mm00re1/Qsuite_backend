from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse
from datetime import timedelta
import time

from models.models import SessionLocal, TestResult

router = APIRouter()

cache = {
    'unique_dates': [],
    'start_date': None,
    'latest_date': None,
    'missing_dates': []
}

def initialize_cache():
    start_time = time.time()
    
    session = SessionLocal()
    try:
        unique_dates_query = session.query(TestResult.date_run.distinct().label('date_run')).order_by(TestResult.date_run)
        unique_dates = [date[0] for date in unique_dates_query]

        cache['unique_dates'] = unique_dates

        if unique_dates:
            cache['start_date'] = unique_dates[0]
            cache['latest_date'] = unique_dates[-1]
            
            all_dates = set(cache['start_date'] + timedelta(days=x) for x in range((cache['latest_date'] - cache['start_date']).days + 1))

            missing_dates = all_dates - set(unique_dates)
            cache['missing_dates'] = sorted(missing_dates)
    finally:
        session.close()
    
    print("Cache initialized in:", time.time() - start_time, "seconds")


@router.post("/refresh_cache/")
async def refresh_cache():
    initialize_cache()
    return {"message": "Cache refreshed successfully."}


@router.get("/get_unique_dates/")
async def get_unique_dates():
    if not cache['unique_dates']:
        return JSONResponse(content={"start_date": None, "latest_date": None, "missing_dates": []})
    
    start_date = cache['start_date']
    latest_date = cache['latest_date']
    missing_dates_str = [date.strftime('%Y-%m-%d') for date in cache['missing_dates']]

    print(start_date.strftime('%Y-%m-%d'))
    print(latest_date.strftime('%Y-%m-%d'))
    return JSONResponse(content={
        "start_date": start_date.strftime('%Y-%m-%d'),
        "latest_date": latest_date.strftime('%Y-%m-%d'),
        "missing_dates": missing_dates_str
    })
