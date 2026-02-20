from fastapi import APIRouter, HTTPException
from schemas import ProfileResponseSchema, ProfileCreate


from src.database.models.accounts import UserProfileModel

router = APIRouter()

@router.post("/users/{user_id}/profile/", response=ProfileResponseSchema)
async def create_profile(
        profile_data: ProfileCreate,
        db: AsyncSession = Depends(get_db),
):
    existing_stmt = select(UserProfileModel).where(
        (UserProfileModel.name == profile_data.name),
        (UserProfileModel.date == profile_data.date)
    )
    existing_result = await db.execute(existing_stmt)
    existing_movie = existing_result.scalars().first()
    if existing_movie:
        raise HTTPException(
            status_code=400,
        )

    if not profile_data.is_active:
        raise HTTPException(
            status_code=401,
        )


    new_profile = UserProfileModel(
        id=profile_data.id,
        first_name=profile_data.first_name,
        avatar=profile_data.avatar,
        gender=profile_data.gender,
        date_of_birth=profile_data.date_of_birth,
        info=profile_data.info
    )

    await db.add(new_profile)
    await  db.commit(new_profile)
    await db.refresh(new_profile)
    return new_profile
