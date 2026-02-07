# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.16.7
#   kernelspec:
#     display_name: Python 3 (ipykernel)
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Patient Data Export
#
# A notebook exporting patient data for study analyses.

# %% [markdown]
# ## Definitions

# %% [markdown]
# ### Imports

# %%
import dataclasses
import io
import itertools
import json
import operator
import os
import pathlib
import pprint
import re
from enum import Enum
from typing import Dict, List, Optional, Union

import bson.objectid
import IPython.display
import ipywidgets
import nbformat
import pandas as pd
import pytz
import pyzipper
import scope.database.date_utils as date_utils
import scope.enums
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from scope.documents import document_set
from scope.populate.data.archive import Archive

# %% [markdown]
# ### Constants and Flags

# %%
# In development, it can be helpful to sample a subset of patients.
# If DEVELOPMENT_SAMPLE_PATIENTS <= 0, process all patients.
# If DEVELOPMENT_SAMPLE_PATIENTS > 0, randomly sample DEVELOPMENT_SAMPLE_PATIENTS patients.
DEVELOPMENT_SAMPLE_PATIENTS: int = -1

# In development, it can be helpful to skip per-patient export.
# If DEVELOPMENT_EXPORT_PER_PATIENT_DOCUMENTS, include per-patient export.
DEVELOPMENT_EXPORT_PER_PATIENT_DOCUMENTS: bool = True

# In development, it can be helpful to skip documents export.
# If DEVELOPMENT_EXPORT_COMBINED_DOCUMENTS, include documents export.
DEVELOPMENT_EXPORT_COMBINED_DOCUMENTS: bool = True


# %% [markdown]
# ### Utilities

# %% [markdown]
# ### Utility: documentation_as_markdown
#
# Returns a string containing markdown content recovered from a cell in this notebook.
#
# Intended to allow including the content of markdown cells as documentation in an export.

# %%
def documentation_as_markdown(documentation_name: str) -> str:
    # Load this same notebook.
    notebook = nbformat.read("patientdata.ipynb", nbformat.NO_CONVERT)

    # Go through each cell, looking for a match.
    for cell_current in notebook["cells"]:
        match = cell_current["cell_type"] == "markdown"
        if match:
            match = re.match(
                "^(#*) Documentation: ({})\\n(.*)".format(documentation_name),
                cell_current["source"],
            )

        if match:
            return cell_current["source"]

    # If no match was found, raise a ValueError.
    raise ValueError(
        "No matching documentation cell found: {}".format(documentation_name)
    )


# %% [markdown]
# ### Utility: ExportFile
#
# The path and contents of a file to be exported.

# %%
class ExportFileType(Enum):
    BYTES = "BYTES"
    CSV = "CSV"
    EXCEL = "EXCEL"
    MARKDOWN = "MARKDOWN"


@dataclasses.dataclass(frozen=True)
class ExportFile:
    path: pathlib.Path
    type: ExportFileType
    bytes: Optional[bytes]
    text: Optional[str]


# %% [markdown]
# ### Utility: export_dataframe_as_csv

# %%
def export_dataframe_as_csv(
    path: pathlib.Path,
    df: pd.DataFrame,
):
    # Extend any existing suffix.
    path = path.with_suffix(path.suffix + ".csv")

    csv_text = df.to_csv(index=False)

    export_file_list.append(
        ExportFile(
            path=path,
            type=ExportFileType.CSV,
            bytes=None,
            text=csv_text,
        )
    )


# %% [markdown]
# ### Utility: export_dataframe_as_excel

# %%
def export_dataframe_as_excel(
    path: pathlib.Path,
    df: pd.DataFrame,
):
    # Extend any existing suffix.
    path = path.with_suffix(path.suffix + ".xlsx")

    iobytes = io.BytesIO()
    # BytesIO works fine at runtime, but pandas does not list it as a valid excel_writer type.
    df.to_excel(iobytes, index=False)  # type: ignore[arg-type]
    excel_bytes = iobytes.getvalue()

    export_file_list.append(
        ExportFile(
            path=path,
            type=ExportFileType.EXCEL,
            bytes=excel_bytes,
            text=None,
        )
    )


# %% [markdown]
# ### Utility: export_dataframe

# %%
def export_dataframe(
    path: pathlib.Path,
    df: pd.DataFrame,
):
    export_dataframe_as_csv(path, df)
    export_dataframe_as_excel(path, df)


# %% [markdown]
# ### Utility: export_file_bytes

# %%
def export_file_bytes(
    path: pathlib.Path,
    file_bytes: bytes,
):
    export_file_list.append(
        ExportFile(
            path=path,
            type=ExportFileType.BYTES,
            bytes=file_bytes,
            text=None,
        )
    )


# %% [markdown]
# ### Utility: export_markdown

# %%
def export_markdown(
    path: pathlib.Path,
    markdown: str,
):
    path = path.with_suffix(path.suffix + ".md")

    export_file_list.append(
        ExportFile(
            path=path,
            type=ExportFileType.MARKDOWN,
            bytes=None,
            text=markdown,
        )
    )


# %% [markdown]
# ### Utility: dataframe_sanitize
#
# Sanitize contents of a dataframe that otherwise cannot be written to Excel.

# %%
def dataframe_sanitize(df: pd.DataFrame) -> pd.DataFrame:
    def sanitize_cell(value):
        if isinstance(value, str):
            value = ILLEGAL_CHARACTERS_RE.sub("?", value)

        return value

    return df.map(sanitize_cell)


# %% [markdown]
# ### Utility: dataframe_format_export
#
# Formats a dataframe for export.

# %%
def dataframe_format_export(
    df: pd.DataFrame,
    *,
    drop_empty_columns: Optional[bool] = False,
    drop_columns: Optional[List[str]] = None,
    rename_columns: Optional[Dict[str, str]] = None,
    sort_columns: Optional[List[str]] = None,
    sort_rows_by_columns: Optional[List[str]] = None,
) -> pd.DataFrame:
    # Ensure we are modifying a copy.
    df = df.copy()

    # If requested, drop empty columns.
    if drop_empty_columns:
        empty_columns = []
        for column_current in df.columns:
            is_empty = bool(
                df[column_current].isnull().all()
                or (
                    df[column_current]
                    .astype(str)
                    .str.strip()
                    .isin(["", "nan", "None"])
                    .all()
                )
            )
            if is_empty:
                empty_columns.append(column_current)

        df = df.drop(columns=empty_columns)

    # If requested, drop specific columns.
    # Be robust to the possibility that a column is not present.
    if drop_columns:
        df = df.drop(columns=drop_columns, errors="ignore")

    # If requested, rename specific columns.
    if rename_columns:
        df = df.rename(columns=rename_columns)

    # If requested, sort specific columns to the front.
    # Be robust to the possibility that a column is not present.
    # Be robust to the presence of additional columns.
    # Preserve existing order of additional columns after requested columns.
    if sort_columns:
        sort_columns = [
            column_current
            for column_current in sort_columns
            if column_current in df.columns
        ]
        sort_columns = sort_columns + [
            column_current
            for column_current in df.columns
            if column_current not in sort_columns
        ]

        df = df.loc[:, sort_columns]

    # If requested, sort rows by specific columns.
    # Be robust to the possibility that a column is not present.
    if sort_rows_by_columns:
        sort_rows_by_columns = [
            column_current
            for column_current in sort_rows_by_columns
            if column_current in df.columns
        ]

        df = df.sort_values(sort_rows_by_columns)

    return df


# %% [markdown]
# ## Input

# %% [markdown]
# ### Utility: archive_dir_path

# %%
# Path containing encrypted archives.
archive_dir_path = "../../../secrets/data"


# %% [markdown]
# ### Input Archive Suffix: archive_suffix

# %%
# Obtain suffix indicating desired version of encrypted archives.
# Do not include the '.zip' suffix.
def input_archive_suffix():
    # Based on archives in our path, identify possible suffixes.
    pattern = re.compile("archive_(multicare|scca)_([^_]+)_(\\d{8})(?:_(.+))?.zip")
    archive_file_names = [
        name_current
        for name_current in os.listdir(archive_dir_path)
        if pattern.search(name_current)
    ]
    archive_matches = [
        re.match(pattern, name_current) for name_current in archive_file_names
    ]
    archive_suffixes = list(
        {
            "{}_{}{}".format(
                match_current.group(2),
                match_current.group(3),
                "_" + match_current.group(4)
                if (len(match_current.groups()) > 3 and match_current.group(4))
                else "",
            )
            for match_current in archive_matches
            if match_current is not None
        }
    )

    # If there is only one possible value, no need for a choice.
    archive_suffix = None
    if len(archive_suffixes) == 1:
        archive_suffix = archive_suffixes[0]
    else:
        for id_current, suffix_current in enumerate(archive_suffixes, 1):
            print("[{}]: {}".format(id_current, suffix_current))

        archive_suffix = archive_suffixes[
            int(input("Encrypted archive suffix index: ")) - 1
        ]

    print(archive_suffix)

    return archive_suffix


archive_suffix = input_archive_suffix()

# %% [markdown]
# ### Input Archive Password: archive_password

# %%
# Obtain password to encrypted archives.
archive_password = input("Encrypted archive password: ")


# %% [markdown]
# ## Load Data

# %% [markdown]
# ### Decrypt Archives

# %% [markdown]
# #### Data: archive_multicare

# %%
def decrypt_archive_multicare():
    # Obtain name for each archive.
    archive_multicare_file_name = "archive_multicare_{}.zip".format(archive_suffix)

    # Obtain a full path to encrypted archive, relative to the location of the notebook.
    # Expects the encrypted archive to be in the "secrets/data" directory.
    archive_multicare_path = pathlib.Path(
        archive_dir_path,
        archive_multicare_file_name,
    )

    print("Decrypting archive:")
    print("{}".format(archive_multicare_path.resolve()))

    # Obtain the archive.
    archive_multicare = Archive.read_archive(
        archive_path=archive_multicare_path,
        password=archive_password,
    )

    print("{} documents.".format(len(archive_multicare.entries.values())))

    return archive_multicare


