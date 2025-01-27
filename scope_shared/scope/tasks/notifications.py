from __future__ import annotations

import json
import pprint

import aws_infrastructure.tasks.ssh
import boto3
import contextlib
from dataclasses import asdict, dataclass
import datetime
from enum import Enum
from invoke import task
import operator
from pathlib import Path
import re
import ruamel.yaml
from typing import List, Optional, Union

import scope.config
import scope.database.date_utils
import scope.database.document_utils
import scope.database.initialize
import scope.database.patient
import scope.database.patient.activities
import scope.database.patient.safety_plan
import scope.database.patient.scheduled_activities
import scope.database.patient.scheduled_assessments
import scope.database.patient.values_inventory
import scope.database.patients
import scope.documentdb.client
import scope.documents.document_set
import scope.populate
import scope.schema
import scope.schema_utils
import scope.utils.compute_patient_summary


class ScopeInstanceId(Enum):
    """
    Based on the string we expect in the database configuration.
    """

    DEV = "dev"
    DEMO = "demo"
    FREDHUTCH = "scca"
    MULTICARE = "multicare"


@dataclass(frozen=True)
class EmailContentData:
    patient_email: str
    testing_destination_email: str

    date_today_formatted_subject: str
    date_today_formatted_body: str

    link_app: str

    assigned_safety_plan: bool
    assigned_values_inventory: bool
    due_check_in_anxiety: bool
    due_check_in_depression: bool

    scheduled_activities_due_today: List[_ContentScheduledActivity]
    scheduled_activities_overdue: List[_ContentScheduledActivity]


class EmailProcessStatus(Enum):
    IN_PROGRESS = 0

    STOPPED_MATCHED_DENY_LIST = 1
    STOPPED_COGNITO_ACCOUNT_DISABLED = 2
    STOPPED_FAILED_ALLOW_LIST = 3

    REACHED_END_OF_FUNCTION = 10

    EMAIL_SUCCESS = 12


@dataclass(frozen=True)
class EmailProcessData:
    patient_id: str
    patient_name: str
    patient_email: str
    cognito_id: str

    content_data: Optional[EmailContentData]

    status: EmailProcessStatus

    @property
    def patient_summary(self):
        # Use a summary string for patient output.
        return "{} : {} : {}".format(
            self.patient_id,
            self.patient_name,
            self.patient_email,
        )

    @classmethod
    def from_content_data(
        cls,
        *,
        current: EmailProcessData,
        content_data: EmailContentData,
    ):
        return EmailProcessData(
            patient_id=current.patient_id,
            patient_name=current.patient_name,
            patient_email=current.patient_email,
            cognito_id=current.cognito_id,
            content_data=content_data,
            status=current.status,
        )

    @classmethod
    def from_patient_data(
        cls,
        *,
        patient_id: str,
        patient_name: str,
        patient_email: str,
        cognito_id: str,
    ):
        return EmailProcessData(
            patient_id=patient_id,
            patient_name=patient_name,
            patient_email=patient_email,
            cognito_id=cognito_id,
            content_data=None,
            status=EmailProcessStatus.IN_PROGRESS,
        )

    @classmethod
    def from_status(
        cls,
        *,
        current: EmailProcessData,
        status: EmailProcessStatus,
    ):
        return EmailProcessData(
            patient_id=current.patient_id,
            patient_name=current.patient_name,
            patient_email=current.patient_email,
            cognito_id=current.cognito_id,
            content_data=current.content_data,
            status=status,
        )


@dataclass(frozen=True)
class TemplatesEmailReminder:
    template_email_reminder_body: str
    template_email_reminder_subject: str
    template_email_reminder_testing_body_header: str
    template_email_reminder_testing_subject_prefix: str

    @classmethod
    def from_paths(
        cls,
        *,
        template_email_reminder_body_path: Union[Path, str],
        template_email_reminder_subject_path: Union[Path, str],
        template_email_reminder_testing_body_header_path: Union[Path, str],
        template_email_reminder_testing_subject_prefix_path: Union[Path, str],
    ):
        template_email_reminder_body = None
        with open(template_email_reminder_body_path, "r") as file_template:
            template_email_reminder_body = file_template.read().strip()

        template_email_reminder_subject = None
        with open(template_email_reminder_subject_path, "r") as file_template:
            template_email_reminder_subject = file_template.read().strip()

        template_email_reminder_testing_body_header = None
        with open(
            template_email_reminder_testing_body_header_path, "r"
        ) as file_template:
            template_email_reminder_testing_body_header = file_template.read().strip()

        template_email_reminder_testing_subject_prefix = None
        with open(
            template_email_reminder_testing_subject_prefix_path, "r"
        ) as file_template:
            template_email_reminder_testing_subject_prefix = (
                file_template.read().strip()
            )

        return TemplatesEmailReminder(
            template_email_reminder_body=template_email_reminder_body,
            template_email_reminder_subject=template_email_reminder_subject,
            template_email_reminder_testing_body_header=template_email_reminder_testing_body_header,
            template_email_reminder_testing_subject_prefix=template_email_reminder_testing_subject_prefix,
        )


