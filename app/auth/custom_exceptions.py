from fastapi import HTTPException, status

class BadCredentialsException(HTTPException):
    def __init__(self, detail: str = "Bad credentials"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=detail
        )

class PermissionDeniedException(HTTPException):
    def __init__(self, detail: str = "Permission denied"):
        super().__init__(
            status_code=status.HTTP_403_FORBIDDEN, detail=detail
        )


class RequiresAuthenticationException(HTTPException):
    def __init__(self, detail: str = "Requires authentication"):
        super().__init__(
            status_code=status.HTTP_401_UNAUTHORIZED, detail=detail
        )


class UnableCredentialsException(HTTPException):
    def __init__(self, detail: str = "Unable to verify credentials"):
        super().__init__(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=detail
        )
