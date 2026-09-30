"""Response, Rescue teams, resources, and assignments schemas."""

from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field, root_validator, model_validator

class RescueTeamResponse(BaseModel):
    id: int
    authority_id: int
    name: str
    team_type: str
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    active_assignment_count: int = 0
    created_at: datetime
    updated_at: datetime

class RescueResourceResponse(BaseModel):
    id: int
    authority_id: int
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    resource_type: str
    name: str
    quantity: int
    status: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    distance_m: Optional[float] = None
    created_at: datetime
    updated_at: datetime

class ResponseAssignmentCreateRequest(BaseModel):
    team_id: Optional[int] = None
    resource_id: Optional[int] = None

    @model_validator(mode="after")
    def check_exactly_one(self):
        has_team = self.team_id is not None
        has_resource = self.resource_id is not None
        if (has_team and has_resource) or (not has_team and not has_resource):
            raise ValueError("Exactly one of team_id or resource_id must be provided")
        return self

class ResponseAssignmentUpdateRequest(BaseModel):
    status: Literal["ASSIGNED", "DEPLOYED", "RELEASED"]

class ResponseAssignmentResponse(BaseModel):
    id: int
    response_action_id: int
    team_id: Optional[int] = None
    team_name: Optional[str] = None
    resource_id: Optional[int] = None
    resource_name: Optional[str] = None
    status: str
    assigned_at: datetime
    released_at: Optional[datetime] = None
    assigned_by: Optional[int] = None