def _content_link_app(
    *,
    scope_instance_id: ScopeInstanceId,
) -> str:
    if scope_instance_id == ScopeInstanceId.DEV:
        return "https://app.dev.uwscope.org/"
    elif scope_instance_id == ScopeInstanceId.DEMO:
        return "https://app.demo.uwscope.org/"
    elif scope_instance_id == ScopeInstanceId.FREDHUTCH:
        return "https://app.fredhutch.uwscope.org/"
    elif scope_instance_id == ScopeInstanceId.MULTICARE:
        return "https://app.multicare.uwscope.org/"
    else:
        raise ValueError("Unknown SCOPE Instance: {}".format(scope_instance_id))


@dataclass(frozen=True)
class _ContentPatientSummaryResult:
    assigned_values_inventory: bool
    assigned_safety_plan: bool
    due_check_in_anxiety: bool
    due_check_in_depression: bool


def _content_patient_summary(
    *,
    patient_document_set: scope.documents.document_set.DocumentSet,
    date_due: datetime.date,
) -> _ContentPatientSummaryResult:
    # Work with only the current documents
    current_document_set = patient_document_set.remove_revisions()

    activity_documents = current_document_set.filter_match(
        match_type=scope.database.patient.activities.DOCUMENT_TYPE,
        match_deleted=False,
    ).documents

    safety_plan_document = current_document_set.filter_match(
        match_type=scope.database.patient.safety_plan.DOCUMENT_TYPE,
        match_deleted=False,
    ).unique()

    scheduled_assessment_documents = current_document_set.filter_match(
        match_type=scope.database.patient.scheduled_assessments.DOCUMENT_TYPE,
        match_deleted=False,
    ).documents

    values_inventory_document = current_document_set.filter_match(
        match_type=scope.database.patient.values_inventory.DOCUMENT_TYPE,
        match_deleted=False,
    ).unique()

    patient_summary = scope.utils.compute_patient_summary.compute_patient_summary(
        activity_documents=activity_documents,
        safety_plan_document=safety_plan_document,
        scheduled_assessment_documents=scheduled_assessment_documents,
        values_inventory_document=values_inventory_document,
        date_due=date_due,
    )

    dueScheduledAssessmentsGad7 = [
        scheduled_assessment_current
        for scheduled_assessment_current in patient_summary[
            "assignedScheduledAssessments"
        ]
        if scheduled_assessment_current["assessmentId"] == "gad-7"
    ]
    dueScheduledAssessmentsGad7 = scope.database.document_utils.normalize_documents(
        documents=dueScheduledAssessmentsGad7
    )

    dueScheduledAssessmentsPhq9 = [
        scheduled_assessment_current
        for scheduled_assessment_current in patient_summary[
            "assignedScheduledAssessments"
        ]
        if scheduled_assessment_current["assessmentId"] == "phq-9"
    ]
    dueScheduledAssessmentsPhq9 = scope.database.document_utils.normalize_documents(
        documents=dueScheduledAssessmentsPhq9
    )

    return _ContentPatientSummaryResult(
        assigned_safety_plan=patient_summary["assignedSafetyPlan"],
        assigned_values_inventory=patient_summary["assignedValuesInventory"],
        due_check_in_anxiety=len(dueScheduledAssessmentsGad7) > 0,
        due_check_in_depression=len(dueScheduledAssessmentsPhq9) > 0,
    )


@dataclass(frozen=True)
class _ContentScheduledActivity:
    activity_name: str
    due_date: datetime.date
    due_time_of_day: int


@dataclass(frozen=True)
class _ContentScheduledActivitiesResult:
    due_today: List[_ContentScheduledActivity]
    overdue: List[_ContentScheduledActivity]


