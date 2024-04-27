import base64
import copy
from dataclasses import dataclass
import hashlib
import timeit
import pymongo.collection
import pymongo.errors
from typing import Dict, List, Optional, Union
import uuid

import scope.database.document_utils as document_utils

PRIMARY_COLLECTION_INDEX = [
    ("_type", pymongo.ASCENDING),
    ("_set_id", pymongo.ASCENDING),
    ("_rev", pymongo.DESCENDING),
]
PRIMARY_COLLECTION_INDEX_NAME = "_primary"


class DocumentModifiedException(Exception):
    """
    Raised if a request that should increment _rev fails due a DuplicateKeyError,
    which implies somebody else has already modified the document.
    """

    document_existing: dict
    """
    Current version of the document.
    """

    def __init__(self, document_existing: dict):
        self.document_existing = document_existing
        super().__init__()


class DocumentNotFoundException(Exception):
    """
    Raised if a request implies existence of a document which is not found.
    """

    pass


@dataclass(frozen=True)
class PutResult:
    inserted_count: int
    inserted_id: str
    document: dict


@dataclass(frozen=True)
class SetPostResult:
    inserted_count: int
    inserted_id: str
    inserted_set_id: str
    document: dict


@dataclass(frozen=True)
class SetPutResult:
    inserted_count: int
    inserted_id: str
    inserted_set_id: str
    document: dict


def generate_set_id() -> str:
    """
    Generates an id that:
    - Is guaranteed to be URL safe.
    - Is guaranteed to be compatible with MongoDB collection naming.
    - Is expected to be unique.
    """

    # Obtain uniqueness
    generated_uuid = uuid.uuid4()
    # Manage length so these don't seem obscenely long
    generated_digest = hashlib.blake2b(generated_uuid.bytes, digest_size=8).digest()
    # Obtain URL safety and MongoDB collection name compatibility.
    generated_base64 = base64.b32encode(generated_digest).decode("ascii").casefold()

    # Remove terminating "=="
    clean_generated_base64 = generated_base64.rstrip("=")

    return clean_generated_base64


def delete_set_element(
    *,
    collection: pymongo.collection.Collection,
    document_type: str,
    set_id: str,
    rev: int,
) -> SetPutResult:
    """
    Delete a set element.

    Implemented by putting a tombstone document with "_deleted".
    The put operation will increment the "_rev", ensuring no race conflict.
    """

    # TODO: An improved put operation would verify this document and _rev exist.
    #       Pending such an operation, we'll hack it via extra operations.
    document_existing = get_set_element(
        collection=collection,
        document_type=document_type,
        set_id=set_id,
    )
    if document_existing is None:
        raise DocumentNotFoundException()
    if document_existing["_rev"] != rev:
        raise DocumentModifiedException(document_existing)

    tombstone_document = {
        "_type": document_type,
        "_set_id": set_id,
        "_rev": rev,
        "_deleted": True,
    }

    try:
        set_put_result = put_set_element(
            collection=collection,
            document_type=document_type,
            semantic_set_id=None,
            set_id=set_id,
            document=tombstone_document,
        )
    except pymongo.errors.DuplicateKeyError:
        document_existing = get_set_element(
            collection=collection,
            document_type=document_type,
            set_id=set_id,
        )

        raise DocumentModifiedException(document_existing=document_existing)

    return set_put_result


def ensure_index(
    *,
    collection: pymongo.collection.Collection,
):
    """
    Ensure the expected index is present on this collection.
    """

    # Examine existing indices
    index_information = collection.index_information()

    # Remove any indices that are not expected
    indices_unexpected = set(index_information.keys()) - {
        "_id_",
        PRIMARY_COLLECTION_INDEX_NAME,
    }
    for index_unexpected in indices_unexpected:
        del index_information[index_unexpected]
        collection.drop_index(index_unexpected)

    # Determine if an existing index needs replaced
    if PRIMARY_COLLECTION_INDEX_NAME in index_information:
        existing_index = index_information[PRIMARY_COLLECTION_INDEX_NAME]

        replace_index = False
        if not replace_index:
            replace_index = existing_index.keys() != {"key", "ns", "unique", "valid"}
        if not replace_index:
            replace_index = existing_index["key"] != PRIMARY_COLLECTION_INDEX
        if not replace_index:
            replace_index = existing_index["unique"] is not True

        if replace_index:
            del index_information[PRIMARY_COLLECTION_INDEX_NAME]
            collection.drop_index(PRIMARY_COLLECTION_INDEX_NAME)

    # Create the index
    if PRIMARY_COLLECTION_INDEX_NAME not in index_information:
        collection.create_index(
            PRIMARY_COLLECTION_INDEX,
            unique=True,
            name=PRIMARY_COLLECTION_INDEX_NAME,
        )


