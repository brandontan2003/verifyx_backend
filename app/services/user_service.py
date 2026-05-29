# Business Logic
from app.core.exceptions.exceptions import UserNotFoundException, UserAlreadyExistsException
from app.dto.base import DataResponse
from app.dto.user import UpdateUsernameRequest
from app.models.user import User
from app.repositories.user_repo import UserRepository


async def retrieve_user(database, user) -> User:
    repo = UserRepository(database)
    database_user = await repo.get_by_user_id(user["sub"])
    return database_user


async def retrieve_user_by_email(email_address, database) -> User:
    repo = UserRepository(database)
    return await repo.get_by_email(email_address)


async def get_user(user, database):
    database_user = await retrieve_user(database, user)
    if not database_user:
        raise UserNotFoundException()
    return DataResponse(result=database_user)


async def create_user(user, database):
    repo = UserRepository(database)
    existing = await repo.get_by_user_id(user["sub"])
    if existing:
        raise UserAlreadyExistsException()

    # derive default username from email prefix
    default_username = user["email"].split("@")[0]
    database_user = await repo.create(user["sub"], user["email"], default_username)
    return DataResponse(result=database_user)


async def update_user(user, payload: UpdateUsernameRequest, database):
    repo = UserRepository(database)
    existing = await retrieve_user(database, user)
    if not existing:
        raise UserNotFoundException()
    updated_user = await repo.update_username(user["sub"], payload.username)
    return DataResponse(result=updated_user)