def _content_scheduled_activities(
    *,
    patient_document_set: scope.documents.document_set.DocumentSet,
    date_due: datetime.date,
) -> _ContentScheduledActivitiesResult:
    # Work with only the current documents.
    current_document_set = patient_document_set.remove_revisions()

    # Obtain scheduled activities which we have not yet completed.
    scheduled_activities = current_document_set.filter_match(
        match_type=scope.database.patient.scheduled_activities.DOCUMENT_TYPE,
        match_values={"completed": False},
        match_deleted=False,
    ).documents

    def _map_content_scheduled_activity(
        scheduled_activity_document: dict,
    ) -> _ContentScheduledActivity:
        return _ContentScheduledActivity(
            activity_name=scheduled_activity_document["dataSnapshot"]["activity"][
                "name"
            ],
            due_date=scope.database.date_utils.parse_date(
                scheduled_activity_document["dueDate"]
            ),
            due_time_of_day=scheduled_activity_document["dueTimeOfDay"],
        )

    def _content_scheduled_activity_key(
        content_scheduled_activity: _ContentScheduledActivity,
    ):
        return (
            content_scheduled_activity.due_date,
            content_scheduled_activity.due_time_of_day,
            content_scheduled_activity.activity_name,
        )

    # Filter and map scheduled activities that are due today.
    scheduled_activities_due_today = []
    for scheduled_activity_current in scheduled_activities:
        scheduled_activity_current_date_due = scope.database.date_utils.parse_date(
            scheduled_activity_current["dueDate"]
        )

        if scheduled_activity_current_date_due == date_due:
            scheduled_activities_due_today.append(
                _map_content_scheduled_activity(scheduled_activity_current)
            )

    # Sort the activities that are due today.
    scheduled_activities_due_today = sorted(
        scheduled_activities_due_today,
        key=operator.attrgetter("due_time_of_day", "activity_name"),
    )

    # Filter and map scheduled activities that are overdue.
    scheduled_activities_overdue = []
    for scheduled_activity_current in scheduled_activities:
        scheduled_activity_current_date_due = scope.database.date_utils.parse_date(
            scheduled_activity_current["dueDate"]
        )

        if scheduled_activity_current_date_due < date_due:
            if scheduled_activity_current_date_due >= date_due - datetime.timedelta(
                days=7
            ):
                scheduled_activities_overdue.append(
                    _map_content_scheduled_activity(scheduled_activity_current)
                )

    # Sort the activities that are overdue.
    scheduled_activities_overdue = sorted(
        scheduled_activities_overdue,
        key=operator.attrgetter("due_time_of_day", "activity_name"),
    )
    scheduled_activities_overdue = sorted(
        scheduled_activities_overdue, key=operator.attrgetter("due_date"), reverse=True
    )

    return _ContentScheduledActivitiesResult(
        due_today=scheduled_activities_due_today,
        overdue=scheduled_activities_overdue,
    )


def _filter_allowlist(
    *,
    allowlist_email_reminder: List[str],
    destination_email: str,
) -> bool:
    # A destination_email must match an element of this list to be allowed.
    for allow_current in allowlist_email_reminder:
        if re.fullmatch(allow_current, destination_email):
            return True

    return False


def _filter_cognito_account_disabled(*, cognito_id: str) -> bool:
    """
    Filter based on whether a Cognito account is disabled.
    :param cognito_id:
    :return: true if enabled, false if disabled.
    """

    # boto will obtain AWS context from environment variables, but will have obtained those at an unknown time.
    # Creating a boto session ensures it uses the current value of AWS configuration environment variables.
    boto_session = boto3.Session()
    boto_userpool = boto_session.client("cognito-idp")

    # def _reset_cognito_password(
    #     *,
    #     database: pymongo.database.Database,
    #     cognito_config: scope.config.CognitoClientConfig,
    #     account_config: dict,  # Subset of a patient config or a provider config
    # ) -> None:
    #     # boto will obtain AWS context from environment variables, but will have obtained those at an unknown time.
    #     # Creating a boto session ensures it uses the current value of AWS configuration environment variables.
    #     boto_session = boto3.Session()
    #     boto_userpool = boto_session.client("cognito-idp")
    #
    #     reset_account_name = account_config["accountName"]
    #     reset_temporary_password = generate_temporary_password()
    #
    #     boto_userpool.admin_set_user_password(
    #         UserPoolId=cognito_config.poolid,
    #         Username=reset_account_name,
    #         Password=reset_temporary_password,
    #         Permanent=False,
    #     )
    #
    #     # Put the temporary password in the config
    #     account_config["temporaryPassword"] = reset_temporary_password
    return True


