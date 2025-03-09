from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import os
from encryption_utils import save_credentials, load_credentials

router = APIRouter()

class ConnectionCredentialsInput(BaseModel):
    method: str
    username: str = None
    password: str = None
    tenant_id: str = None
    client_id: str = None
    client_secret: str = None
    # Add additional fields as needed

@router.post("/store_credentials/")
async def store_credentials(credentials: ConnectionCredentialsInput):
    # Validate input
    if credentials.method not in ['User/Password', 'Azure Oauth']:
        raise HTTPException(status_code=400, detail="Invalid connection method.")
    
    credentials_data = credentials.dict()
    # Remove None values
    credentials_data = {k: v for k, v in credentials_data.items() if v is not None}

    try:
        save_credentials(credentials_data)
        return {"message": "Credentials stored securely."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_credentials/")
async def get_credentials():
    try:
        credentials = load_credentials()
        return credentials
    except FileNotFoundError:
        return {"method": "User/Password"}
        #raise HTTPException(status_code=404, detail="Credentials not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/get_connect_method/")
async def get_connect_method():
    try:
        credentials = load_credentials()
        return credentials["method"]
    except FileNotFoundError:
        return "User/Password"
        #raise HTTPException(status_code=404, detail="Credentials not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

