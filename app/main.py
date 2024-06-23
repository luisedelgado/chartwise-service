from fastapi import (Cookie, FastAPI)
from fastapi.middleware.cors import CORSMiddleware
from typing import Annotated, Union

from .internal import (library_clients, security)
from .routers import (assistant_router,
                      audio_processing_router,
                      image_processing_router)

app = FastAPI()

app.include_router(assistant_router.router)
app.include_router(audio_processing_router.router)
app.include_router(image_processing_router.router)

origins = [
    # Daniel Daza development
    "https://localhost:5173",
    library_clients.SPEECHMATICS_NOTIFICATION_IPS,
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

"""
Returns an OK status if the endpoint can be reached.

Arguments:
authorization – The authorization cookie, if exists.
"""
@app.get("/v1/healthcheck")
def read_healthcheck(authorization: Annotated[Union[str, None], Cookie()] = None):
    if not security.access_token_is_valid(authorization):
        raise security.TOKEN_EXPIRED_ERROR

    return {"status": "ok"}
