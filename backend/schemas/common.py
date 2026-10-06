from typing import Annotated

from pydantic import Field

MAX_AMOUNT = 10_000

Latitude = Annotated[float, Field(ge=-90, le=90, allow_inf_nan=False)]
Longitude = Annotated[float, Field(ge=-180, le=180, allow_inf_nan=False)]
Amount = Annotated[float, Field(gt=0, le=MAX_AMOUNT, allow_inf_nan=False)]
