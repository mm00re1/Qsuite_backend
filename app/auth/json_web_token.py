from dataclasses import dataclass
import jwt
from config.config import settings
from auth.custom_exceptions import BadCredentialsException, UnableCredentialsException
import requests

# Simple in-memory cache for JWKS
jwks_cache = {}

@dataclass
class JsonWebToken:
    jwt_access_token: str
    auth0_issuer_url: str = f"https://{settings.auth0_domain}/"
    auth0_audience: str = settings.auth0_audience
    algorithm: str = "RS256"

    def get_signing_key(self):
        # Extract 'kid' from the token header
        unverified_header = jwt.get_unverified_header(self.jwt_access_token)
        kid = unverified_header.get('kid')

        if not kid:
            raise BadCredentialsException("Invalid token header. 'kid' missing.")

        # Fetch JWKS if not cached or 'kid' not found in cached keys
        if 'jwks' not in jwks_cache or 'keys' not in jwks_cache['jwks'] or kid not in [key['kid'] for key in jwks_cache['jwks']['keys']]:
            self.refresh_jwks_cache()

        # Try to get the key matching the 'kid'
        for key in jwks_cache['jwks']['keys']:
            if key['kid'] == kid:
                try:
                    signing_key = jwt.algorithms.RSAAlgorithm.from_jwk(key)
                    return signing_key
                except Exception:
                    raise UnableCredentialsException("Unable to parse signing key.")

        raise BadCredentialsException("Unable to find matching key for 'kid'.")

    def refresh_jwks_cache(self):
        """Fetch JWKS from Auth0 and cache it."""
        jwks_uri = f"{self.auth0_issuer_url}.well-known/jwks.json"
        response = requests.get(jwks_uri)
        response.raise_for_status()  # Raise an exception if the request fails
        jwks_cache['jwks'] = response.json()

    def validate(self):
        try:
            signing_key = self.get_signing_key()
            payload = jwt.decode(
                self.jwt_access_token,
                signing_key,
                algorithms=[self.algorithm],
                audience=self.auth0_audience,
                issuer=self.auth0_issuer_url,
            )
            return payload

        except jwt.exceptions.PyJWKClientError:
            raise UnableCredentialsException
        except jwt.exceptions.InvalidTokenError:
            raise BadCredentialsException
