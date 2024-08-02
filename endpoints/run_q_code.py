from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.orm import Session

from models.models import TestGroup
from dependencies import get_db
from KdbSubs import *

router = APIRouter()

class QCodeRequest(BaseModel):
    code: List[str]
    group_id: int

@router.post("/execute_q_code/")
async def execute_q_code(request: QCodeRequest, db: Session = Depends(get_db)):
    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == request.group_id).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    try:
        kdbQuery = wrapQcode(request.code)
        result = sendFreeFormQuery(kdbQuery, test_group.server, test_group.port, test_group.tls, [])
        print(result)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Python Error => {str(e)}")


@router.get("/execute_q_function/")
async def execute_q_function(
    test_name: str,
    group_id: Optional[int] = None,
    db: Session = Depends(get_db)
):
    # Query the TestGroup table to get the server, port, and tls values
    test_group = db.query(TestGroup).filter(TestGroup.id == group_id).first()

    if not test_group:
        raise HTTPException(status_code=404, detail="TestGroup not found")

    try:
        result = sendFunctionalQuery(test_name, test_group.server, test_group.port, test_group.tls)
        print(result)
        return result
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Python Error => {str(e)}")