archive_multicare = decrypt_archive_multicare()


# %% [markdown]
# #### Data: archive_scca

# %%
def decrypt_archive_scca():
    # Obtain name for each archive.
    archive_scca_file_name = "archive_scca_{}.zip".format(archive_suffix)

    # Obtain a full path to encrypted archive, relative to the location of the notebook.
    # Expects the encrypted archive to be in the "secrets/data" directory.
    archive_scca_path = pathlib.Path(
        archive_dir_path,
        archive_scca_file_name,
    )

    print("Decrypting archive:")
    print("{}".format(archive_scca_path.resolve()))

    # Obtain the archive.
    archive_scca = Archive.read_archive(
        archive_path=archive_scca_path,
        password=archive_password,
    )

    print("{} documents.".format(len(archive_scca.entries.values())))

    return archive_scca


archive_scca = decrypt_archive_scca()


# %% [markdown]
# ### Decrypt MRN to RecordId

# %% [markdown]
# #### Data: mrn_to_record_id_bytes

# %% [markdown]
# #### Data: mrn_to_record_id

# %%
def decrypt_mrn_to_record_id():
    # Obtain a full path to encrypted archive, relative to the location of the notebook.
    # Expects the encrypted archive to be in the "secrets/data" directory.
    archive_mrn_to_record_id_path = pathlib.Path(
        archive_dir_path,
        "archive_mrn_to_record_id.zip",
    )

    # Open the file
    with open(
        archive_mrn_to_record_id_path,
        mode="rb",
    ) as archive_file:
        with pyzipper.AESZipFile(
            archive_file,
            "r",
            compression=pyzipper.ZIP_LZMA,
            encryption=pyzipper.WZ_AES,
        ) as archive_zipfile:
            # Set the zipfile password
            archive_zipfile.setpassword(archive_password.encode("utf-8"))

            # Confirm the zipfile is valid
            if archive_zipfile.testzip():
                raise ValueError("Invalid archive or password")

            # Retrieve the Excel file.
            excel_bytes = archive_zipfile.read(
                "archive_mrn_to_record_id/archive_mrn_to_record_id.xlsx"
            )
            df_mrn_to_record_id = pd.read_excel(io.BytesIO(excel_bytes))

            # Ensure MRN are treated as strings.
            df_mrn_to_record_id["MRN"] = df_mrn_to_record_id["MRN"].astype(str)

            # Return the Excel file and a dictionary.
            return (
                excel_bytes,
                df_mrn_to_record_id.set_index("MRN")["recordId"].to_dict(),
            )


mrn_to_record_id_bytes, mrn_to_record_id = decrypt_mrn_to_record_id()


# %% [markdown]
# ## Process Archives

# %% [markdown]
# ### Combine Patients DataFrames

# %%
def combine_patients_dataframes():
    # Get patient documents from MultiCare.
    documents_multicare_patients = (
        archive_multicare.collection_documents(
            collection="patients",
        )
        .remove_sentinel()
        .remove_revisions()
    )
    df_multicare_patients = pd.DataFrame.from_records(
        documents_multicare_patients.documents
    )
    df_multicare_patients["database"] = "multicare"

    # Get patient documents from SCCA.
    documents_scca_patients = (
        archive_scca.collection_documents(
            collection="patients",
        )
        .remove_sentinel()
        .remove_revisions()
    )
    df_scca_patients = pd.DataFrame.from_records(documents_scca_patients.documents)
    df_scca_patients["database"] = "fhcc"

    # Unify all current patient documents.
    df_combined_patients = pd.concat(
        [df_multicare_patients, df_scca_patients]
    ).reset_index(drop=True)

    # Sanitize once so contents dataframe can be exported.
    df_combined_patients = dataframe_sanitize(df_combined_patients)

    return df_combined_patients


df_archive_patients_raw = combine_patients_dataframes()

# %% [markdown]
# ### Reset Filtering and Sampling

# %% [markdown]
# #### Data: df_archive_patients

# %%
df_archive_patients = df_archive_patients_raw.copy()

# %% [markdown]
# ### Filter Pilot Patients
#
# Remove the 6 pilot patients.

# %%
df_archive_patients = df_archive_patients.drop(
    index=df_archive_patients[
        df_archive_patients["patientId"].isin(
            [
                "ymzwx6e6w6kqi",
                "mmmb54v52l7re",
                "ouoa4ucldbhie",
                "zazst4yu23a5q",
                "wf4btxqjtd2oa",
                "s3bcmgmp7gdss",
            ]
        )
    ].index.tolist()
).reset_index(drop=True)

# %% [markdown]
# ### Sample Patients
#
# In development, it can be helpful to sample a subset of patients.

# %%
if DEVELOPMENT_SAMPLE_PATIENTS > 0:
    df_archive_patients = df_archive_patients.sample(
        n=DEVELOPMENT_SAMPLE_PATIENTS
    ).reset_index(drop=True)


# %% [markdown]
# ### Utility: patient_documents

# %%
# Create a helper for accessing the document collection of a unified patient.
def patient_documents(row_patient) -> document_set.DocumentSet:
    if row_patient["database"] == "multicare":
        archive = archive_multicare
    elif row_patient["database"] == "fhcc":
        archive = archive_scca
    else:
        raise ValueError()

    return archive.collection_documents(collection=row_patient["collection"])


# %% [markdown]
# ## Prepare Data

# %% [markdown]
# ### Prepare Patients

# %% [markdown]
# #### Documentation: Patients
#
# All patients included in this export, based on `patientIdentity` documents.
# These are stored separately from the collection of documents associated with each patient.
# They provide an index of all patients, then we can access the collection of documents for each individual patient.
#
# A `patientIdentity` document may have been modified throughout the study (e.g., to change a patient name or email address).
# If the document was modified, this export includes only the final version.
# There is therefore exactly one row per patient.
#
# Data is originally taken from two database exports: from FHCC and from MultiCare.
# Raw data are merged, then a `database` column is added to indicate the origin of each patient.
#
# There were 6 pilot patients. These have been completely removed.
#
# TODO: The patient with `recordId` `1747` maps to two different `MRN` and `patientId`.
# This was because they moved from one system to another during the study.
# There is still a need to decide how to special case that patient.

# %% [markdown]
# #### Data: df_patients_raw

# %%
df_patients_raw = df_archive_patients.copy()

# %% [markdown]
# #### Data: df_patients
#
# Remove most fields, so they are not needlessly visible during export script development.
#
# Use `MRN` to map each patient to a `recordId`.

# %%
df_patients = df_patients_raw.copy()

# Ensure MRN are treated as strings.
df_patients["MRN"] = df_patients["MRN"].astype(str)

# Apply a transform to look up the recordId.
def transform_add_record_id(
    df_patients: pd.DataFrame,
) -> pd.DataFrame:
    def _transform_add_record_id_from_mrn(row):
        return str(mrn_to_record_id.get(row["MRN"], "???"))

    df_patients = df_patients.copy()
    df_patients["recordId"] = df_patients.apply(
        _transform_add_record_id_from_mrn, axis=1
    )

    return df_patients


df_patients = transform_add_record_id(df_patients)

# "collection" cannot be removed at this point, as it is used by later processing.
df_patients = dataframe_format_export(
    df_patients,
    drop_columns=[
        # Remove clutter.
        "_id",
        "_rev",
        "_set_id",
        "_type",
        # Remove identifiers.
        "cognitoAccount",  # Includes email.
        "name",
    ],
    sort_columns=[
        "recordId",
        "database",
        "patientId",
        "MRN",
        "collection",
    ],
    sort_rows_by_columns=[
        "recordId",
        "database",
        "patientId",
    ],
)

# %% [markdown]
# #### Data: patient_id_to_record_id

# %%
patient_id_to_record_id = (
    df_patients.copy().set_index("patientId")["recordId"].to_dict()
)


# %% [markdown]
# ### Prepare Per-Patient DocumentSets and DataFrames

# %% [markdown]
# #### Data: patient_id_to_documentset

# %%
def prepare_patient_id_to_documentset():
    patient_id_to_documentset = {}

    progress_max = len(df_patients)
    progress_patient_count = ipywidgets.IntProgress(min=0, max=progress_max)

    print("Preparing DocumentSet for {} Patients".format(progress_max))
    IPython.display.display(progress_patient_count)

    progress_patient_count.description = "{}/{}".format(0, progress_max)
    for patient_count, (row_current, patient_current) in enumerate(
        df_patients.iterrows()
    ):
        patient_id_current = patient_current["patientId"]
        patient_collection = patient_documents(patient_current.to_dict())

        patient_id_to_documentset[patient_id_current] = patient_collection

        progress_patient_count.description = "{}/{}".format(
            patient_count + 1, progress_max
        )
        progress_patient_count.value = patient_count + 1

    return patient_id_to_documentset


patient_id_to_documentset = prepare_patient_id_to_documentset()


# %% [markdown]
# #### Transform: transform_add_created
#
# Add a `_created` column to each document.

