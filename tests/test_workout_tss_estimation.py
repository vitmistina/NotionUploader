"""Test workout TSS estimation."""

import pytest

from src.application.workouts import CreateManualWorkoutUseCase
from src.models.workout import ManualWorkoutSubmission
from src.notion.application.ports import WorkoutRepository

class WorkoutRepositoryStub(WorkoutRepository):
    def __init__(self, athlete_profile=None):
        self.athlete_profile = athlete_profile or {}
        self.saved_workouts = []

    async def fetch_latest_athlete_profile(self):
        return self.athlete_profile

    async def save_workout(self, detail, attachment, hr_drift, vo2max, tss, intensity_factor):
        self.saved_workouts.append({
            "detail": detail,
            "hr_drift": hr_drift,
            "vo2max": vo2max,
            "tss": tss,
            "intensity_factor": intensity_factor
        })

pytestmark = pytest.mark.asyncio

async def test_workout_tss_estimation_with_hr():
    """Should correctly estimate TSS and IF when HR data is available."""
    # Arrange
    repo = WorkoutRepositoryStub(athlete_profile={"max_hr": 190, "resting_hr": 60})
    use_case = CreateManualWorkoutUseCase(repository=repo)
    
    submission = ManualWorkoutSubmission(
        type="Run",
        name="Test Run",
        start_time="2025-11-06T10:00:00Z",  # Added required field
        duration_minutes=60,  # Added required field (3600 seconds = 60 minutes)
        duration_seconds=3600,
        distance_meters=10000,
        average_heartrate=150,
        max_heartrate=170,
        calories=500
    )

    # Act
    result = await use_case(submission)

    # Assert
    assert result.status == "ok"
    assert len(repo.saved_workouts) == 1
    saved = repo.saved_workouts[0]
    assert saved["tss"] is not None
    assert saved["intensity_factor"] is not None