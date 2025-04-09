from contextlib import asynccontextmanager
from fastapi import APIRouter, FastAPI, HTTPException, status, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from .internal.db.connection import connect_pool, disconnect_pool
from .internal.logging.logging_middleware import TimingMiddleware
from .data_processing.electra_model_data import ELECTRA_MODEL_CACHE_DIR, ELECTRA_MODEL_NAME

@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_pool(app)
    print("Loading model and tokenizer...")
    AutoTokenizer.from_pretrained(ELECTRA_MODEL_NAME,
                                  cache_dir=ELECTRA_MODEL_CACHE_DIR)
    AutoModelForSequenceClassification.from_pretrained(ELECTRA_MODEL_NAME,
                                                       cache_dir=ELECTRA_MODEL_CACHE_DIR)
    print("Finished loading model and tokenizer.")
    yield
    await disconnect_pool(app)
    print("Releasing model and tokenizer.")

class HSTSMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        try:
            response: Response = await call_next(request)
        except Exception as e:
            return JSONResponse(
                {"detail": "Internal server error in middleware."},
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        return response

class EndpointServiceCoordinator:

    origins = [
        # localhost
        "https://localhost:5173",
        # staging webapp
        "https://www.staging.api.chartwise.ai",
        "https://www.staging.app.chartwise.ai",
        "https://staging.api.chartwise.ai",
        "https://staging.app.chartwise.ai",
        # prod webapp
        "https://www.api.chartwise.ai",
        "https://www.app.chartwise.ai",
        "https://api.chartwise.ai",
        "https://app.chartwise.ai",
    ]

    def __init__(self, routers, environment):
        is_prod_environment = environment == "prod"
        openapi_url = "/openapi.json" if not is_prod_environment else None
        docs_url = "/docs" if not is_prod_environment else None
        redoc_url = "/redoc" if not is_prod_environment else None
        self.app = FastAPI(lifespan=lifespan,
                           title="ChartWise API Service",
                           openapi_url=openapi_url,
                           docs_url=docs_url,
                           redoc_url=redoc_url)
        self.app.add_middleware(
            CORSMiddleware,
            allow_origins=self.origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
        self.app.add_middleware(TimingMiddleware)
        self.app.add_middleware(HSTSMiddleware)
        self.environment = environment

        try:
            assert len(routers) > 0, "Did not receive any routers"

            for router in routers:
                assert type(router) is APIRouter, "Received invalid object instead of router"
                self.app.include_router(router)

        except Exception as e:
            raise HTTPException(detail=str(e), status_code=status.HTTP_500_INTERNAL_SERVER_ERROR)