# %%
def transform_add_created(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    def _transform_add_created_from_id(row):
        datetime_parsed = bson.objectid.ObjectId(row["_id"]).generation_time.astimezone(
            pytz.utc
        )
        datetime_pacific = datetime_parsed.astimezone(
            pytz.timezone("America/Los_Angeles")
        )

        return datetime_pacific.strftime("%Y-%m-%dT%H:%M:%S")

    df_documents = df_documents.copy()
    df_documents["_created"] = df_documents.apply(
        _transform_add_created_from_id, axis=1
    )

    return df_documents


# %% [markdown]
# #### Transform: transform_add_record_id_and_patient_id
#
# Add a `patientId` column to each document.

# %%
def transform_add_record_id_and_patient_id(
    df_documents: pd.DataFrame,
    *,
    patient_id,
) -> pd.DataFrame:
    df_documents = df_documents.copy()
    df_documents["recordId"] = patient_id_to_record_id[patient_id]
    df_documents["_patientId"] = patient_id

    return df_documents


# %% [markdown]
# #### Data: patient_id_to_df_documents_raw

# %%
def prepare_patient_id_to_df_documents_raw():
    patient_id_to_df_documents_raw = {}

    progress_max = len(patient_id_to_documentset)
    progress_patient_count = ipywidgets.IntProgress(min=0, max=progress_max)

    print("Preparing DataFrame for {} Patients".format(progress_max))
    IPython.display.display(progress_patient_count)

    progress_patient_count.description = "{}/{}".format(0, progress_max)
    for patient_count, (patient_id_current, patient_documentset_current) in enumerate(
        patient_id_to_documentset.items()
    ):
        df_documents_raw_current = pd.DataFrame.from_records(
            patient_documentset_current.documents
        )

        # Sanitize contents for export.
        df_documents_raw_current = dataframe_sanitize(df_documents_raw_current)

        # Apply minimal transforms to the "raw" documents.
        df_documents_raw_current = transform_add_created(
            df_documents_raw_current,
        )
        df_documents_raw_current = transform_add_record_id_and_patient_id(
            df_documents_raw_current, patient_id=patient_id_current
        )

        patient_id_to_df_documents_raw[patient_id_current] = df_documents_raw_current

        progress_patient_count.description = "{}/{}".format(
            patient_count + 1, progress_max
        )
        progress_patient_count.value = patient_count + 1

    return patient_id_to_df_documents_raw


patient_id_to_df_documents_raw = prepare_patient_id_to_df_documents_raw()

# %%
df_documents_raw = pd.concat(patient_id_to_df_documents_raw.values(), ignore_index=True)


# %% [markdown]
# ## Transform Documents

# %% [markdown]
# ### Documentation: Common Fields
#
# Several common fields are shared across different analysis exports:
#
# - `_docType` identifies the type of the document.
#
# - `recordId` identifies the patient, according to the study id.
#
# - `_patientId` identifies the patient, according to the database id.
#
# - `_docId` uniquely identifies a document within the collection for a `_patientId`.
#
#   The combination of `_patientId` and `_docId` are persistent and unique.
#   This can support inspection and data cleaning, but is unlikely to be direclty used in analyses.
#
# - If there could be multiple instances of a document type (e.g., multiple assessment logs, multiple mood logs),
#   then documents include a type-specific identifier (e.g., `_assessmentLogId`, `_moodLogId`).
#
# - `_rev` identifies the version of the document (i.e., the revision).
#   If only one instance of a document type is allowed (e.g., a single safety plan),
#   this identifies revisions of that document over time.
#   If there could be multiple instances of a document type,
#   the combination of the type-specific identifier and the version identifies revisions of specific instances.
#
# - `_created` indicates when a document was created, recovered from an encoding within `_docId`.
#   This is provided in Pacific time.
#
# - `_deleted` indicates that a revision deleted the document.

# %% [markdown]
# ### Documentation: Activities
#
# Exported from `activity` documents. A single row is included for each `activity`.
#
# Includes common fields documented in `commonFields.md`.
#
# Notable transformations:
#
# - `valueLifeArea` and `valueName` are calculated via lookup of `valueId`.

# %% [markdown]
# ### Transform: transform_activity

# %%
def transform_activity(
    df_documents: pd.DataFrame,
    documents: document_set.DocumentSet,
) -> pd.DataFrame:
    # Deleted rows will not have a id, so restore that from the _set_id.
    def _transform_activity_id_deleted(row):
        if (
            row["_type"] == "activity"
            and pd.notna(row.get("_deleted", None))
            and row.get("_deleted", False)
        ):
            return row["_set_id"]

        return row.get("activityId", None)

    # Use the valueId to recover a valueLifeArea.
    def _transform_expand_value_life_area(row):
        if row["_type"] != "activity":
            return row.get("valueLifeArea", None)

        if pd.isna(row.get("valueId", None)) or not row.get("valueId", None):
            return None

        value_document = documents.filter_match(
            match_type="value",
            match_deleted=False,
            match_datetime_at=document_set.datetime_from_document_id(
                document_id=row["_id"]
            ),
            match_values={"valueId": row["valueId"]},
        ).unique()

        return value_document["lifeAreaId"]

    # Use the valueId to recover a valueName.
    def _transform_expand_value_name(row):
        if row["_type"] != "activity":
            return row.get("valueName", None)

        if pd.isna(row.get("valueId", None)) or not row.get("valueId", None):
            return None

        value_document = documents.filter_match(
            match_type="value",
            match_deleted=False,
            match_datetime_at=document_set.datetime_from_document_id(
                document_id=row["_id"]
            ),
            match_values={"valueId": row["valueId"]},
        ).unique()

        return value_document["name"]

    df_documents = df_documents.copy()
    df_documents["activityId"] = df_documents.apply(
        _transform_activity_id_deleted, axis=1
    )
    df_documents["valueLifeArea"] = df_documents.apply(
        _transform_expand_value_life_area, axis=1
    )
    df_documents["valueName"] = df_documents.apply(_transform_expand_value_name, axis=1)

    return df_documents


# %% [markdown]
# ### Documentation: Activity Logs
#
# Exported from `activityLog` documents. A single row is included for each `activityLog`.
#
# Includes common fields documented in `commonFields.md`.
#
# Notable values:
#
# - All values of `_rev` are `1`, as it was not possible to edit an activity log.
#
# - Documents include both `_created` and `dueDate`.
#
#   - Per common fields, `_created` indicates when a document was created.
#
#   - `dueDate` indicates what date the activity due in an `activitySchedule`.
#
# Notable transformations:
#
# - `value` and `activity` fields are calculated from a snapshot stored with the `activityLog`.

# %% [markdown]
# ### Transform: transform_activity_log

# %%
def transform_activity_log(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    def _transform_snapshot_value_id(row):
        if row["_type"] != "activityLog":
            return row.get("valueId", None)

        if "value" not in row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]:
            return None

        return row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]["value"][
            "valueId"
        ]

    def _transform_snapshot_value_life_area(row):
        if row["_type"] != "activityLog":
            return row.get("valueLifeArea", None)

        if "value" not in row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]:
            return None

        return row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]["value"][
            "lifeAreaId"
        ]

    def _transform_snapshot_value_name(row):
        if row["_type"] != "activityLog":
            return row.get("valueLifeName", None)

        if "value" not in row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]:
            return None

        return row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]["value"]["name"]

    def _transform_snapshot_activity_id(row):
        if row["_type"] != "activityLog":
            return row.get("activityId", None)

        return row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]["activity"][
            "activityId"
        ]

    def _transform_snapshot_activity_enjoyment(row):
        if row["_type"] != "activityLog":
            return row.get("activityEnjoyment", None)

        if (
            "enjoyment"
            not in row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]["activity"]
        ):
            return None

        return row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]["activity"][
            "enjoyment"
        ]

    def _transform_snapshot_activity_importance(row):
        if row["_type"] != "activityLog":
            return row.get("activityImportance", None)

        if (
            "importance"
            not in row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]["activity"]
        ):
            return None

        return row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]["activity"][
            "importance"
        ]

    def _transform_snapshot_activity_name(row):
        if row["_type"] != "activityLog":
            return row.get("activityName", None)

        return row["dataSnapshot"]["scheduledActivity"]["dataSnapshot"]["activity"][
            "name"
        ]

    # Format a dueDate.
    def _transform_snapshot_due_date(row):
        if row["_type"] != "activityLog":
            return row.get("dueDate", None)

        date_parsed = date_utils.parse_date(
            date=row["dataSnapshot"]["scheduledActivity"]["dueDate"]
        )

        return date_parsed.strftime("%Y-%m-%d")

    df_documents = df_documents.copy()
    df_documents["valueId"] = df_documents.apply(_transform_snapshot_value_id, axis=1)
    df_documents["valueLifeArea"] = df_documents.apply(
        _transform_snapshot_value_life_area, axis=1
    )
    df_documents["valueName"] = df_documents.apply(
        _transform_snapshot_value_name, axis=1
    )
    df_documents["dueDate"] = df_documents.apply(_transform_snapshot_due_date, axis=1)
    df_documents["activityId"] = df_documents.apply(
        _transform_snapshot_activity_id, axis=1
    )
    df_documents["activityEnjoyment"] = df_documents.apply(
        _transform_snapshot_activity_enjoyment, axis=1
    )
    df_documents["activityImportance"] = df_documents.apply(
        _transform_snapshot_activity_importance, axis=1
    )
    df_documents["activityName"] = df_documents.apply(
        _transform_snapshot_activity_name, axis=1
    )

    return df_documents


# %% [markdown]
# ### Documentation: Activity Schedules
#
# Exported from `activitySchedule` documents. A single row is included for each `activitySchedule`.
#
# Includes common fields documented in `commonFields.md`.
#
# - Documents include both `_created` and `scheduledDate`.
#
#   - Per common fields, `_created` indicates when a document was created.
#
#   - `scheduledDate` indicates what date was indicated for an `activitySchedule`.
#
# Notable transformations:
#
# - `activityEnjoyment`, `activityImportance`, `activityName`, `valueId` are calculated via lookup of `activityId`.
#
# - `valueLifeArea` and `valueName` are calculated via lookup of `valueId`.
#
# - `scheduleRepeatDays` is calculated from a raw `repeatDayFlags`.

# %% [markdown]
# ### Transform: transform_activity_schedule