def get_multiple_types(
    *,
    collection: pymongo.collection.Collection,
    singleton_types: List[str],
    set_types: List[str],
# ) -> Dict[str, Union[List[dict], Optional[dict]]]:
)-> dict:
    timeit_start = timeit.default_timer()

    # Combine the document types
    combined_document_types = singleton_types + set_types

    # Parameters in query pipeline
    query_document_types = combined_document_types

    # Query pipeline
    pipeline = [
        # Obtain all documents of the desired "_type"
        {"$match": {"_type": {"$in": query_document_types}}},
        # Sort by "_rev",
        # store the most recent "_rev" in "result",
        # move forward with that version
        {"$sort": {"_rev": pymongo.DESCENDING}},
        {
            "$group": {
                "_id": {"_type": "$_type", "_set_id": "$_set_id"},
                "result": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$result"}},
        # Filter any document with "_deleted"
        {"$match": {"_deleted": {"$exists": False}}},
    ]

    # Execute pipeline, obtain list of results
    timeit_step = timeit.default_timer()
    with collection.aggregate(pipeline, batchSize=16*1024*1024) as pipeline_result:
        # Confirm a result was found
        documents = []
        timeit_query_initial = timeit.default_timer() - timeit_step
        if pipeline_result.alive:
            pipeline_result_len = len(pipeline_result._CommandCursor__data)
            documents = list(pipeline_result)
            documents_len = len(documents)
    timeit_query_complete = timeit.default_timer() - timeit_step

    # Create a result dictionary with a key for each type
    documents_by_type = {}
    for type_current in combined_document_types:
        documents_by_type[type_current] = []

    # Put each document with its type
    # TODO this could probably be accomplished in the above query
    timeit_step = timeit.default_timer()
    for document_current in documents:
        documents_by_type[document_current["_type"]].append(document_current)
    timeit_bucket = timeit.default_timer() - timeit_step

    # Normalize each type's list of documents
    timeit_step = timeit.default_timer()
    for type_current in combined_document_types:
        documents_by_type[type_current] = document_utils.normalize_documents(
            documents=documents_by_type[type_current]
        )
    timeit_normalize = timeit.default_timer() - timeit_step

    # Restore singleton types to a single item instead of a list
    if singleton_types:
        for type_singleton_current in singleton_types:
            result_documents_current = documents_by_type[type_singleton_current]
            if len(result_documents_current) == 0:
                documents_by_type[type_singleton_current] = None
            elif len(result_documents_current) == 1:
                documents_by_type[type_singleton_current] = result_documents_current[0]
            else:
                assert False

    timeit_total = timeit.default_timer() - timeit_start

    return {
        "documents_by_type": documents_by_type,
        "_timing": {
            "0 - total": format(timeit_total, 'f'),
            "1 - query_initial": format(timeit_query_initial, 'f'),
            "2 - query_complete": format(timeit_query_complete, 'f'),
            "3 - bucket": format(timeit_bucket, 'f'),
            "4 - normalize": format(timeit_normalize, 'f'),
            "documents_len": documents_len,
            "pipeline_result_len": pipeline_result_len
        },
    }


def get_set(
    *,
    collection: pymongo.collection.Collection,
    document_type: str,
) -> Optional[List[dict]]:
    """
    Retrieve all elements of set with "_type" of document_type.

    If none exist, return None.
    """

    # Parameters in query pipeline
    query_document_type = document_type

    # Query pipeline
    pipeline = [
        # Obtain all documents of the desired "_type"
        {"$match": {"_type": query_document_type}},
        # Sort by "_rev",
        # store the most recent "_rev" in "result",
        # move forward with that version
        {"$sort": {"_rev": pymongo.DESCENDING}},
        {
            "$group": {
                "_id": "$_set_id",
                "result": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$result"}},
        # Filter any document with "_deleted"
        {"$match": {"_deleted": {"$exists": False}}},
    ]

    # Execute pipeline, obtain list of results
    with collection.aggregate(pipeline) as pipeline_result:
        # Confirm a result was found
        if not pipeline_result.alive:
            return []

        documents = list(pipeline_result)

    # Normalize the list of documents
    documents = document_utils.normalize_documents(documents=documents)

    return documents


def get_set_element(
    *,
    collection: pymongo.collection.Collection,
    document_type: str,
    set_id: str,
) -> Optional[dict]:
    """
    Retrieve all elements of set with "_type" document_type.

    If none exist, return None.
    """

    # Parameters in query pipeline
    query_document_type = document_type
    query_set_id = set_id

    # Query pipeline
    pipeline = [
        # Obtain all documents of the desired "_type"
        {
            "$match": {
                "_type": query_document_type,
                "_set_id": query_set_id,
            }
        },
        # Sort by "_rev",
        # store the most recent "_rev" in "result",
        # move forward with that version
        {"$sort": {"_rev": pymongo.DESCENDING}},
        {
            "$group": {
                "_id": None,
                "result": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$result"}},
        # Filter any document with "_deleted"
        {"$match": {"_deleted": {"$exists": False}}},
    ]

    # Execute pipeline, obtain single result
    with collection.aggregate(pipeline) as pipeline_result:
        # Confirm a result was found
        if not pipeline_result.alive:
            return None

        document = pipeline_result.next()

    # Normalize the document
    document = document_utils.normalize_document(document=document)

    return document


def get_singleton(
    *,
    collection: pymongo.collection.Collection,
    document_type: str,
) -> Optional[dict]:
    """
    Retrieve current document for singleton with "_type" document_type.

    If none exists, return None.
    """

    # Parameters in query pipeline
    query_document_type = document_type

    # Query pipeline
    pipeline = [
        {"$match": {"_type": query_document_type}},
        {"$sort": {"_rev": pymongo.DESCENDING}},
        {
            "$group": {
                "_id": None,
                "result": {"$first": "$$ROOT"},
            }
        },
        {"$replaceRoot": {"newRoot": "$result"}},
    ]

    # Execute pipeline, obtain single result
    with collection.aggregate(pipeline) as pipeline_result:
        # Confirm a result was found
        if not pipeline_result.alive:
            return None

        document = pipeline_result.next()

    # Normalize the document
    document = document_utils.normalize_document(document=document)

    return document


def post_set_element(
    *,
    collection: pymongo.collection.Collection,
    document_type: str,
    semantic_set_id: Optional[str],
    document: dict,
) -> SetPostResult:
    """
    Put a set element document.
    - Document must not already include an "_id".
    - An existing "_type" must match document_type.
    - Document must not already include an "_set_id".
    - Document must not already include an "_rev".
    - semantic_set_id may indicate a field that will be treated like "_set_id".
      - Document must not already include an "semantic_set_id".
      - "semantic_set_id" will additionally be set to "_set_id".
    """

    # Work with a copy
    document = copy.deepcopy(document)

    # Document must not include an "_id",
    # as this indicates it was retrieved from the database.
    if "_id" in document:
        raise ValueError('Document must not have existing "_id"')

    # If a document includes a "_type", it must match document_type.
    if "_type" in document:
        if document["_type"] != document_type:
            raise ValueError('document["_type"] must match document_type')
    else:
        document["_type"] = document_type

    # Document must not include an "_set_id",
    # as post expects to assign this.
    if "_set_id" in document:
        raise ValueError('Document must not have existing "_set_id"')

    # Document must not include an "_rev",
    # as this indicates it was retrieved from the database.
    if "_rev" in document:
        raise ValueError('Document must not have existing "_rev"')

    # Generate a "_set_id" and a "_rev"
    generated_set_id = generate_set_id()
    document["_set_id"] = generated_set_id
    document["_rev"] = 1

    # If a semantic_set_id is specified
    if semantic_set_id:
        # Document must not include a semantic set id,
        # as post expects to assign this.
        if semantic_set_id in document:
            raise ValueError(
                'Document must not have existing "{}"'.format(semantic_set_id)
            )

        document[semantic_set_id] = generated_set_id

    # insert_one will modify the document to insert an "_id"
    document = document_utils.normalize_document(document=document)
    result = collection.insert_one(document=document)
    document = document_utils.normalize_document(document=document)

    return SetPostResult(
        inserted_count=1,
        inserted_id=str(result.inserted_id),
        inserted_set_id=generated_set_id,
        document=document,
    )


def put_set_element(
    *,
    collection: pymongo.collection.Collection,
    document_type: str,
    semantic_set_id: Optional[str],
    set_id: str,
    document: dict,
) -> SetPutResult:
    """
    Put a set element document.
    - Document must not already include an "_id".
    - An existing "_type" must match document_type.
    - An existing "_set_id" must match set_id.
    - An existing "_rev" will be incremented.
    - semantic_set_id may indicate a field that will be treated like "_set_id".
      - An existing "semantic_set_id" must match set_id.
      - An existing "semantic_set_id" must match an existing "_set_id".
      - "semantic_set_id" will additionally be set to "_set_id".
    """

    # Work with a copy
    document = copy.deepcopy(document)

    # Document must not include an "_id",
    # as this indicates it was retrieved from the database.
    if "_id" in document:
        raise ValueError('Document must not have existing "_id"')

    # If a document includes a "_type", it must match document_type.
    if "_type" in document:
        if document["_type"] != document_type:
            raise ValueError('document["_type"] must match document_type')
    else:
        document["_type"] = document_type

    # If a document includes a "_set_id", it must match set_id.
    if "_set_id" in document:
        if document["_set_id"] != set_id:
            raise ValueError('document["_set_id"] must match set_id')
    else:
        # Set the "_set_id"
        document["_set_id"] = set_id

    # Increment the "_rev"
    if "_rev" in document:
        if not isinstance(document["_rev"], int):
            raise ValueError('document["_rev"] must be int')

        # TODO: We could check to ensure the previous _rev actually exists.
        #       This is only relevant if the client has skipped ahead to some false future _rev.
        #       An ordered bulk operation could findUpdate the previous _rev to update an ignored field,
        #       then insert the new _rev (i.e., findUpdate would fail if the previous _rev did not exist,
        #       insert would fail if somebody else has already created the new _rev).
        #       If that field were to have actual meaning, this would need to be done in a transaction.

        document["_rev"] += 1
    else:
        document["_rev"] = 1

    # If a semantic_set_id is specified
    if semantic_set_id:
        # If a document includes a "semantic_set_id", it must match set_id.
        if semantic_set_id in document:
            if document[semantic_set_id] != set_id:
                raise ValueError(
                    'document["{}"] must match set_id'.format(semantic_set_id)
                )
        else:
            # Set the "semantic_set_id"
            document[semantic_set_id] = set_id

    # insert_one will modify the document to insert an "_id"
    document = document_utils.normalize_document(document=document)
    result = collection.insert_one(document=document)
    document = document_utils.normalize_document(document=document)

    return SetPutResult(
        inserted_count=1,
        inserted_id=str(result.inserted_id),
        inserted_set_id=set_id,
        document=document,
    )


def put_singleton(
    *,
    collection: pymongo.collection.Collection,
    document_type: str,
    document: dict,
) -> PutResult:
    """
    Put a singleton document.
    - Document must not already include an "_id".
    - An existing "_type" must match document_type.
    - An existing "_rev" will be incremented.
    """

    # Work with a copy
    document = copy.deepcopy(document)

    # Document must not include an "_id",
    # as this indicates it was retrieved from the database.
    if "_id" in document:
        raise ValueError('Document must not have existing "_id"')

    # If a document includes a "_type", it must match document_type.
    if "_type" in document:
        if document["_type"] != document_type:
            raise ValueError('document["_type"] must match document_type')
    else:
        document["_type"] = document_type

    # Increment the "_rev"
    if "_rev" in document:
        if not isinstance(document["_rev"], int):
            raise ValueError('document["_rev"] must be int')

        document["_rev"] += 1
    else:
        document["_rev"] = 1

    # insert_one will modify the document to insert an "_id"
    document = document_utils.normalize_document(document=document)
    result = collection.insert_one(document=document)
    document = document_utils.normalize_document(document=document)

    return PutResult(
        inserted_count=1,
        inserted_id=str(result.inserted_id),
        document=document,
    )


def unsafe_delete_set_element_destructive(
    *,
    collection: pymongo.collection.Collection,
    document_type: str,
    set_id: str,
) -> bool:
    """
    Delete a set element destructively,
    completely removing the document and its history of revisions.
    """

    # There is likely a race condition here, but our semantics for destructive deletion are weak.
    result = collection.delete_many(
        {
            "_type": document_type,
            "_set_id": set_id,
        }
    )

    return result.deleted_count > 0
