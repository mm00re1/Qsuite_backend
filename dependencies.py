from sqlalchemy.orm import Session
from models.models import SessionLocal
from auth.authorization_header_elements import get_bearer_token
from auth.custom_exceptions import PermissionDeniedException
from fastapi import Depends
from auth.json_web_token import JsonWebToken

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def validate_token(token: str = Depends(get_bearer_token)):
    return JsonWebToken(token).validate()


class PermissionsValidator:
    def __init__(self, required_scopes: list[str]):
        self.required_scopes = required_scopes

    def __call__(self, token: dict = Depends(validate_token)):
        # Get the 'scope' from the token and split it into a list
        token_scopes = token.get("scope", "").split()  # Split the scope string into a list
        token_scopes_set = set(token_scopes)
        required_scopes_set = set(self.required_scopes)

        print("token_scopes_set: ", token_scopes_set)
        print("required_scopes_set: ", required_scopes_set)

        # Check if all required scopes are present in the token
        if not required_scopes_set.issubset(token_scopes_set):
            raise PermissionDeniedException
