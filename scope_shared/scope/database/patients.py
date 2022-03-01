import pymongo.database
from typing import List, Optional

import scope.database.collection_utils
import scope.database.patient.clinical_history
import scope.database.patient.patient_profile
import scope.schema

PATIENT_IDENTITY_COLLECTION = "patients"

PATIENT_IDENTITY_DOCUMENT_TYPE = "patientIdentity"
PATIENT_IDENTITY_SEMANTIC_SET_ID = "patientId"


def _patient_collection_name(*, patient_id: str) -> str:
    return "patient_{}".format(patient_id)


def create_patient(
    *,
    database: pymongo.database.Database,
    patient_id: str = None,
    patient_name: str,
    patient_mrn: str,
) -> dict:
    """
    Create a patient. This includes:
    - Generate a patient_id, unless it was provided.
    - Create a patient collection.
    - Create a profile document containing the name and MRN.
    - Finally, create the patient identity document.
    """

    patient_identity_collection = database.get_collection(PATIENT_IDENTITY_COLLECTION)

    # Obtain a unique ID for the patient, use that to create a collection name.
    if patient_id is None:
        patient_id = scope.database.collection_utils.generate_set_id()
    generated_patient_collection_name = _patient_collection_name(patient_id=patient_id)

    # Ensure this patient id and collection do not already exist
    if get_patient_identity(database=database, patient_id=patient_id) is not None:
        raise ValueError('Patient "{}" already exists'.format(patient_id))
    if generated_patient_collection_name in database.list_collection_names():
        raise ValueError(
            'Collection "{}" already exists'.format(generated_patient_collection_name)
        )

    # Create the patient collection with a sentinel document
    patient_collection = database.get_collection(generated_patient_collection_name)
    result = scope.database.collection_utils.put_singleton(
        collection=patient_collection,
        document_type="sentinel",
        document={},
    )

    # Create the index on the patient collection
    scope.database.collection_utils.ensure_index(collection=patient_collection)

    # Create the initial profile document
    patient_profile_document = {
        "_type": scope.database.patient.patient_profile.DOCUMENT_TYPE,
        "name": patient_name,
        "MRN": patient_mrn,
    }
    scope.schema.raise_for_invalid(
        schema=scope.schema.patient_profile_schema,
        document=patient_profile_document,
    )
    result = scope.database.patient.patient_profile.put_patient_profile(
        database=database,
        collection=patient_collection,
        patient_id=patient_id,
        patient_profile=patient_profile_document,
    )

    # Create the initial clinical history document
    clinical_history_document = {
        "_type": scope.database.patient.clinical_history.DOCUMENT_TYPE,
    }
    scope.schema.raise_for_invalid(
        schema=scope.schema.clinical_history_schema,
        document=clinical_history_document,
    )
    result = scope.database.patient.clinical_history.put_clinical_history(
        collection=patient_collection,
        clinical_history=clinical_history_document,
    )

    # Atomically store the patient identity document.
    # Do this last, because it means all other steps have already succeeded.
    patient_identity_document = {
        "_type": PATIENT_IDENTITY_DOCUMENT_TYPE,
        "name": patient_name,
        "MRN": patient_mrn,
        "collection": generated_patient_collection_name,
    }
    scope.schema.raise_for_invalid(
        schema=scope.schema.patient_identity_schema,
        document=patient_identity_document,
    )
    result = scope.database.collection_utils.put_set_element(
        collection=patient_identity_collection,
        document_type=PATIENT_IDENTITY_DOCUMENT_TYPE,
        semantic_set_id=PATIENT_IDENTITY_SEMANTIC_SET_ID,
        set_id=patient_id,
        document=patient_identity_document,
    )
    patient_identity_document = result.document

    return patient_identity_document


def delete_patient(
    *,
    database: pymongo.database.Database,
    patient_id: str,
    destructive: bool,
):
    """
    Delete a patient identity and collection.
    """

    if not destructive:
        raise NotImplementedError()

    patient_identity_collection = database.get_collection(PATIENT_IDENTITY_COLLECTION)

    # Confirm the patient exists.
    patient_identity_document = scope.database.collection_utils.get_set_element(
        collection=patient_identity_collection,
        document_type=PATIENT_IDENTITY_DOCUMENT_TYPE,
        set_id=patient_id,
    )
    if patient_identity_document is None:
        return False

    # Atomically delete the identity first, then delete all other traces of the patient.
    scope.database.collection_utils.delete_set_element(
        collection=patient_identity_collection,
        document_type=PATIENT_IDENTITY_DOCUMENT_TYPE,
        set_id=patient_id,
        destructive=destructive,
    )

    database.drop_collection(patient_identity_document["collection"])

    return True


def get_patient_identity(
    *,
    database: pymongo.database.Database,
    patient_id: str,
) -> Optional[dict]:
    """
    Retrieve a patient identity document.
    """

    patient_identity_collection = database.get_collection(PATIENT_IDENTITY_COLLECTION)

    return scope.database.collection_utils.get_set_element(
        collection=patient_identity_collection,
        document_type=PATIENT_IDENTITY_DOCUMENT_TYPE,
        set_id=patient_id,
    )


def put_patient_identity(
    *,
    database: pymongo.database.Database,
    patient_id: str,
    patient_identity: dict,
) -> scope.database.collection_utils.SetPutResult:
    """
    Put a patient identity document.
    """

    patient_identity_collection = database.get_collection(PATIENT_IDENTITY_COLLECTION)

    return scope.database.collection_utils.put_set_element(
        collection=patient_identity_collection,
        document_type=PATIENT_IDENTITY_DOCUMENT_TYPE,
        semantic_set_id=PATIENT_IDENTITY_SEMANTIC_SET_ID,
        set_id=patient_id,
        document=patient_identity,
    )


def get_patient_identities(
    *,
    database: pymongo.database.Database,
) -> Optional[List[dict]]:
    """
    Retrieve all patient identity documents.
    """

    patient_identity_collection = database.get_collection(PATIENT_IDENTITY_COLLECTION)

    return scope.database.collection_utils.get_set(
        collection=patient_identity_collection,
        document_type=PATIENT_IDENTITY_DOCUMENT_TYPE,
    )
