from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Response,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from database import get_db
from dependencies import get_current_user
from models import Task, User
from schemas import (
    TaskCreate,
    TaskReplace,
    TaskResponse,
    TaskUpdate,
)


router = APIRouter(
    prefix="/tasks",
    tags=["Tasks"],
)


def get_owned_task(
    task_id: int,
    user_id: int,
    db: Session,
) -> Task:
    task = db.scalar(
        select(Task).where(
            Task.id == task_id,
            Task.owner_id == user_id,
        )
    )

    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task not found",
        )

    return task


def check_duplicate_title(
    title: str,
    user_id: int,
    db: Session,
    exclude_id: int | None = None,
) -> None:
    statement = select(Task.id).where(
        Task.owner_id == user_id,
        func.lower(Task.title) == title.lower(),
    )

    if exclude_id is not None:
        statement = statement.where(Task.id != exclude_id)

    existing_id = db.scalar(statement)

    if existing_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You already have a task with this title",
        )


# IMPORTANT:
# Fixed routes such as /tasks/filter must appear before /tasks/{task_id}.


@router.get("/", response_model=list[TaskResponse])
def get_tasks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    completed: bool | None = None,
    skip: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
):
    statement = select(Task).where(
        Task.owner_id == current_user.id
    )

    if completed is not None:
        statement = statement.where(
            Task.completed == completed
        )

    statement = (
        statement
        .order_by(Task.id)
        .offset(skip)
        .limit(limit)
    )

    return list(db.scalars(statement).all())


@router.get("/filter", response_model=list[TaskResponse])
def filter_tasks(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    title: Annotated[str | None, Query(max_length=100)] = None,
    completed: bool | None = None,
):
    statement = select(Task).where(
        Task.owner_id == current_user.id
    )

    if title is not None:
        search_title = title.strip()

        if search_title:
            statement = statement.where(
                func.lower(Task.title).contains(
                    search_title.lower(),
                    autoescape=True,
                )
            )

    if completed is not None:
        statement = statement.where(
            Task.completed == completed
        )

    statement = statement.order_by(Task.id)

    return list(db.scalars(statement).all())


@router.get("/{task_id}", response_model=TaskResponse)
def get_task(
    task_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    return get_owned_task(task_id, current_user.id, db)


@router.post(
    "/",
    response_model=TaskResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_task(
    task_data: TaskCreate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    check_duplicate_title(
        title=task_data.title,
        user_id=current_user.id,
        db=db,
    )

    task = Task(
        title=task_data.title,
        description=task_data.description,
        completed=task_data.completed,
        owner_id=current_user.id,
    )

    db.add(task)
    db.commit()
    db.refresh(task)

    return task


@router.put("/{task_id}", response_model=TaskResponse)
def replace_task(
    task_id: int,
    task_data: TaskReplace,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    task = get_owned_task(task_id, current_user.id, db)

    check_duplicate_title(
        title=task_data.title,
        user_id=current_user.id,
        db=db,
        exclude_id=task.id,
    )

    task.title = task_data.title
    task.description = task_data.description
    task.completed = task_data.completed

    db.commit()
    db.refresh(task)

    return task


@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(
    task_id: int,
    task_data: TaskUpdate,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    task = get_owned_task(task_id, current_user.id, db)

    update_data = task_data.model_dump(exclude_unset=True)

    if "title" in update_data:
        if update_data["title"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Task title cannot be null",
            )

        check_duplicate_title(
            title=update_data["title"],
            user_id=current_user.id,
            db=db,
            exclude_id=task.id,
        )

    if "completed" in update_data:
        if update_data["completed"] is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Completed cannot be null",
            )

    for field, value in update_data.items():
        setattr(task, field, value)

    db.commit()
    db.refresh(task)

    return task


@router.delete(
    "/{task_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_task(
    task_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    task = get_owned_task(task_id, current_user.id, db)

    db.delete(task)
    db.commit()

    return Response(status_code=status.HTTP_204_NO_CONTENT)