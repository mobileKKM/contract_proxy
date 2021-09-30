import base64
import json
import os
import time

from datetime import datetime, timedelta
from io import BytesIO

import aiohttp
import aioredis
import zxingcpp

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, RedirectResponse

from PIL import Image
from pydantic import BaseModel, Required

# Ticket contract endpoint
CONTRACT_URL = "https://api.kkm.krakow.pl/api/v1/mkkm/tickets/{ticket_guid}/contract"

# Redis settings
REDIS_URL = os.getenv("REDIS_URL", "redis://user:sEcRet@localhost/")


class HTTPException(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ContractResponse(BaseModel):
    aztec: str
    valid_from: datetime


class ErrorResponse(BaseModel):
    message: str


app = FastAPI(
    debug=False,
    title="Ticket Contract Proxy",
    description="A microservice to decode AZTEC codes from mKKM to save bandwidth.",
    version="1.3",
    docs_url="/docs/",
    redoc_url=None
)

redis = aioredis.from_url(REDIS_URL, decode_responses=True)


@app.on_event("shutdown")
async def shutdown_event():
    await redis.close()


@app.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time
    response.headers["X-Process-Time"] = str(process_time)
    return response


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exception: HTTPException):
    """Returns exception as JSON response"""
    return JSONResponse(
        status_code=exception.status_code,
        content={"message": exception.message},
    )


@app.get("/", include_in_schema=False)
async def index():
    return RedirectResponse(
        status_code=301,
        url="https://mobilekkm.codebucket.de"
    )


@app.get("/ticket/{ticket_guid}/contract", response_model=ContractResponse, responses={
    400: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def get_contract(ticket_guid: str, authorization: str = Header(Required)):
    """Returns decoded AZTEC barcode data"""
    if await redis.exists(f"ticket:{ticket_guid}:contract"):
        return json.loads(await redis.get(f"ticket:{ticket_guid}:contract"))

    auth_headers = {
        "User-Agent": "mobileKKM/contract_proxy",
        "Authorization": authorization
    }

    async with aiohttp.ClientSession() as session:
        async with session.get(CONTRACT_URL.format(ticket_guid=ticket_guid), headers=auth_headers) as resp:
            data = await resp.json()

            if not resp.ok:
                raise HTTPException(status_code=resp.status, message=data["message"])

            try:
                image = Image.open(BytesIO(base64.b64decode(data["aztec"])))
                result = zxingcpp.read_barcode(image, formats=zxingcpp.Aztec, try_rotate=False)
            except ValueError as exc:
                raise HTTPException(status_code=500, message="Could not decode barcode from image.") from exc

            valid_from = datetime.utcnow().replace(second=0, microsecond=0)
            expires = (valid_from + timedelta(minutes=2)) - datetime.utcnow()

            contract = {
                "aztec": result.text,
                "valid_from": f"{valid_from.isoformat()}Z"
            }

            await redis.set(f"ticket:{ticket_guid}:contract", json.dumps(contract), ex=expires.seconds)
            return contract


@app.api_route("/healthcheck", methods=["GET", "HEAD"], include_in_schema=False)
async def healthcheck():
    """Returns true if the proxy is alive"""
    return {"success": True, "message": "healthy"}