def _filter_denylist(
    *,
    denylist_email_reminder: List[str],
    email_process_data: EmailProcessData,
) -> bool:
    """
    Filter based on whether a patient appears in the deny list.
    A patient that matches any element of this list will be denied.
    Matching is by name, patient_id, or email.
    """
    for block_current in denylist_email_reminder:
        if re.fullmatch(block_current, email_process_data.patient_id):
            return False
        if re.fullmatch(block_current, email_process_data.patient_name):
            return False
        if re.fullmatch(block_current, email_process_data.patient_email):
            return False

    return True


@dataclass(frozen=True)
class _FormatEmailResult:
    body: str
    subject: str


def _format_email(
    *,
    email_content_data: EmailContentData,
    templates_email_reminder: TemplatesEmailReminder,
    testing_destination_email: str,
) -> _FormatEmailResult:
    # Start from the production templates.
    template_body = templates_email_reminder.template_email_reminder_body
    template_subject = templates_email_reminder.template_email_reminder_subject

    # Apply transformations for testing.
    if testing_destination_email:
        # Because we are testing, apply the testing body header.
        template_body = template_body.replace(
            "{template_email_reminder_testing_body_header}",
            templates_email_reminder.template_email_reminder_testing_body_header,
        )
        # Because we are testing, apply the subject prefix.
        # Force a space after the template, because all the templates are being stripped.
        template_subject = template_subject.replace(
            "{template_email_reminder_testing_subject_prefix}",
            templates_email_reminder.template_email_reminder_testing_subject_prefix
            + " ",
        )
    else:
        # Because we are not testing, delete the placeholder for the testing body header.
        template_body = template_body.replace(
            "{template_email_reminder_testing_body_header}",
            "",
        )
        # Because we are not testing, delete the placeholder for the testing subject prefix.
        template_subject = template_subject.replace(
            "{template_email_reminder_testing_subject_prefix}",
            "",
        )

    # Calculate what to display for "Requested by Provider"
    requested_by_provider_count = len(
        [
            request_current
            for request_current in [
                email_content_data.assigned_values_inventory,
                email_content_data.assigned_safety_plan,
                email_content_data.due_check_in_depression,
                email_content_data.due_check_in_anxiety,
            ]
            if request_current
        ]
    )
    requested_by_provider_formatted = ""
    if requested_by_provider_count > 0:
        requested_by_provider_formatted += " " * 14 + "<h3>Requested by Provider</h3>\n"
        requested_by_provider_formatted += (
            " " * 14
            + "<p>Your social worker has {} requests:</p>\n".format(
                requested_by_provider_count
            )
        )
        if email_content_data.assigned_values_inventory:
            requested_by_provider_formatted += (
                "<p>- Complete Values & Activities Inventory</p>\n"
            )
        if email_content_data.assigned_safety_plan:
            requested_by_provider_formatted += "<p>- Complete Safety Plan</p>\n"
        if email_content_data.due_check_in_depression:
            requested_by_provider_formatted += "<p>- Complete Depression Check-In</p>\n"
        if email_content_data.due_check_in_anxiety:
            requested_by_provider_formatted += "<p>- Complete Anxiety Check-In</p>\n"

    # Provide our email content data and our formatted content.
    format_params = dict(vars(email_content_data))
    format_params["requested_by_provider_formatted"] = requested_by_provider_formatted

    formatted_body = template_body.format_map(format_params)
    formatted_subject = template_subject.format_map(format_params)

    return _FormatEmailResult(
        body=formatted_body,
        subject=formatted_subject,
    )


