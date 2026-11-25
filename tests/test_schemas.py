import pytest
from pydantic import ValidationError
from app.schemas import ProfileIn, ChatIn, CredentialsIn, PlanItemIn


@pytest.mark.parametrize("email", [
    "a@b.co",
    "a" * 145 + "@example.com",
])
def test_credentials_accept_valid_lengths(email):
    credentials = CredentialsIn(email=email, password="a" * 200)
    assert credentials.email == email


@pytest.mark.parametrize("email", [
    "",
    "ab",
])
def test_credentials_reject_email_below_min_length(email):
    with pytest.raises(ValidationError):
        CredentialsIn(email=email, password="123456")


def test_credentials_reject_email_above_max_length():
    with pytest.raises(ValidationError):
        CredentialsIn(email="a" * 161, password="123456")


@pytest.mark.parametrize("password", [
    "",
    "a" * 201,
])
def test_credentials_reject_password_outside_length_bounds(password):
    with pytest.raises(ValidationError):
        CredentialsIn(email="valid@example.com", password=password)

@pytest.mark.parametrize("budget, is_valid", [
    (300, True),
    (100000, True),
    (299, False),
    (100001, False),
])
def test_profile_budget(budget, is_valid):
    data = {"skin_types": ["dry"], "concerns": [], "budget_month": budget}
    if is_valid:
        ProfileIn(**data)
    else:
        with pytest.raises(ValidationError):
            ProfileIn(**data)

@pytest.mark.parametrize("length, is_valid", [
    (1, True),
    (5, True),
    (0, False),
    (6, False),
])
def test_profile_skin_types_length(length, is_valid):
    data = {"skin_types": ["dry"] * length, "concerns": [], "budget_month": 1000}
    if is_valid:
        ProfileIn(**data)
    else:
        with pytest.raises(ValidationError):
            ProfileIn(**data)

@pytest.mark.parametrize("length, is_valid", [
    (1, True),
    (1000, True),
    (0, False),
    (1001, False),
])
def test_chat_message_length(length, is_valid):
    data = {"message": "a" * length}
    if is_valid:
        ChatIn(**data)
    else:
        with pytest.raises(ValidationError):
            ChatIn(**data)

@pytest.mark.parametrize("time_of_day, is_valid", [
    ("morning", True),
    ("evening", True),
    ("noon", False),
    ("", False),
    ("Morning", False),
])
def test_plan_item_time_of_day(time_of_day, is_valid):
    data = {"product_id": "123", "time_of_day": time_of_day}
    if is_valid:
        PlanItemIn(**data)
    else:
        with pytest.raises(ValidationError):
            PlanItemIn(**data)