# %%
def transform_activity_schedule(
    df_documents: pd.DataFrame,
    documents: document_set.DocumentSet,
) -> pd.DataFrame:
    # Deleted rows will not have a id, so restore that from the _set_id.
    def _transform_activity_schedule_id_deleted(row):
        if (
            row["_type"] == "activitySchedule"
            and pd.notna(row.get("_deleted", None))
            and row.get("_deleted", False)
        ):
            return row["_set_id"]

        return row.get("activityScheduleId", None)

    # Use the activityId to recover an enjoyment.
    def _transform_expand_activity_enjoyment(row):
        if row["_type"] != "activitySchedule":
            return row.get("activityEnjoyment", None)

        if pd.isna(row.get("activityId", None)) or not row.get("activityId", None):
            return None

        activity_document = documents.filter_match(
            match_type="activity",
            match_deleted=False,
            match_datetime_at=document_set.datetime_from_document_id(
                document_id=row["_id"]
            ),
            match_values={"activityId": row["activityId"]},
        ).unique()

        return activity_document.get("enjoyment", None)

    # Use the activityId to recover an importance.
    def _transform_expand_activity_importance(row):
        if row["_type"] != "activitySchedule":
            return row.get("activityImportance", None)

        if pd.isna(row.get("activityId", None)) or not row.get("activityId", None):
            return None

        activity_document = documents.filter_match(
            match_type="activity",
            match_deleted=False,
            match_datetime_at=document_set.datetime_from_document_id(
                document_id=row["_id"]
            ),
            match_values={"activityId": row["activityId"]},
        ).unique()

        return activity_document.get("importance", None)

    # Use the activityId to recover a name.
    def _transform_expand_activity_name(row):
        if row["_type"] != "activitySchedule":
            return row.get("activityName", None)

        if pd.isna(row.get("activityId", None)) or not row.get("activityId", None):
            return None

        activity_document = documents.filter_match(
            match_type="activity",
            match_deleted=False,
            match_datetime_at=document_set.datetime_from_document_id(
                document_id=row["_id"]
            ),
            match_values={"activityId": row["activityId"]},
        ).unique()

        return activity_document["name"]

    # Use the activityId to recover a valueId.
    def _transform_expand_activity_value_id(row):
        if row["_type"] != "activitySchedule":
            return row.get("valueId", None)

        if pd.isna(row.get("activityId", None)) or not row.get("activityId", None):
            return None

        activity_document = documents.filter_match(
            match_type="activity",
            match_deleted=False,
            match_datetime_at=document_set.datetime_from_document_id(
                document_id=row["_id"]
            ),
            match_values={"activityId": row["activityId"]},
        ).unique()

        return activity_document.get("valueId", None)

    # Use the valueId to recover a valueLifeArea.
    def _transform_expand_value_life_area(row):
        if row["_type"] != "activitySchedule":
            return row.get("valueLifeArea", None)

        if pd.isna(row.get("valueId", None)) or not row.get("valueId", None):
            return None

        value_document = documents.filter_match(
            match_type="value",
            match_deleted=False,
            match_datetime_at=document_set.datetime_from_document_id(
                document_id=row["_id"]
            ),
            match_values={"valueId": row["valueId"]},
        ).unique()

        return value_document["lifeAreaId"]

    # Use the valueId to recover a valueName.
    def _transform_expand_value_name(row):
        if row["_type"] != "activitySchedule":
            return row.get("valueName", None)

        if pd.isna(row.get("valueId", None)) or not row.get("valueId", None):
            return None

        value_document = documents.filter_match(
            match_type="value",
            match_deleted=False,
            match_datetime_at=document_set.datetime_from_document_id(
                document_id=row["_id"]
            ),
            match_values={"valueId": row["valueId"]},
        ).unique()

        return value_document["name"]

    # Recover the repeat day flags.
    def _transform_repeat_day_flags(row):
        if row["_type"] != "activitySchedule":
            return row.get("repeatDayFlags", None)

        if pd.isna(row.get("repeatDayFlags", None)) or not row.get(
            "repeatDayFlags", None
        ):
            return None

        result = ""
        for day_of_week_current in scope.enums.DayOfWeek:
            if row["repeatDayFlags"][day_of_week_current.value]:
                result += day_of_week_current.value[0:2]

        return result

    df_documents = df_documents.copy()
    df_documents["activityScheduleId"] = df_documents.apply(
        _transform_activity_schedule_id_deleted, axis=1
    )
    df_documents["activityEnjoyment"] = df_documents.apply(
        _transform_expand_activity_enjoyment, axis=1
    )
    df_documents["activityImportance"] = df_documents.apply(
        _transform_expand_activity_importance, axis=1
    )
    df_documents["activityName"] = df_documents.apply(
        _transform_expand_activity_name, axis=1
    )
    df_documents["valueId"] = df_documents.apply(
        _transform_expand_activity_value_id, axis=1
    )
    df_documents["valueLifeArea"] = df_documents.apply(
        _transform_expand_value_life_area, axis=1
    )
    df_documents["valueName"] = df_documents.apply(_transform_expand_value_name, axis=1)
    df_documents["repeatDayFlags"] = df_documents.apply(
        _transform_repeat_day_flags, axis=1
    )

    return df_documents


# %% [markdown]
# ### Documentation: Assessments
#
# Exported from `assessment` documents. A single row is included for each `assessment`.
#
# Includes common fields documented in `commonFields.md`.

# %% [markdown]
# ### Transform: transform_assessment