def _patient_calculate_email_content_data(
    *,
    email_process_data: EmailProcessData,
    patient_document_set: scope.documents.document_set.DocumentSet,
    scope_instance_id: ScopeInstanceId,
    testing_destination_email: str,
) -> EmailProcessData:
    date_today = datetime.date.today()

    content_patient_summary = _content_patient_summary(
        patient_document_set=patient_document_set,
        date_due=date_today,
    )
    content_scheduled_activities = _content_scheduled_activities(
        patient_document_set=patient_document_set,
        date_due=date_today,
    )

    return EmailProcessData.from_content_data(
        current=email_process_data,
        content_data=EmailContentData(
            # Email addresses.
            patient_email=email_process_data.patient_email,
            testing_destination_email=testing_destination_email,
            # Date of today formatted for rendering.
            date_today_formatted_subject="{} {} {}".format(
                date_today.strftime(format="%a"),
                date_today.strftime(format="%b"),
                date_today.day,
            ),
            date_today_formatted_body="{}, {} {}".format(
                date_today.strftime(format="%A"),
                date_today.strftime(format="%B"),
                date_today.day,
            ),
            # Link to scope app.
            link_app=_content_link_app(
                scope_instance_id=scope_instance_id,
            ),
            # Content requested by provider.
            assigned_safety_plan=content_patient_summary.assigned_safety_plan,
            assigned_values_inventory=content_patient_summary.assigned_values_inventory,
            due_check_in_anxiety=content_patient_summary.due_check_in_anxiety,
            due_check_in_depression=content_patient_summary.due_check_in_depression,
        ),
    )


def _patient_filter_email_process_data(
    *,
    email_process_data: EmailProcessData,
    denylist_email_reminder: List[str],
) -> EmailProcessData:
    """
    Apply all filtering criteria.
    """

    # Filter if the patient appears in a deny list.
    if not _filter_denylist(
        denylist_email_reminder=denylist_email_reminder,
        email_process_data=email_process_data,
    ):
        return EmailProcessData.from_status(
            current=email_process_data,
            status=EmailProcessStatus.STOPPED_MATCHED_DENY_LIST,
        )

    # Filter if the patient Cognito account has been disabled.
    if not _filter_cognito_account_disabled(
        cognito_id=email_process_data.cognito_id,
    ):
        return EmailProcessData.from_status(
            current=email_process_data,
            status=EmailProcessStatus.STOPPED_COGNITO_ACCOUNT_DISABLED,
        )

    return email_process_data


def _patient_email_reminder(
    *,
    email_process_data: EmailProcessData,
    patient_document_set: scope.documents.document_set.DocumentSet,
    scope_instance_id: ScopeInstanceId,
    allowlist_email_reminder: List[str],
    denylist_email_reminder: List[str],
    templates_email_reminder: TemplatesEmailReminder,
    testing_destination_email: Optional[str],
) -> EmailProcessData:
    # Filter whether this patient receives an email.
    email_process_data = _patient_filter_email_process_data(
        email_process_data=email_process_data,
        denylist_email_reminder=denylist_email_reminder,
    )
    if email_process_data.status != EmailProcessStatus.IN_PROGRESS:
        return email_process_data

    # Calculate values needed for an email.
    email_process_data = _patient_calculate_email_content_data(
        email_process_data=email_process_data,
        patient_document_set=patient_document_set,
        scope_instance_id=scope_instance_id,
        testing_destination_email=testing_destination_email,
    )
    if email_process_data.status != EmailProcessStatus.IN_PROGRESS:
        return email_process_data

    # Differentiate destination email from the patient email.
    # These will be the same in production, but are differentiated in testing.
    # This must be done before testing the allowlist.
    destination_email = email_process_data.patient_email
    if testing_destination_email:
        # Because we are testing, email will instead go to the testing destination.
        destination_email = testing_destination_email

    # Ensure the destination_email appears in an allow list.
    if not _filter_allowlist(
        allowlist_email_reminder=allowlist_email_reminder,
        destination_email=destination_email,
    ):
        return EmailProcessData.from_status(
            current=email_process_data,
            status=EmailProcessStatus.STOPPED_FAILED_ALLOW_LIST,
        )

    # Format the actual email.
    format_email_result = _format_email(
        email_content_data=email_process_data.content_data,
        templates_email_reminder=templates_email_reminder,
        testing_destination_email=testing_destination_email,
    )

    # boto will obtain AWS context from environment variables, but will have obtained those at an unknown time.
    # Creating a boto session ensures it uses the current value of AWS configuration environment variables.
    boto_session = boto3.Session()
    boto_ses = boto_session.client("ses")

    # Send the formatted email.
    response = boto_ses.send_email(
        Source="SCOPE Reminders <do-not-reply@uwscope.org>",
        Destination={
            "ToAddresses": [destination_email],
            # "CcAddresses": ["<email@email.org>"],
        },
        ReplyToAddresses=["do-not-reply@uwscope.org"],
        Message={
            "Subject": {
                "Data": format_email_result.subject,
                "Charset": "UTF-8",
            },
            "Body": {
                "Html": {
                    "Data": format_email_result.body,
                    "Charset": "UTF-8",
                }
            },
        },
    )

    return EmailProcessData.from_status(
        current=email_process_data,
        status=EmailProcessStatus.EMAIL_SUCCESS,
    )


