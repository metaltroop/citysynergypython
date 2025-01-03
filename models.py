from pydantic import BaseModel
from typing import List, Dict, Union

class PincodeRequest(BaseModel):
    pincode: str

class ClashDetails(BaseModel):
    tender_id: str
    clashing_tender_id: str
    overlap_days: int
    priority_issue: bool

class ClashResponse(BaseModel):
    clashes: List[ClashDetails]
    suggestions: List[str]