# %%
def transform_assessment(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    df_documents = df_documents.copy()

    # Medication tracking was never activated.
    df_documents = df_documents.loc[
        (df_documents["_type"] != "assessment")
        | (
            (df_documents["_type"] == "assessment")
            & (df_documents["assessmentId"] != "medication")
        )
    ]

    return df_documents


# %% [markdown]
# ### Documentation: Assessment Logs
#
# Exported from `assessmentLog` documents. A single row is included for each `assessmentLog`.
#
# Includes common fields documented in `commonFields.md`.
#
# Notable values:
#
# - `assessmentId` will be either `gad-7` or `phq-9`.
#
# - Documents include both `_created` and `recordedDate`.
#
#   - Per common fields, `_created` indicates when a document was created.
#
#   - `recordedDate` indicates what date was indicated for an `assessmentLog`.
#
#   - For assessment logs submitted via the patient app, these were the same.
#
#   - For assessment logs submitted via the provider registry, the provider entered the date of the assessment log.
#
# Notable transformations:
#
# - `recordedDate` is calculated in Pacific time from a raw `recordedDateTime`.
#
# - `submittedBy` is calculated from a raw `patientSubmitted`.
#
# - If individual scale components were available in a raw `pointValues`,
#   they were promoted to columns (e.g., `gad7Anxious`, `phq9Interest`).
#
# - An assessment score (i.e., `gad7Score`, `phq9Score`)
#   was taken from a raw `totalScore` or by summing the values in a raw `pointValues`.
#
# TODO: Inspecting a sample of revised assessment logs suggests there will not be a simple approach to data cleaning.
#
# TODO: `submittedBy` value of `SW` is potentially misleading.
# These were created using the registry, but not necessarily by a social worker.
#
# TODO: `todo_scheduledAssessmentId` is present for patient-submitted entries, may allow recovering information about an assessment schedule.
# It is unclear how correct this field is, so it may be best to not rely upon it.
#
# TODO: `todo_submittedByProviderId` is present for registry-submitted entries, may allow recovering information about who submitted an entry.

# %% [markdown]
# ### Transform: transform_assessment_log

# %%
def transform_assessment_log(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # Pull each value of the gad-7 assessment scale out to its own column.
    def _transform_gad7_points(
        df_documents: pd.DataFrame,
    ) -> pd.DataFrame:
        def _factory_transform_gad7_points_key(keyJson):
            def _transform_gad7_points_key(row):
                if row["_type"] != "assessmentLog":
                    return None
                if row["assessmentId"] != "gad-7":
                    return None
                if not row["pointValues"]:
                    return None

                return row["pointValues"][keyJson]

            return _transform_gad7_points_key

        gad7EnumMap = {
            "Anxious": "gad7Anxious",
            "Constant worrying": "gad7ConstantWorrying",
            "Worrying too much": "gad7WorryingTooMuch",
            "Trouble relaxing": "gad7TroubleRelaxing",
            "Restless": "gad7Restless",
            "Irritable": "gad7Irritable",
            "Afraid": "gad7Afraid",
        }

        for (keyJson, keyExport) in gad7EnumMap.items():
            df_documents[keyExport] = df_documents.apply(
                _factory_transform_gad7_points_key(keyJson), axis=1
            )

        return df_documents

    # Obtain or calculate a gad-7 score.
    def _transform_gad7_score(row):
        if row["_type"] != "assessmentLog":
            return row.get("gad7Score", None)
        if row["assessmentId"] != "gad-7":
            return row.get("gad7Score", None)

        # Some rows already provide a totalScore.
        if "totalScore" in row and not pd.isna(row["totalScore"]):
            return row["totalScore"]

        # Otherwise we need to sum the pointValues.
        if "pointValues" in row and row["pointValues"]:
            return sum(row["pointValues"].values())

        # We should always have one or the other.
        raise ValueError()

    # Pull each value of the phq-9 assessment scale out to its own column.
    def _transform_phq9_points(
        df_documents: pd.DataFrame,
    ) -> pd.DataFrame:
        def _factory_transform_phq9_points_key(keyJson):
            def _transform_phq9_points_key(row):
                if row["_type"] != "assessmentLog":
                    return None
                if row["assessmentId"] != "phq-9":
                    return None
                if not row["pointValues"]:
                    return None

                return row["pointValues"][keyJson]

            return _transform_phq9_points_key

        phq9EnumMap = {
            "Interest": "phq9Interest",
            "Mood": "phq9Mood",
            "Sleep": "phq9Sleep",
            "Energy": "phq9Energy",
            "Appetite": "phq9Appetite",
            "Guilt": "phq9Guilt",
            "Concentrating": "phq9Concentrating",
            "Motor": "phq9Motor",
            "Suicide": "phq9Suicide",
        }

        for (keyJson, keyExport) in phq9EnumMap.items():
            df_documents[keyExport] = df_documents.apply(
                _factory_transform_phq9_points_key(keyJson), axis=1
            )

        return df_documents

    # Obtain or calculate a phq-9 score.
    def _transform_phq9_score(row):
        if row["_type"] != "assessmentLog":
            return row.get("phq9Score", None)
        if row["assessmentId"] != "phq-9":
            return row.get("phq9Score", None)

        # Some rows already provide a totalScore.
        if "totalScore" in row and not pd.isna(row["totalScore"]):
            return row["totalScore"]

        # Otherwise we need to sum the pointValues.
        if "pointValues" in row and row["pointValues"]:
            return sum(row["pointValues"].values())

        # We should always have one or the other.
        raise ValueError()

    # Format a recordedDate.
    def _transform_recorded_date(row):
        if row["_type"] != "assessmentLog":
            return row.get("assessmentLogRecordedDate", None)

        datetime_parsed = date_utils.parse_datetime(datetime=row["recordedDateTime"])
        datetime_pacific = datetime_parsed.astimezone(
            pytz.timezone("America/Los_Angeles")
        )

        return datetime_pacific.strftime("%Y-%m-%d")

    def _transform_scheduled_assessment_id(row):
        if row["_type"] != "assessmentLog":
            return row.get("assessmentLogScheduledAssessmentId", None)

        # Logs labeled on-demand should all be submitted by a social worker.
        if row["scheduledAssessmentId"] == "on-demand":
            if row["patientSubmitted"] == True:
                raise ValueError()

            return None

        return row["scheduledAssessmentId"]

    # Format a submittedBy column as requested.
    def _transform_submitted_by(row):
        if row["_type"] != "assessmentLog":
            return row.get("assessmentLogSubmittedBy", None)

        if row["patientSubmitted"] == True:
            return "Pt"
        elif row["patientSubmitted"] == False:
            return "SW"
        else:
            raise ValueError()

    df_documents = df_documents.copy()
    df_documents = _transform_gad7_points(df_documents)
    df_documents["gad7Score"] = df_documents.apply(_transform_gad7_score, axis=1)
    df_documents = _transform_phq9_points(df_documents)
    df_documents["phq9Score"] = df_documents.apply(_transform_phq9_score, axis=1)
    df_documents["assessmentLogRecordedDate"] = df_documents.apply(
        _transform_recorded_date, axis=1
    )
    df_documents["assessmentLogScheduledAssessmentId"] = df_documents.apply(
        _transform_scheduled_assessment_id, axis=1
    )
    df_documents["assessmentLogSubmittedBy"] = df_documents.apply(
        _transform_submitted_by, axis=1
    )

    return df_documents


# %% [markdown]
# ### Documentation: Case Reviews
#
# Exported from `caseReview` documents. A single row is included for each `caseReview`.
#
# Includes common fields documented in `commonFields.md`.

# %% [markdown]
# ### Transform: transform_case_review

# %%
def transform_case_review(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # Elevate up the name of the psychiatrist.
    def _transform_consulting_psychiatrist(row):
        if row["_type"] != "caseReview":
            return row.get("consultingPsychiatrist", None)

        return row["consultingPsychiatrist"]["name"]

    # Format date of case review.
    def _transform_case_review_date(row):
        if row["_type"] != "caseReview":
            return row.get("date", None)

        date_parsed = date_utils.parse_date(
            date=row["date"]
        )

        return date_parsed.strftime("%Y-%m-%d")

    df_documents = df_documents.copy()
    df_documents["consultingPsychiatrist"] = df_documents.apply(_transform_consulting_psychiatrist, axis=1)
    df_documents["date"] = df_documents.apply(_transform_case_review_date, axis=1)

    return df_documents


# %% [markdown]
# ### Documentation: Clinical History
#
# Exported from `clinicalHistory` documents. A single row is included for each `clinicalHistory`.
#
# Includes common fields documented in `commonFields.md`.

# %% [markdown]
# ### Transform: transform_clinical_history

# %%
def transform_clinical_history(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # Expand currentTreatmentRegimen (cancerTreatmentRegimenFlags) into one column per flag.
    def _factory_transform_current_treatment_regimen_key(keyJson):
        def _transform_key(row):
            if row["_type"] != "clinicalHistory":
                return None
            regimen = row.get("currentTreatmentRegimen")
            if not isinstance(regimen, dict):
                return None
            return regimen.get(keyJson)

        return _transform_key

    currentTreatmentRegimenEnumMap = {
        "Surgery": "currentTreatmentRegimenSurgery",
        "Chemotherapy": "currentTreatmentRegimenChemotherapy",
        "Radiation": "currentTreatmentRegimenRadiation",
        "Stem Cell Transplant": "currentTreatmentRegimenStemCellTransplant",
        "Immunotherapy": "currentTreatmentRegimenImmunotherapy",
        "CAR-T": "currentTreatmentRegimenCART",
        "Endocrine": "currentTreatmentRegimenEndocrine",
        "Surveillance": "currentTreatmentRegimenSurveillance",
        "Other": "currentTreatmentRegimenOtherFlag",
    }

    df_documents = df_documents.copy()
    for (keyJson, keyExport) in currentTreatmentRegimenEnumMap.items():
        df_documents[keyExport] = df_documents.apply(
            _factory_transform_current_treatment_regimen_key(keyJson), axis=1
        )

    return df_documents


# %% [markdown]
# ### Documentation: Mood Logs
#
# Exported from `moodLog` documents. A single row is included for each `moodLog`.
#
# Includes common fields documented in `commonFields.md`.
#
# Notable values:
#
# - All values of `_rev` are `1`, as it was not possible to edit a mood log.

# %% [markdown]
# ### Transform: transform_mood_log

# %%
def transform_mood_log(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # No transformations are needed.
    return df_documents


# %% [markdown]
# ### Documentation: Patient Profile
#
# Exported from `profile` (patientProfile) documents. A single row is included for each `profile`.
#
# Includes common fields documented in `commonFields.md`.

# %% [markdown]
# ### Transform: transform_patient_profile

# %%
def transform_patient_profile(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # Flatten primaryCareManager to primaryCareManagerName.
    def _transform_primary_care_manager_name(row):
        if row["_type"] != "profile":
            return None
        primary_care_manager = row.get("primaryCareManager")
        if not isinstance(primary_care_manager, dict):
            return None
        return primary_care_manager.get("name")

    # Expand race (PatientRaceFlags) into one column per flag.
    def _factory_transform_race_key(keyJson):
        def _transform_key(row):
            if row["_type"] != "profile":
                return None
            race_obj = row.get("race")
            if not isinstance(race_obj, dict):
                return None
            return race_obj.get(keyJson)

        return _transform_key

    raceEnumMap = {
        "American Indian or Alaska Native": "raceAmericanIndianOrAlaskaNative",
        "Asian or Asian American": "raceAsianOrAsianAmerican",
        "Black or African American": "raceBlackOrAfricanAmerican",
        "Native Hawaiian or Other Pacific Islander": "raceNativeHawaiianOrOtherPacificIslander",
        "White": "raceWhite",
        "Unknown": "raceUnknown",
    }

    # Expand discussionFlag (DiscussionFlags) into one column per flag.
    def _factory_transform_discussion_flag_key(keyJson):
        def _transform_key(row):
            if row["_type"] != "profile":
                return None
            discussion_flag = row.get("discussionFlag")
            if not isinstance(discussion_flag, dict):
                return None
            return discussion_flag.get(keyJson)

        return _transform_key

    discussionFlagEnumMap = {
        "Flag as safety risk": "discussionFlagFlagAsSafetyRisk",
        "Flag for discussion": "discussionFlagFlagForDiscussion",
    }

    # Format enrollmentDate as YYYY-MM-DD.
    def _transform_enrollment_date(row):
        if row["_type"] != "profile":
            return row.get("enrollmentDate", None)
        if pd.isna(row.get("enrollmentDate", None)) or not row.get("enrollmentDate"):
            return None
        date_parsed = date_utils.parse_date(date=row["enrollmentDate"])
        return date_parsed.strftime("%Y-%m-%d")

    df_documents = df_documents.copy()
    df_documents["enrollmentDate"] = df_documents.apply(
        _transform_enrollment_date, axis=1
    )
    df_documents["primaryCareManagerName"] = df_documents.apply(
        _transform_primary_care_manager_name, axis=1
    )
    for (keyJson, keyExport) in raceEnumMap.items():
        df_documents[keyExport] = df_documents.apply(
            _factory_transform_race_key(keyJson), axis=1
        )
    for (keyJson, keyExport) in discussionFlagEnumMap.items():
        df_documents[keyExport] = df_documents.apply(
            _factory_transform_discussion_flag_key(keyJson), axis=1
        )

    return df_documents


# %% [markdown]
# ### Documentation: Review Mark
#
# Exported from `reviewMark` documents. A single row is included for each `reviewMark`.
#
# Includes common fields documented in `commonFields.md`.

# %% [markdown]
# ### Transform: transform_review_mark

# %%
def transform_review_mark(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # No transformations are needed.
    return df_documents


# %% [markdown]
# ### Documentation: Safety Plan
#
# Exported from `safetyPlan` documents. A single row is included for each `safetyPlan`.
#
# Includes common fields documented in `commonFields.md`.

# %% [markdown]
# ### Transform: transform_safety_plan

# %%
def transform_safety_plan(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # No transformations are needed.
    return df_documents


# %% [markdown]
# ### Documentation: Session
#
# Exported from `session` documents. A single row is included for each `session`.
#
# Includes common fields documented in `commonFields.md`.

# %% [markdown]
# ### Transform: transform_session

# %%
def transform_session(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # Expand behavioralStrategyChecklist (behavioralStrategyChecklistFlags) into one column per flag.
    def _factory_transform_behavioral_strategy_checklist_key(keyJson):
        def _transform_key(row):
            if row["_type"] != "session":
                return None
            checklist = row.get("behavioralStrategyChecklist")
            if not isinstance(checklist, dict):
                return None
            return checklist.get(keyJson)

        return _transform_key

    behavioralStrategyChecklistEnumMap = {
        "Behavioral Activation": "behavioralStrategyChecklistBehavioralActivation",
        "Motivational Interviewing": "behavioralStrategyChecklistMotivationalInterviewing",
        "Problem Solving Therapy": "behavioralStrategyChecklistProblemSolvingTherapy",
        "Cognitive Therapy": "behavioralStrategyChecklistCognitiveTherapy",
        "Mindfulness Strategies": "behavioralStrategyChecklistMindfulnessStrategies",
        "Supportive Therapy": "behavioralStrategyChecklistSupportiveTherapy",
        "Other": "behavioralStrategyChecklistOther",
    }

    # Expand behavioralActivationChecklist (bAChecklistFlags) into one column per flag.
    def _factory_transform_behavioral_activation_checklist_key(keyJson):
        def _transform_key(row):
            if row["_type"] != "session":
                return None
            checklist = row.get("behavioralActivationChecklist")
            if not isinstance(checklist, dict):
                return None
            return checklist.get(keyJson)

        return _transform_key

    behavioralActivationChecklistEnumMap = {
        "Review of the BA model": "behavioralActivationChecklistReviewOfTheBAModel",
        "Values and goals assessment": "behavioralActivationChecklistValuesAndGoalsAssessment",
        "Activity scheduling": "behavioralActivationChecklistActivityScheduling",
        "Mood and activity monitoring": "behavioralActivationChecklistMoodAndActivityMonitoring",
        "Relaxation": "behavioralActivationChecklistRelaxation",
        "Positive reinforcement": "behavioralActivationChecklistPositiveReinforcement",
        "Managing avoidance behaviors": "behavioralActivationChecklistManagingAvoidanceBehaviors",
        "Problem-solving": "behavioralActivationChecklistProblemSolving",
    }

    df_documents = df_documents.copy()
    for (keyJson, keyExport) in behavioralStrategyChecklistEnumMap.items():
        df_documents[keyExport] = df_documents.apply(
            _factory_transform_behavioral_strategy_checklist_key(keyJson), axis=1
        )
    for (keyJson, keyExport) in behavioralActivationChecklistEnumMap.items():
        df_documents[keyExport] = df_documents.apply(
            _factory_transform_behavioral_activation_checklist_key(keyJson), axis=1
        )

    return df_documents


# %% [markdown]
# ### Documentation: Values
#
# Exported from `value` documents. A single row is included for each `value`.
#
# Includes common fields documented in `commonFields.md`.

# %% [markdown]
# ### Transform: transform_value

# %%
def transform_value(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # Deleted rows will not have a id, so restore that from the _set_id.
    def _transform_value_id_deleted(row):
        if (
            row["_type"] == "value"
            and pd.notna(row.get("_deleted", None))
            and row.get("_deleted", False)
        ):
            return row["_set_id"]

        return row.get("valueId", None)

    df_documents = df_documents.copy()
    df_documents["valueId"] = df_documents.apply(_transform_value_id_deleted, axis=1)

    return df_documents


# %% [markdown]
# ### Documentation: Values Inventory
#
# Exported from `valuesInventory` documents. A single row is included for each `valuesInventory`.
#
# Includes common fields documented in `commonFields.md`.

# %% [markdown]
# ### Transform: transform_values_inventory

# %%
def transform_values_inventory(
    df_documents: pd.DataFrame,
) -> pd.DataFrame:
    # No transformations are needed.
    return df_documents


# %% [markdown]
# ### Utility: apply_transforms

# %% [markdown]
# ### Data: patient_id_to_df_documents

# %%
def apply_transforms(
    df_documents: pd.DataFrame,
    documents: document_set.DocumentSet,
) -> pd.DataFrame:
    df_documents = df_documents.copy()
    df_documents = transform_activity(
        df_documents,
        documents,
    )
    df_documents = transform_activity_log(
        df_documents,
    )
    df_documents = transform_activity_schedule(
        df_documents,
        documents,
    )
    df_documents = transform_assessment(
        df_documents,
    )
    df_documents = transform_assessment_log(
        df_documents,
    )
    df_documents = transform_case_review(
        df_documents,
    )
    df_documents = transform_clinical_history(
        df_documents,
    )
    df_documents = transform_mood_log(
        df_documents,
    )
    df_documents = transform_patient_profile(
        df_documents,
    )
    df_documents = transform_review_mark(
        df_documents,
    )
    df_documents = transform_safety_plan(
        df_documents,
    )
    df_documents = transform_session(
        df_documents,
    )
    df_documents = transform_value(
        df_documents,
    )
    df_documents = transform_values_inventory(
        df_documents,
    )

    return df_documents


# %%
def prepare_transform_patient_documents():
    patient_id_to_df_documents = {}

    progress_max = len(patient_id_to_df_documents_raw)
    progress_patient_count = ipywidgets.IntProgress(min=0, max=progress_max)

    print("Transforming DataFrame for {} Patients".format(progress_max))
    IPython.display.display(progress_patient_count)

    progress_patient_count.description = "{}/{}".format(0, progress_max)
    for patient_count, (patient_id_current, df_documents_raw_current) in enumerate(
        patient_id_to_df_documents_raw.items()
    ):
        patient_id_to_df_documents[patient_id_current] = apply_transforms(
            df_documents_raw_current.copy(),
            patient_id_to_documentset[patient_id_current],
        )

        progress_patient_count.description = "{}/{}".format(
            patient_count + 1, progress_max
        )
        progress_patient_count.value = patient_count + 1

    return patient_id_to_df_documents


patient_id_to_df_documents = prepare_transform_patient_documents()

# %% [markdown]
# ### Prepare Combined Documents DataFrame

# %% [markdown]
# #### Data: df_documents_raw

# %%
df_documents_raw = pd.concat(patient_id_to_df_documents_raw.values(), ignore_index=True)

# %% [markdown]
# #### Data: df_documents

# %%
df_documents = pd.concat(patient_id_to_df_documents.values(), ignore_index=True)

# %% [markdown]
# ## Export

# %% [markdown]
# ### Reset Export File List

# %%
export_file_list: List[ExportFile] = []

# %% [markdown]
# ### Documentation: Export
#
# This folder contains an export of SCOPE platform data.
# This includes patient data, should always be stored in an encrypted format, and should be treated as highly sensitive.
# Tables are commonly exported in both Excel and comma-separated formats
# (i.e., `.xlsx` via `pd.DataFrame.to_excel`, `.csv` via `pd.DataFrame.to_csv`).
# Excel will typically be easier to visually inspect,
# while comma-separated may be easier for R-based analyses.
#
# The root folder contains exports that are intended to be used in analyses.
#
# - `patients` is a list of all patients included in the export. Documentation in `patients.md`.
# - `activities` is an export of all `activity` documents. Documentation in `activities.md`.
# - `activityLogs` is an export of all `activityLog` documents. Documentation in `activityLogs.md`.
# - `activitySchedules` is an export of all `activitySchedule` documents. Documentation in `activitySchedules.md`.
# - `assessments` is an export of all `assessment` documents. Documentation in `assessments.md`.
# - `assessmentsGad7` is an export of all GAD-7 `assessmentLog` documents. Documentation in `assessmentLogs.md`.
# - `assessmentsPhq9` is an export of all PHQ-9 `assessmentLog` documents. Documentation in `assessmentLogs.md`.
# - `clinicalHistory` is an export of all `clinicalHistory` documents. Documentation in `clinicalHistory.md`.
# - `moodLogs` is an export of all `moodLog` documents. Documentation in `moodLogs.md`.
# - `patientProfiles` is an export of all `profile` documents. Documentation in `patientProfiles.md`.
# - `reviewMarks` is an export of all `reviewMark` documents. Documentation in `reviewMarks.md`.
# - `safetyPlans` is an export of all `safetyPlan` documents. Documentation in `safetyPlans.md`.
# - `sessions` is an export of all `session` documents. Documentation in `sessions.md`.
# - `values` is an export of all `value` documents. Documentation in `values.md`.
# - `valuesInventories` is an export of all `valuesInventory` documents. Documentation in `valuesInventories.md`.
#
# Several of the above data types are related.
#
# - A person may have configured one or more `value`.
# - A person may have configured one or more `activity`. Each may have a `value` associated with it.
# - A `activity` may have one or more `activitySchedule` configured. These may be one-time or repeating.
# - Not currently included in any analysis export, creation of an `activitySchedule` also created of a set of `scheduledActivity` instances (i.e., one for each day the activity was scheduled).
# - A person could complete an `activityLog` corresponding to a `scheduledActivity`.
#
# There was also a significant redesign of the relationship between `value` and `activity` documents in the `v0.7.0` release deployed on 2023-04-29.
# - Release notes at: https://github.com/uwscope/scope-web/releases/tag/v0.7.0
# - Prior to that release, a person was required to first create a `value` and then an `activity`. Every `activity` had an associated `value`.
# - Beginning with that release, a person could create a `value` or an `activity` independently. Associating an `activity` with a `value` became optional.
#
# The `data` folder contains additional exports, intended to support inspection of and communication around underlying data.
# Exports are prepared in a multi-step process, converting a database of JSON documents into tables for analyses.
#
# - Note that document tables are sparse, as most documents (i.e., rows) do not contain most values (i.e., columns).
#   Each row includes a `_type` taken from the JSON document, commonly used for filtering to specific types of documents.
#
# - Raw JSON documents are first loaded into a table for each patient.
#   This is the raw underlying data, included in the export to allow inspection.
#   The `data/patients` folder includes a folder for each patient, named according to the `patientId`.
#
# - Tables for all patients are combined in a single large table, exported as `documents.raw`.
#   This is all of the raw data and contains everything that is available.
#
# - A series of transformations are applied to the single large table.
#   Each transformation computes one or more new columns that are added to the single large table.
#
# - After all transformations are completed, the single large table is exported as `documents.transformed`.
#   Filtering the single large table by `patientId`, transformed tables are also exported to the each folder in `data/patients`.
#   These are included in the export to allow inspection.
#
# - Tables intended for analyses are then exported as different subsets of `documents.transformed`.
#
# The `config` folder contains additional configuration that was used in the export.
# If a change in configuration is needed, these files should be modified and then used in a new export.
#
# - `archive_mrn_to_record_id.xlsx` contains the mapping from `MRN` to `recordId` that was used in this export.
#

# %%
export_markdown(pathlib.Path("documentation"), documentation_as_markdown("Export"))
export_markdown(
    pathlib.Path("commonFields"), documentation_as_markdown("Common Fields")
)

# %% [markdown]
# ### Patients
#
# - Documented above in "Documentation: Patients Export".

# %%
export_markdown(
    pathlib.Path("patients"),
    documentation_as_markdown("Patients"),
)

export_file_bytes(
    pathlib.Path(
        "config",
        "archive_mrn_to_record_id.xlsx",
    ),
    mrn_to_record_id_bytes,
)

export_dataframe(
    pathlib.Path(
        "data",
        "patients.raw",
    ),
    df_patients_raw,
)

export_dataframe(
    pathlib.Path(
        "patients",
    ),
    dataframe_format_export(
        df_patients,
        drop_columns=["collection"],
    ),
)


# %% [markdown]
# ### Per-Patient Documents

# %%
def export_per_patient_documents():
    progress_max = len(df_patients)
    progress_patient_count = ipywidgets.IntProgress(min=0, max=progress_max)

    print("Per-Patient Export for {} Patients".format(progress_max))
    IPython.display.display(progress_patient_count)

    progress_patient_count.description = "{}/{}".format(0, progress_max)
    for patient_count, (row_current, patient_current) in enumerate(
        df_patients.iterrows()
    ):
        patient_id_current = patient_current["patientId"]

        df_documents_raw_current = patient_id_to_df_documents_raw[patient_id_current]
        export_dataframe(
            pathlib.Path(
                "data",
                "patients",
                "patient_{}".format(patient_id_current),
                "patient_{}.raw".format(patient_id_current),
            ),
            df_documents_raw_current,
        )

        df_documents_current = patient_id_to_df_documents[patient_id_current]
        export_dataframe(
            pathlib.Path(
                "data",
                "patients",
                "patient_{}".format(patient_id_current),
                "patient_{}.transformed".format(patient_id_current),
            ),
            df_documents_current,
        )

        progress_patient_count.description = "{}/{}".format(
            patient_count + 1, progress_max
        )
        progress_patient_count.value = patient_count + 1


if DEVELOPMENT_EXPORT_PER_PATIENT_DOCUMENTS:
    export_per_patient_documents()

# %% [markdown]
# ### Combined Documents

# %%
if DEVELOPMENT_EXPORT_COMBINED_DOCUMENTS:
    export_dataframe(
        pathlib.Path(
            "data",
            "documents.raw",
        ),
        df_documents_raw,
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "documents.transformed",
        ),
        df_documents,
    )


# %% [markdown]
# ### Analysis: Activities

# %%
def export_analysis_activities():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("activities"),
        documentation_as_markdown("Activities"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "activities.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[df_documents_raw["_type"] == "activity"],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "activities.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "activity"],
            drop_empty_columns=True,
        ),
    )

    # Formatted values.
    drop_columns = [
        "_set_id",
        "editedDateTime",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
        "activityId": "_activityId",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "_activityId",
        "_rev",
        "_created",
        "_deleted",
        "valueId",
        "valueLifeArea",
        "valueName",
        "enjoyment",
        "importance",
        "name",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_created",
    ]

    export_dataframe(
        pathlib.Path("activities"),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "activity"],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Activity Logs

# %%
def export_analysis_activity_logs():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("activityLogs"),
        documentation_as_markdown("Activity Logs"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "activityLogs.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[df_documents_raw["_type"] == "activityLog"],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "activityLogs.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "activityLog"],
            drop_empty_columns=True,
        ),
    )

    # Formatted values.
    drop_columns = [
        "_set_id",
        "recordedDateTime",
        "dataSnapshot",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
        "activityLogId": "_activityLogId",
        "success": "completed",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "_activityLogId",
        "_rev",
        "_created",
        "scheduledActivityId",
        "valueId",
        "valueLifeArea",
        "valueName",
        "activityId",
        "activityEnjoyment",
        "activityImportance",
        "activityName",
        "dueDate",
        "completed",
        "accomplishment",
        "pleasure",
        "alternative",
        "comment",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_created",
    ]

    export_dataframe(
        pathlib.Path("activityLogs"),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "activityLog"],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Activity Schedules

# %%
def export_analysis_activity_schedules():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("activitySchedules"),
        documentation_as_markdown("Activity Schedules"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "activitySchedules.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[df_documents_raw["_type"] == "activitySchedule"],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "activitySchedules.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "activitySchedule"],
            drop_empty_columns=True,
        ),
    )

    # Formatted values.
    drop_columns = [
        "_set_id",
        "editedDateTime",
        "hasReminder",  # Junk reminder field that was never implemented.
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
        "activityScheduleId": "_activityScheduleId",
        "date": "scheduleDate",
        "timeOfDay": "scheduleTimeOfDay",
        "hasRepetition": "scheduleRepeat",
        "repeatDayFlags": "scheduleRepeatDays",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "_activityScheduleId",
        "_rev",
        "_created",
        "_deleted",
        "valueId",
        "valueLifeArea",
        "valueName",
        "activityId",
        "activityEnjoyment",
        "activityImportance",
        "activityName",
        "scheduleDate",
        "scheduleTimeOfDay",
        "scheduleRepeat",
        "scheduleRepeatDays",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_created",
    ]

    export_dataframe(
        pathlib.Path("activitySchedules"),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "activitySchedule"],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Assessments

# %%
def export_analysis_assessments():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("assessments"),
        documentation_as_markdown("Assessments"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "assessments.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                df_documents_raw["_type"] == "assessment"
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "assessments.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "assessment"
            ],
            drop_empty_columns=True,
        ),
    )

    # Formatted assessment documents.
    drop_columns = [
        "_set_id",
        "assignedDateTime",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "assessmentId",
        "_rev",
        "_created",
        "assigned",
        "dayOfWeek",
        "frequency",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "assessmentId",
        "_rev",
    ]

    export_dataframe(
        pathlib.Path("assessments"),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "assessment"
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Assessment Logs

# %%
def export_analysis_assessment_logs():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("assessmentLogs"),
        documentation_as_markdown("Assessment Logs"),
    )

    # Preliminary GAD-7 documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "assessmentLogsGad7.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                (df_documents_raw["_type"] == "assessmentLog")
                & (df_documents_raw["assessmentId"] == "gad-7")
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "assessmentLogsGad7.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                (df_documents["_type"] == "assessmentLog")
                & (df_documents["assessmentId"] == "gad-7")
            ],
            drop_empty_columns=True,
        ),
    )

    # Preliminary PHQ-9 documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "assessmentLogsPhq9.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                (df_documents_raw["_type"] == "assessmentLog")
                & (df_documents_raw["assessmentId"] == "phq-9")
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "assessmentLogsPhq9.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                (df_documents["_type"] == "assessmentLog")
                & (df_documents["assessmentId"] == "phq-9")
            ],
            drop_empty_columns=True,
        ),
    )

    # Formatted GAD-7 and PHQ-9 documents.
    drop_columns = [
        "_type",
        "_set_id",
        "patientSubmitted",
        "pointValues",
        "recordedDateTime",
        "scheduledAssessmentId",
        "totalScore",
    ]
    rename_columns = {
        "_id": "_docId",
        "assessmentLogId": "_assessmentLogId",
        "assessmentLogRecordedDate": "recordedDate",
        "assessmentLogScheduledAssessmentId": "todo_scheduledAssessmentId",
        "submittedByProviderId": "todo_submittedByProviderId",
        "assessmentLogSubmittedBy": "submittedBy",
    }
    sort_columns = [
        "recordId",
        "_patientId",
        "_docId",
        "_assessmentLogId",
        "_rev",
        "_created",
        "assessmentId",
        "recordedDate",
        "submittedBy",
        "todo_scheduledAssessmentId",
        "todo_submittedByProviderId",
        "gad7Anxious",
        "gad7ConstantWorrying",
        "gad7WorryingTooMuch",
        "gad7TroubleRelaxing",
        "gad7Restless",
        "gad7Irritable",
        "gad7Afraid",
        "gad7Score",
        "phq9Interest",
        "phq9Mood",
        "phq9Sleep",
        "phq9Energy",
        "phq9Appetite",
        "phq9Guilt",
        "phq9Concentrating",
        "phq9Motor",
        "phq9Suicide",
        "phq9Score",
        "comment",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_assessmentLogId",
        "_rev",
    ]

    export_dataframe(
        pathlib.Path("assessmentLogsGad7"),
        dataframe_format_export(
            df_documents.loc[
                (df_documents["_type"] == "assessmentLog")
                & (df_documents["assessmentId"] == "gad-7")
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )

    export_dataframe(
        pathlib.Path("assessmentLogsPhq9"),
        dataframe_format_export(
            df_documents.loc[
                (df_documents["_type"] == "assessmentLog")
                & (df_documents["assessmentId"] == "phq-9")
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Case Reviews

# %%
def export_analysis_case_reviews():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("caseReviews"),
        documentation_as_markdown("Case Reviews"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "caseReviews.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                df_documents_raw["_type"] == "caseReview"
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "caseReviews.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "caseReview"
            ],
            drop_empty_columns=True,
        ),
    )

    # Formatted caseReview documents.
    drop_columns = [
        "_set_id",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
        "date": "caseReviewDate",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "caseReviewId",
        "_rev",
        "_created",
        "caseReviewDate",
        "consultingPsychiatrist",
        "behavioralStrategyChange",
        "medicationChange",
        "otherRecommendations",
        "referralsChange",
        "reviewNote",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "caseReviewDate",
        "caseReviewId",
        "_rev",
    ]

    export_dataframe(
        pathlib.Path("caseReviews"),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "caseReview"
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Clinical History

# %%
def export_analysis_clinical_history():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("clinicalHistory"),
        documentation_as_markdown("Clinical History"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "clinicalHistory.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                df_documents_raw["_type"] == "clinicalHistory"
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "clinicalHistory.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "clinicalHistory"
            ],
            drop_empty_columns=True,
        ),
    )

    # Formatted clinical history documents.
    drop_columns = [
        "_set_id",
        "currentTreatmentRegimen",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "_rev",
        "_created",
        "primaryCancerDiagnosis",
        "dateOfCancerDiagnosis",
        "currentTreatmentRegimenSurgery",
        "currentTreatmentRegimenChemotherapy",
        "currentTreatmentRegimenRadiation",
        "currentTreatmentRegimenStemCellTransplant",
        "currentTreatmentRegimenImmunotherapy",
        "currentTreatmentRegimenCART",
        "currentTreatmentRegimenEndocrine",
        "currentTreatmentRegimenSurveillance",
        "currentTreatmentRegimenOtherFlag",
        "currentTreatmentRegimenOther",
        "currentTreatmentRegimenNotes",
        "psychDiagnosis",
        "pastPsychHistory",
        "pastSubstanceUse",
        "psychSocialBackground",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_rev",
    ]

    export_dataframe(
        pathlib.Path("clinicalHistory"),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "clinicalHistory"
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Mood Logs

# %%
def export_analysis_mood_logs():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("moodLogs"),
        documentation_as_markdown("Mood Logs"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "moodLogs.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[df_documents_raw["_type"] == "moodLog"],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "moodLogs.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "moodLog"],
            drop_empty_columns=True,
        ),
    )

    # Formatted mood logs.
    drop_columns = [
        "_type",
        "_set_id",
        "recordedDateTime",
    ]
    rename_columns = {
        "_id": "_docId",
        "moodLogId": "_moodLogId",
    }
    sort_columns = [
        "recordId",
        "_patientId",
        "_docId",
        "_moodLogId",
        "_rev",
        "_created",
        "mood",
        "comment",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_created",
    ]

    export_dataframe(
        pathlib.Path("moodLogs"),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "moodLog"],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Patient Profile

# %%
def export_analysis_patient_profile():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("patientProfiles"),
        documentation_as_markdown("Patient Profile"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "patientProfiles.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                df_documents_raw["_type"] == "profile"
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "patientProfiles.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "profile"
            ],
            drop_empty_columns=True,
        ),
    )

    # Formatted patient profile documents.
    drop_columns = [
        "_set_id",
        "primaryCareManager",
        "race",
        "discussionFlag",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "_rev",
        "_created",
        "name",
        "MRN",
        "clinicCode",
        "birthdate",
        "sex",
        "gender",
        "pronoun",
        "raceAmericanIndianOrAlaskaNative",
        "raceAsianOrAsianAmerican",
        "raceBlackOrAfricanAmerican",
        "raceNativeHawaiianOrOtherPacificIslander",
        "raceWhite",
        "raceUnknown",
        "ethnicity",
        "primaryOncologyProvider",
        "primaryCareManagerName",
        "discussionFlagFlagAsSafetyRisk",
        "discussionFlagFlagForDiscussion",
        "followupSchedule",
        "depressionTreatmentStatus",
        "site",
        "enrollmentDate",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_rev",
    ]

    export_dataframe(
        pathlib.Path("patientProfiles"),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "profile"
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Review Mark

# %%
def export_analysis_review_mark():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("reviewMarks"),
        documentation_as_markdown("Review Mark"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "reviewMarks.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                df_documents_raw["_type"] == "reviewMark"
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "reviewMarks.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "reviewMark"
            ],
            drop_empty_columns=True,
        ),
    )

    # Formatted review mark documents.
    drop_columns = [
        "_set_id",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "reviewMarkId",
        "_rev",
        "_created",
        "editedDateTime",
        "effectiveDateTime",
        "providerId",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_created",
    ]

    export_dataframe(
        pathlib.Path("reviewMarks"),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "reviewMark"
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Safety Plan

# %%
def export_analysis_safety_plan():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("safetyPlans"),
        documentation_as_markdown("Safety Plan"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "safetyPlans.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                df_documents_raw["_type"] == "safetyPlan"
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "safetyPlans.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "safetyPlan"
            ],
            drop_empty_columns=True,
        ),
    )

    # Formatted safety plan documents.
    drop_columns = [
        "_set_id",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "_rev",
        "_created",
        "assigned",
        "assignedDateTime",
        "lastUpdatedDateTime",
        "reasonsForLiving",
        "warningSigns",
        "copingStrategies",
        "socialDistractions",
        "settingDistractions",
        "supporters",
        "professionals",
        "urgentServices",
        "safeEnvironment",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_rev",
    ]

    export_dataframe(
        pathlib.Path("safetyPlans"),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "safetyPlan"
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Session

# %%
def export_analysis_session():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("sessions"),
        documentation_as_markdown("Session"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "sessions.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                df_documents_raw["_type"] == "session"
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "sessions.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "session"
            ],
            drop_empty_columns=True,
        ),
    )

    # Formatted session documents.
    drop_columns = [
        "_set_id",
        "behavioralStrategyChecklist",
        "behavioralActivationChecklist",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "sessionId",
        "_rev",
        "_created",
        "date",
        "sessionType",
        "billableMinutes",
        "medicationChange",
        "currentMedications",
        "behavioralStrategyChecklistBehavioralActivation",
        "behavioralStrategyChecklistMotivationalInterviewing",
        "behavioralStrategyChecklistProblemSolvingTherapy",
        "behavioralStrategyChecklistCognitiveTherapy",
        "behavioralStrategyChecklistMindfulnessStrategies",
        "behavioralStrategyChecklistSupportiveTherapy",
        "behavioralStrategyChecklistOther",
        "behavioralStrategyOther",
        "behavioralActivationChecklistReviewOfTheBAModel",
        "behavioralActivationChecklistValuesAndGoalsAssessment",
        "behavioralActivationChecklistActivityScheduling",
        "behavioralActivationChecklistMoodAndActivityMonitoring",
        "behavioralActivationChecklistRelaxation",
        "behavioralActivationChecklistPositiveReinforcement",
        "behavioralActivationChecklistManagingAvoidanceBehaviors",
        "behavioralActivationChecklistProblemSolving",
        "referrals",
        "otherRecommendations",
        "sessionNote",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_created",
    ]

    export_dataframe(
        pathlib.Path("sessions"),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "session"
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Values

# %%
def export_analysis_values():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("values"),
        documentation_as_markdown("Values"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "values.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[df_documents_raw["_type"] == "value"],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "values.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "value"],
            drop_empty_columns=True,
        ),
    )

    # Formatted values.
    drop_columns = [
        "_type",
        "_set_id",
        "editedDateTime",
    ]
    rename_columns = {
        "_id": "_docId",
        "valueId": "_valueId",
        "lifeAreaId": "lifeArea",
    }
    sort_columns = [
        "recordId",
        "_patientId",
        "_docId",
        "_valueId",
        "_rev",
        "_created",
        "_deleted",
        "lifeArea",
        "name",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_created",
    ]

    export_dataframe(
        pathlib.Path("values"),
        dataframe_format_export(
            df_documents.loc[df_documents["_type"] == "value"],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Analysis: Values Inventory

# %%
def export_analysis_values_inventory():
    # Documentation of this analysis.
    export_markdown(
        pathlib.Path("valuesInventories"),
        documentation_as_markdown("Values Inventory"),
    )

    # Preliminary documents.
    export_dataframe(
        pathlib.Path(
            "data",
            "valuesInventories.raw",
        ),
        dataframe_format_export(
            df_documents_raw.loc[
                df_documents_raw["_type"] == "valuesInventory"
            ],
            drop_empty_columns=True,
        ),
    )

    export_dataframe(
        pathlib.Path(
            "data",
            "valuesInventories.transformed",
        ),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "valuesInventory"
            ],
            drop_empty_columns=True,
        ),
    )

    # Formatted values inventory documents.
    drop_columns = [
        "_set_id",
    ]
    rename_columns = {
        "_type": "_docType",
        "_id": "_docId",
    }
    sort_columns = [
        "_docType",
        "recordId",
        "_patientId",
        "_docId",
        "_rev",
        "_created",
        "assigned",
        "assignedDateTime",
    ]
    sort_rows_by_columns = [
        "recordId",
        "_patientId",
        "_rev",
    ]

    export_dataframe(
        pathlib.Path("valuesInventories"),
        dataframe_format_export(
            df_documents.loc[
                df_documents["_type"] == "valuesInventory"
            ],
            drop_empty_columns=True,
            drop_columns=drop_columns,
            rename_columns=rename_columns,
            sort_columns=sort_columns,
            sort_rows_by_columns=sort_rows_by_columns,
        ),
    )


