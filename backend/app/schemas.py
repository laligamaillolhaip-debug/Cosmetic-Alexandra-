from pydantic import BaseModel, Field

SKIN_TYPE_PATTERN = "^(dry|oily|combination|sensitive|normal)$"


class CredentialsIn(BaseModel):
    email: str = Field(min_length=3, max_length=160)
    password: str = Field(min_length=1, max_length=200)


class ProfileIn(BaseModel):
    skin_types: list[str] = Field(min_length=1, max_length=5)
    concerns: list[str] = []
    budget_month: int = Field(ge=300, le=100000)


class ToggleIn(BaseModel):
    date: str
    time_of_day: str
    product_id: str
    done: bool


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=1000)


class AdviceIn(BaseModel):
    profile_id: str


class FavoriteIn(BaseModel):
    product_id: str


class PlanItemIn(BaseModel):
    product_id: str
    time_of_day: str = Field(pattern="^(morning|evening)$")


class ReorderIn(BaseModel):
    time_of_day: str = Field(pattern="^(morning|evening)$")
    item_ids: list[int]
