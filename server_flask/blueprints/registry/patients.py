import copy
import flask
import flask_json
import pymongo.collection
import timeit

import request_utils
import request_context
import scope.database.collection_utils
import scope.database.patient.activities
import scope.database.patient.activity_logs
import scope.database.patient.activity_schedules
import scope.database.patient.assessment_logs
import scope.database.patient.assessments
import scope.database.patient.case_reviews
import scope.database.patient.clinical_history
import scope.database.patient.mood_logs
import scope.database.patient.patient_profile
import scope.database.patient.safety_plan
import scope.database.patient.scheduled_activities
import scope.database.patient.scheduled_assessments
import scope.database.patient.sessions
import scope.database.patient.values
import scope.database.patient.values_inventory
import scope.database.patients

patients_blueprint = flask.Blueprint(
    "patients_blueprint",
    __name__,
)


def _construct_patient_document(
    *,
    patient_identity: dict,
    patient_collection: pymongo.collection.Collection,
) -> dict:
    timeit_start = timeit.default_timer()

    patient_document = {}

    patient_document["_type"] = "patient"

    # Identity
    patient_document["identity"] = copy.deepcopy(patient_identity)

    # Get multiple document types simultaneously
    result = scope.database.collection_utils.get_multiple_types(
        collection=patient_collection,
        singleton_types=[
            scope.database.patient.clinical_history.DOCUMENT_TYPE,
            scope.database.patient.patient_profile.DOCUMENT_TYPE,
            scope.database.patient.safety_plan.DOCUMENT_TYPE,
            scope.database.patient.values_inventory.DOCUMENT_TYPE,
        ],
        set_types=[
            scope.database.patient.activities.DOCUMENT_TYPE,
            scope.database.patient.activity_logs.DOCUMENT_TYPE,
            scope.database.patient.activity_schedules.DOCUMENT_TYPE,
            scope.database.patient.assessments.DOCUMENT_TYPE,
            scope.database.patient.assessment_logs.DOCUMENT_TYPE,
            scope.database.patient.case_reviews.DOCUMENT_TYPE,
            scope.database.patient.mood_logs.DOCUMENT_TYPE,
            scope.database.patient.scheduled_activities.DOCUMENT_TYPE,
            scope.database.patient.sessions.DOCUMENT_TYPE,
            scope.database.patient.values.DOCUMENT_TYPE,
        ],
    )

    documents_by_type = result["documents_by_type"]

    # Activities
    patient_document["activities"] = documents_by_type[
        scope.database.patient.activities.DOCUMENT_TYPE
    ]

    # Activity Logs
    patient_document["activityLogs"] = documents_by_type[
        scope.database.patient.activity_logs.DOCUMENT_TYPE
    ]

    # Activity Schedules
    patient_document["activitySchedules"] = documents_by_type[
        scope.database.patient.activity_schedules.DOCUMENT_TYPE
    ]

    # Assessments
    patient_document["assessments"] = documents_by_type[
        scope.database.patient.assessments.DOCUMENT_TYPE
    ]

    # Assessment Logs
    patient_document["assessmentLogs"] = documents_by_type[
        scope.database.patient.assessment_logs.DOCUMENT_TYPE
    ]

    # Case Reviews
    patient_document["caseReviews"] = documents_by_type[
        scope.database.patient.case_reviews.DOCUMENT_TYPE
    ]

    # Clinical History
    patient_document["clinicalHistory"] = documents_by_type[
        scope.database.patient.clinical_history.DOCUMENT_TYPE
    ]

    # Mood Logs
    patient_document["moodLogs"] = documents_by_type[
        scope.database.patient.mood_logs.DOCUMENT_TYPE
    ]

    # Profile
    patient_document["profile"] = documents_by_type[
        scope.database.patient.patient_profile.DOCUMENT_TYPE
    ]

    # Safety Plan
    patient_document["safetyPlan"] = documents_by_type[
        scope.database.patient.safety_plan.DOCUMENT_TYPE
    ]

    # Scheduled Assessments
    # TODO: this access currently modifies documents, cannot be replaced
    timeit_step = timeit.default_timer()
    patient_document[
        "scheduledAssessments"
    ] = scope.database.patient.scheduled_assessments.get_scheduled_assessments(
        collection=patient_collection
    )
    timeit_get_scheduled_assessments = timeit.default_timer() - timeit_step

    # Scheduled Activities
    patient_document["scheduledActivities"] = documents_by_type[
        scope.database.patient.scheduled_activities.DOCUMENT_TYPE
    ]

    # Sessions
    patient_document["sessions"] = documents_by_type[
        scope.database.patient.sessions.DOCUMENT_TYPE
    ]

    # Values
    patient_document["values"] = documents_by_type[
        scope.database.patient.values.DOCUMENT_TYPE
    ]

    # Values Inventory
    patient_document["valuesInventory"] = documents_by_type[
        scope.database.patient.values_inventory.DOCUMENT_TYPE
    ]

    timeit_total = timeit.default_timer() - timeit_start

    return {
        "patient_document": patient_document,
        "_timing": {
            "0 - total": format(timeit_total, 'f'),
            "1 - get_multiple_types": result["_timing"],
            "2 - get_scheduled_assessments": format(timeit_get_scheduled_assessments, 'f'),
        }
    }