# %% [markdown]
# ### Execute Exports
#
# Runs all analysis export functions defined above.
#
# Document types not yet exported:
# - scheduledActivity
# - scheduledAssessment

# %%
export_analysis_activities()
export_analysis_activity_logs()
export_analysis_activity_schedules()
export_analysis_assessments()
export_analysis_assessment_logs()
export_analysis_case_reviews()
export_analysis_clinical_history()
export_analysis_mood_logs()
export_analysis_patient_profile()
export_analysis_review_mark()
export_analysis_safety_plan()
export_analysis_session()
export_analysis_values()
export_analysis_values_inventory()

# %% [markdown]
# ### Write Archive

# %%
# The export is stored in a single zip file.
with open(
    pathlib.Path(
        archive_dir_path,
        "export_{}.zip".format(archive_suffix),
    ),
    mode="xb",
) as archive_file:
    with pyzipper.AESZipFile(
        archive_file,
        "w",
        compression=pyzipper.ZIP_LZMA,
        encryption=pyzipper.WZ_AES,
    ) as archive_zipfile:
        # Set the password
        archive_zipfile.setpassword(archive_password.encode("utf-8"))

        for file_current in export_file_list:
            if file_current.type in [
                ExportFileType.BYTES,
                ExportFileType.EXCEL,
            ]:
                archive_zipfile.writestr(
                    file_current.path.as_posix(), file_current.bytes
                )
            elif file_current.type in [
                ExportFileType.CSV,
                ExportFileType.MARKDOWN,
            ]:
                assert file_current.text is not None

                archive_zipfile.writestr(
                    file_current.path.as_posix(), file_current.text.encode("utf-8")
                )
            else:
                raise ValueError("Unknown ExportFileType")
