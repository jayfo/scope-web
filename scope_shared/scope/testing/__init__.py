from scope.testing.testing_check_fixtures import testing_check_fixtures
from scope.testing.testing_config import TestingConfig

PYTEST_PLUGINS = [
    "scope.testing.fake_data.fixtures_fake_activity",
    "scope.testing.fake_data.fixtures_fake_activities",
    "scope.testing.fake_data.fixtures_fake_activity_logs",
    "scope.testing.fake_data.fixtures_fake_activity_schedule",
    "scope.testing.fake_data.fixtures_fake_activity_schedules",
    "scope.testing.fake_data.fixtures_fake_assessments",
    "scope.testing.fake_data.fixtures_fake_assessment_contents",
    "scope.testing.fake_data.fixtures_fake_assessment_logs",
    "scope.testing.fake_data.fixtures_fake_case_review",
    "scope.testing.fake_data.fixtures_fake_case_reviews",
    "scope.testing.fake_data.fixtures_fake_clinical_history",
    "scope.testing.fake_data.fixtures_fake_contact",
    "scope.testing.fake_data.fixtures_fake_life_area_contents",
    "scope.testing.fake_data.fixtures_fake_mood_log",
    "scope.testing.fake_data.fixtures_fake_mood_logs",
    "scope.testing.fake_data.fixtures_fake_patient_profile",
    "scope.testing.fake_data.fixtures_fake_provider_identity",
    "scope.testing.fake_data.fixtures_fake_referral_status",
    "scope.testing.fake_data.fixtures_fake_review_mark",
    "scope.testing.fake_data.fixtures_fake_review_marks",
    "scope.testing.fake_data.fixtures_fake_safety_plan",
    "scope.testing.fake_data.fixtures_fake_session",
    "scope.testing.fake_data.fixtures_fake_sessions",
    "scope.testing.fake_data.fixtures_fake_scheduled_activities",
    "scope.testing.fake_data.fixtures_fake_scheduled_assessments",
    "scope.testing.fake_data.fixtures_fake_value",
    "scope.testing.fake_data.fixtures_fake_values",
    "scope.testing.fake_data.fixtures_fake_values_inventory",
    "scope.testing.fixtures_config",
    "scope.testing.fixtures_database",
    "scope.testing.fixtures_database_temp_collection",
    "scope.testing.fixtures_database_temp_patient",
    "scope.testing.fixtures_database_temp_provider",
    "scope.testing.fixtures_documentdb",
    "scope.testing.fixtures_faker",
    "scope.testing.fixtures_flask",
]
