import base64

from io import BytesIO

import aiohttp
import zxingcpp

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse

from PIL import Image
from pydantic import BaseModel, Required

CONTRACT_URL = "https://api.kkm.krakow.pl/api/v1/mkkm/tickets/{ticket_guid}/contract"


class HTTPException(Exception):
    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


class ContractResponse(BaseModel):
    aztec: str


class ErrorResponse(BaseModel):
    message: str


app = FastAPI(
    debug=False,
    title="Ticket Contract Proxy",
    description="A microservice to decode AZTEC codes from mKKM to save bandwidth.",
    version="1.0",
    docs_url=None,
    redoc_url="/docs/"
)


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exception: HTTPException):
    """Return exception as JSON response"""
    return JSONResponse(
        status_code=exception.status_code,
        content={"message": exception.message},
    )


@app.get("/ticket/{ticket_guid}", response_model=ContractResponse, responses={
    400: {"model": ErrorResponse},
    403: {"model": ErrorResponse},
    500: {"model": ErrorResponse}
})
async def get_contract(ticket_guid: str, authorization: str = Header(Required)):
    """Return decoded AZTEC barcode data"""
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

            return {"aztec": result.text}
