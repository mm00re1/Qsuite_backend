from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from config import kdb_host, kdb_port
from KdbSubs import *

router = APIRouter()

class QCodeRequest(BaseModel):
    code: List[str]

@router.post("/execute_q_code/")
async def execute_q_code(request: QCodeRequest):
    try:
        kdbQuery = wrapQcode(request.code)
        result = sendFreeFormQuery(kdbQuery, kdb_host, kdb_port, [])
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Python Error => {str(e)}")

@router.get("/execute_q_function/")
async def execute_q_function(
    test_name: str,
    group_id: Optional[int] = None,
):
    try:
        result = sendFunctionalQuery(test_name, kdb_host, kdb_port)
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Python Error => {str(e)}")
