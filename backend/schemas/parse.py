from pydantic import BaseModel, Field


class ParseRequest(BaseModel):
    text: str = Field(min_length=3, max_length=500)


class ParseResult(BaseModel):
    category: str
    description: str
    quantity_portions: float
    quantity_estimated: bool
    expiry_time: str
    expiry_estimated: bool
    warnings: list[str] = []
