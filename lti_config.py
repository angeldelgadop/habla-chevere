from ltiauth.fastapi import LTIAuth
from fastapi import Depends

auth = LTIAuth(
    consumers={
        "your-key": "your-secret"
    }
)

def get_lti_user(user=Depends(auth)):
    return user