@patients_blueprint.route(
    "/patients",
    methods=["GET"],
)
@flask_json.as_json
def get_patients():
    timeit_start = timeit.default_timer()

    context = request_context.authorized_for_everything()
    database = context.database

    # List of documents from the patient identities collection
    patient_identities = scope.database.patients.get_patient_identities(
        database=database,
    )

    # Construct a full patient document for each
    patient_documents = []
    timing_construct_patient_document = []
    for patient_identity_current in patient_identities:
        patient_collection = database.get_collection(
            patient_identity_current["collection"]
        )

        result = _construct_patient_document(
            patient_identity=patient_identity_current,
            patient_collection=patient_collection,
        )

        patient_documents.append(
            result["patient_document"]
        )
        timing_construct_patient_document.append(
            result["_timing"]
        )

    timeit_total = timeit.default_timer() - timeit_start

    return {
        "patients": patient_documents,
        "_timing": {
            "total": format(timeit_total, 'f'),
            "_construct_patient_document": timing_construct_patient_document,
        },
    }


@patients_blueprint.route(
    "/patient/<string:patient_id>",
    methods=["GET"],
)
@flask_json.as_json
def get_patient(patient_id):
    timeit_start = timeit.default_timer()

    context = request_context.authorized_for_patient(patient_id=patient_id)
    database = context.database

    # Document from the patient identities collection
    patient_identity = scope.database.patients.get_patient_identity(
        database=context.database,
        patient_id=patient_id,
    )
    if patient_identity is None:
        request_utils.abort_patient_not_found()

    # Construct a full patient document
    patient_collection = database.get_collection(patient_identity["collection"])

    result = _construct_patient_document(
        patient_identity=patient_identity,
        patient_collection=patient_collection,
    )

    timeit_total = timeit.default_timer() - timeit_start

    return {
        "patient": result["patient_document"],
        "_timing": {
            "total": format(timeit_total, 'f'),
            "_construct_patient_document": result["_timing"],
        },
    }


@patients_blueprint.route(
    "/patientidentities",
    methods=["GET"],
)
@flask_json.as_json
def get_patient_identities():
    context = request_context.authorized_for_everything()
    database = context.database

    # List of documents from the patient identities collection
    patient_identities = scope.database.patients.get_patient_identities(
        database=database,
    )

    # Validate and normalize the response
    patient_identities = request_utils.set_get_response_validate(
        documents=patient_identities,
    )

    return {"patientidentities": patient_identities}
