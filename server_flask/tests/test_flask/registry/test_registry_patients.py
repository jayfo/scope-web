import http
import requests
from typing import Callable
from urllib.parse import urljoin

import scope.config
import scope.database.collection_utils as collection_utils
import scope.database.patients
import scope.schema
import scope.schema_utils as schema_utils
import scope.testing.fixtures_database_temp_patient
import tests.testing_config

TESTING_CONFIGS = tests.testing_config.ALL_CONFIGS

QUERY_PATIENTS = "patients"
QUERY_PATIENT = "patient/{patient_id}"
QUERY_PATIENTIDENTITIES = "patientidentities"


def test_patients_get(
    database_temp_patient_factory: Callable[
        [],
        scope.testing.fixtures_database_temp_patient.DatabaseTempPatient,
    ],
    flask_client_config: scope.config.FlaskClientConfig,
    flask_session_unauthenticated_factory: Callable[[], requests.Session],
):
    """
    Test retrieving patients.
    """

    session = flask_session_unauthenticated_factory()

    created_ids = [database_temp_patient_factory().patient_id for _ in range(5)]

    response = session.get(
        url=urljoin(
            flask_client_config.baseurl,
            QUERY_PATIENTS,
        ),
    )
    assert response.ok

    # Assert the response includes patients
    assert "patients" in response.json()
    patient_documents = response.json()["patients"]

    # Assert all of our created test patients are present
    retrieved_ids = [
        patient_document_current["identity"][
            scope.database.patients.PATIENT_IDENTITY_SEMANTIC_SET_ID
        ]
        for patient_document_current in patient_documents
    ]
    assert all(patient_id in retrieved_ids for patient_id in created_ids)

    # Assert each individual patient document is a valid document
    for patient_document_current in patient_documents:
        # Assert each piece of the document is valid
        # schema_utils.assert_schema(
        #     data=patient_document_current["activities"],
        #     schema=scope.schema.activities_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["activityLogs"],
        #     schema=scope.schema.activity_logs_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["assessments"],
        #     schema=scope.schema.assessments_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["assessmentLogs"],
        #     schema=scope.schema.assessment_logs_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["caseReviews"],
        #     schema=scope.schema.case_reviews_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["clinicalHistory"],
        #     schema=scope.schema.clinical_history_schema,
        # )
        schema_utils.assert_schema(
            data=patient_document_current["identity"],
            schema=scope.schema.patient_identity_schema,
        )
        # schema_utils.assert_schema(
        #     data=patient_document_current["moodLogs"],
        #     schema=scope.schema.mood_logs_schema,
        # )
        schema_utils.assert_schema(
            data=patient_document_current["profile"],
            schema=scope.schema.patient_profile_schema,
        )
        # schema_utils.assert_schema(
        #     data=patient_document_current["safetyPlan"],
        #     schema=scope.schema.safety_plan_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["scheduledAssessments"],
        #     schema=scope.schema.scheduled_assessments_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["scheduledActivities"],
        #     schema=scope.schema.scheduled_activities_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["sessions"],
        #     schema=scope.schema.sessions_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["values"],
        #     schema=scope.schema.values_schema,
        # )
        # schema_utils.assert_schema(
        #     data=patient_document_current["valuesInventory"],
        #     schema=scope.schema.values_inventory_schema,
        # )
        #
        # # Assert the combination is a valid patient document
        # schema_utils.assert_schema(
        #     data=patient_document_current,
        #     schema=scope.schema.patient_schema,
        # )

    # Assert the overall combination of patients is a valid document
    schema_utils.assert_schema(
        data=response.json()["patients"],
        schema=scope.schema.patients_schema,
    )


def test_patientidentities_get(
    database_temp_patient_factory: Callable[
        [],
        scope.testing.fixtures_database_temp_patient.DatabaseTempPatient,
    ],
    flask_client_config: scope.config.FlaskClientConfig,
    flask_session_unauthenticated_factory: Callable[[], requests.Session],
):
    """
    Test retrieving patient identities.
    """

    session = flask_session_unauthenticated_factory()

    created_ids = [database_temp_patient_factory().patient_id for _ in range(5)]

    response = session.get(
        url=urljoin(
            flask_client_config.baseurl,
            QUERY_PATIENTIDENTITIES,
        ),
    )
    assert response.ok

    assert "patientidentities" in response.json()
    patient_identity_documents = response.json()["patientidentities"]
    schema_utils.assert_schema(
        data=patient_identity_documents,
        schema=scope.schema.patient_identities_schema,
    )

    retrieved_ids = [
        patient_identity_document_current[
            scope.database.patients.PATIENT_IDENTITY_SEMANTIC_SET_ID
        ]
        for patient_identity_document_current in patient_identity_documents
    ]
    assert all(patient_id in retrieved_ids for patient_id in created_ids)


def test_patient_get(
    database_temp_patient_factory: Callable[
        [],
        scope.testing.fixtures_database_temp_patient.DatabaseTempPatient,
    ],
    flask_client_config: scope.config.FlaskClientConfig,
    flask_session_unauthenticated_factory: Callable[[], requests.Session],
):
    """
    Test retrieving a patient.
    """

    session = flask_session_unauthenticated_factory()

    created_id = database_temp_patient_factory().patient_id

    response = session.get(
        url=urljoin(
            flask_client_config.baseurl,
            QUERY_PATIENT.format(patient_id=created_id),
        ),
    )
    assert response.ok

    assert "patient" in response.json()
    patient_document = response.json()["patient"]
    schema_utils.assert_schema(
        data=patient_document,
        schema=scope.schema.patient_schema,
    )

    patient_identity = patient_document["identity"]
    patient_id = patient_identity[
        scope.database.patients.PATIENT_IDENTITY_SEMANTIC_SET_ID
    ]
    assert patient_id == created_id


def test_patient_get_invalid(
    flask_client_config: scope.config.FlaskClientConfig,
    flask_session_unauthenticated_factory: Callable[[], requests.Session],
):
    """
    Test non-existent patient yields 404.
    """

    session = flask_session_unauthenticated_factory()

    response = session.get(
        url=urljoin(
            flask_client_config.baseurl,
            QUERY_PATIENT.format(patient_id="invalid"),
        ),
    )
    assert response.status_code == http.HTTPStatus.NOT_FOUND

    response = session.get(
        url=urljoin(
            flask_client_config.baseurl,
            QUERY_PATIENT.format(patient_id=collection_utils.generate_set_id()),
        ),
    )
    assert response.status_code == http.HTTPStatus.NOT_FOUND
