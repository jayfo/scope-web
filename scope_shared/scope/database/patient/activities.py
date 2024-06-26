import datetime
import pymongo.collection
import pytz
from typing import List, Optional

import scope.database.collection_utils
import scope.database.patient.activity_schedules
import scope.database.patient.scheduled_activities
import scope.enums
import scope.schema


DOCUMENT_TYPE = "activity"
SEMANTIC_SET_ID = "activityId"


def delete_activity(
    *,
    collection: pymongo.collection.Collection,
    set_id: str,
    rev: int,
) -> scope.database.collection_utils.SetPutResult:
    """
    Delete "activity" document.

    - Any corresponding ActivitySchedule documents must be deleted.
    - Which will in turn delete any pending ScheduledActivity documents.
    """

    result = scope.database.collection_utils.delete_set_element(
        collection=collection,
        document_type=DOCUMENT_TYPE,
        set_id=set_id,
        rev=rev,
    )

    if result.inserted_count == 1:
        existing_activity_schedules = (
            scope.database.patient.activity_schedules.get_activity_schedules(
                collection=collection
            )
        )
        for activity_schedule in existing_activity_schedules:
            if activity_schedule.get(SEMANTIC_SET_ID) == set_id:
                scope.database.patient.activity_schedules.delete_activity_schedule(
                    collection=collection,
                    set_id=activity_schedule[
                        scope.database.patient.activity_schedules.SEMANTIC_SET_ID
                    ],
                    rev=activity_schedule.get("_rev"),
                )

    return result


def get_activities(
    *,
    collection: pymongo.collection.Collection,
) -> Optional[List[dict]]:
    """
    Get list of "activity" documents.
    """

    # patients.py/_construct_patient_document
    # currently assumes this access does nothing to retrieved documents.
    return scope.database.collection_utils.get_set(
        collection=collection,
        document_type=DOCUMENT_TYPE,
    )


def get_activity(
    *,
    collection: pymongo.collection.Collection,
    set_id: str,
) -> Optional[dict]:
    """
    Get "activity" document.
    """

    return scope.database.collection_utils.get_set_element(
        collection=collection,
        document_type=DOCUMENT_TYPE,
        set_id=set_id,
    )


def post_activity(
    *,
    collection: pymongo.collection.Collection,
    activity: dict,
) -> scope.database.collection_utils.SetPostResult:
    """
    Post "activity" document.
    """

    return scope.database.collection_utils.post_set_element(
        collection=collection,
        document_type=DOCUMENT_TYPE,
        semantic_set_id=SEMANTIC_SET_ID,
        document=activity,
    )


def put_activity(
    *,
    collection: pymongo.collection.Collection,
    activity: dict,
    set_id: str,
) -> scope.database.collection_utils.SetPutResult:
    """
    Put "activity" document.

    - Because ScheduledActivity documents may reference this activity, their snapshots must be updated.
    """

    activity_set_put_result = scope.database.collection_utils.put_set_element(
        collection=collection,
        document_type=DOCUMENT_TYPE,
        semantic_set_id=SEMANTIC_SET_ID,
        set_id=set_id,
        document=activity,
    )

    if activity_set_put_result.inserted_count == 1:
        scope.database.patient.scheduled_activities.maintain_scheduled_activities_data_snapshot(
            collection=collection,
            maintenance_datetime=pytz.utc.localize(datetime.datetime.utcnow()),
        )

    return activity_set_put_result