def task_email(
    *,
    instance_ssh_config_path: Union[Path, str],
    documentdb_config_path: Union[Path, str],
    database_config_path: Union[Path, str],
    allowlist_email_reminder_path: Union[Path, str],
    denylist_email_reminder_path: Union[Path, str],
    templates_email_reminder: TemplatesEmailReminder,
):
    instance_ssh_config = aws_infrastructure.tasks.ssh.SSHConfig.load(
        instance_ssh_config_path
    )
    documentdb_config = scope.config.DocumentDBClientConfig.load(documentdb_config_path)
    database_config = scope.config.DatabaseClientConfig.load(database_config_path)
    allowlist_email_reminder = None
    with open(allowlist_email_reminder_path, encoding="UTF-8") as config_file:
        yaml = ruamel.yaml.YAML(typ="safe", pure=True)
        allowlist_email_reminder = yaml.load(config_file)
        if allowlist_email_reminder == None:
            allowlist_email_reminder = []
    denylist_email_reminder = None
    with open(denylist_email_reminder_path, encoding="UTF-8") as config_file:
        yaml = ruamel.yaml.YAML(typ="safe", pure=True)
        denylist_email_reminder = yaml.load(config_file)
        if denylist_email_reminder == None:
            denylist_email_reminder = []

    @task(optional=["production", "testing_destination_email"])
    def email_notifications(context, production=False, testing_destination_email=None):
        """
        Email patient notifications in {} database.
        """

        # Parameters must either:
        # - Explicitly indicate this is a production execution.
        # - Provide a testing_destination_email address to which email will be sent.
        if production:
            if testing_destination_email:
                raise ValueError("-production does not allow -testing-email")
        else:
            if not testing_destination_email:
                raise ValueError("Provide either -production or -testing-email")

        # Used for determining a URL base for any links included in emails.
        scope_instance_id = ScopeInstanceId(database_config.name)

        # Store state about results.
        email_process_data_results: List[EmailProcessData] = []

        # Obtain a database client.
        with contextlib.ExitStack() as context_manager:
            database = scope.documentdb.client.documentdb_client_database(
                context_manager=context_manager,
                instance_ssh_config=instance_ssh_config,
                host=documentdb_config.endpoint,
                port=documentdb_config.port,
                direct_connection=True,
                tls_insecure=True,
                database_name=database_config.name,
                user=database_config.user,
                password=database_config.password,
            )

            # Iterate over every patient.
            patients = scope.database.patients.get_patient_identities(database=database)
            for patient_identity_current in patients:
                # Obtain needed documents for this patient.
                patient_collection = database.get_collection(
                    patient_identity_current["collection"]
                )
                patient_profile = scope.database.patient.get_patient_profile(
                    collection=patient_collection
                )

                result_current = _patient_email_reminder(
                    email_process_data=EmailProcessData.from_patient_data(
                        patient_id=patient_identity_current["patientId"],
                        patient_name=patient_profile["name"],
                        patient_email=patient_identity_current["cognitoAccount"][
                            "email"
                        ],
                        cognito_id=patient_identity_current["cognitoAccount"][
                            "cognitoId"
                        ],
                    ),
                    patient_document_set=scope.documents.document_set.DocumentSet(
                        documents=patient_collection.find()
                    ),
                    scope_instance_id=scope_instance_id,
                    allowlist_email_reminder=allowlist_email_reminder,
                    denylist_email_reminder=denylist_email_reminder,
                    templates_email_reminder=templates_email_reminder,
                    testing_destination_email=testing_destination_email,
                )

                # Store the result
                email_process_data_results.append(result_current)

        for status_current in EmailProcessStatus:
            matching_results = [
                email_process_data_current
                for email_process_data_current in email_process_data_results
                if email_process_data_current.status == status_current
            ]

            if len(matching_results) > 0:
                print(status_current.name)
                for email_process_data_current in matching_results:
                    print("  {}".format(email_process_data_current.patient_summary))
                print()

    email_notifications.__doc__ = email_notifications.__doc__.format(
        database_config.name
    )

    return email_notifications
