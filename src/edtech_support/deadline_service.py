from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import uvicorn
from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, field_validator

from .deadline_routing import DeadlineState, classify_deadline
from .infrai_realtime import InfraiError, InfraiRealtimeClient


class SupportChatRequest(BaseModel):
    request_id: str = Field(min_length=1)
    course_id: str = Field(min_length=1)
    course_title: str = Field(min_length=1)
    learner_id: str = Field(min_length=1)
    educator_id: str = Field(min_length=1)
    deadline_at: datetime
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("deadline_at")
    @classmethod
    def require_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("deadline_at must include a timezone")
        return value


class SupportChatResponse(BaseModel):
    request_id: str
    channel: str
    deadline_state: DeadlineState
    report_dimensions: dict[str, str]
    realtime_token: dict[str, Any]


def get_realtime_client() -> InfraiRealtimeClient:
    api_key = os.environ.get("INFRAI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=503, detail="INFRAI_API_KEY is required")
    client = InfraiRealtimeClient(api_key)
    try:
        yield client
    finally:
        client.close()


app = FastAPI(title="Course deadline support chat")


@app.post("/support/chats", response_model=SupportChatResponse, status_code=201)
def open_support_chat(
    request: SupportChatRequest,
    client: InfraiRealtimeClient = Depends(get_realtime_client),
) -> SupportChatResponse:
    observed_at = datetime.now(timezone.utc)
    deadline_state = classify_deadline(request.deadline_at, observed_at)
    channel = f"course-{request.course_id}-learner-{request.learner_id}"
    report_dimensions = {
        "course_id": request.course_id,
        "educator_id": request.educator_id,
        "deadline_state": deadline_state.value,
    }

    try:
        client.create_channel(channel, f"{request.request_id}:channel")
        client.publish(
            channel=channel,
            event="support.requested",
            data={
                "request_id": request.request_id,
                "course_title": request.course_title,
                "message": request.message,
                "deadline_at": request.deadline_at.isoformat(),
                "observed_at": observed_at.isoformat(),
                "report_dimensions": report_dimensions,
            },
            account_id=request.educator_id,
            idempotency_key=f"{request.request_id}:event",
        )
        token = client.issue_token(
            client_id=request.learner_id,
            channel=channel,
            idempotency_key=f"{request.request_id}:token",
        )
    except InfraiError as exc:
        client_status = exc.status_code if 400 <= exc.status_code < 500 else 502
        raise HTTPException(
            status_code=client_status,
            detail={"code": exc.code, "message": str(exc)},
        ) from exc

    return SupportChatResponse(
        request_id=request.request_id,
        channel=channel,
        deadline_state=deadline_state,
        report_dimensions=report_dimensions,
        realtime_token=token,
    )


def run() -> None:
    uvicorn.run("edtech_support.deadline_service:app", host="127.0.0.1", port=8000)


if __name__ == "__main__":
    run()
