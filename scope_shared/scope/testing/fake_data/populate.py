import copy
import faker
import pymongo.database

import scope.database.patient.activities
import scope.database.patient.activity_logs
import scope.database.patient.assessments
import scope.database.patient.assessment_logs
import scope.database.patient.case_reviews
import scope.database.patient.clinical_history
import scope.database.patient.mood_logs
import scope.database.patient.patient_profile
import scope.database.patient.safety_plan
import scope.database.patient.sessions
import scope.database.patient.scheduled_activities
import scope.database.patient.scheduled_assessments
import scope.database.patient.values_inventory
import scope.database.patients
import scope.database.providers
import scope.testing.fake_data.enums
import scope.testing.fake_data.fixtures_fake_activity
import scope.testing.fake_data.fixtures_fake_activity_logs
import scope.testing.fake_data.fixtures_fake_assessments
import scope.testing.fake_data.fixtures_fake_assessment_contents
import scope.testing.fake_data.fixtures_fake_assessment_logs
import scope.testing.fake_data.fixtures_fake_activities
import scope.testing.fake_data.fixtures_fake_case_review
import scope.testing.fake_data.fixtures_fake_case_reviews
import scope.testing.fake_data.fixtures_fake_clinical_history
import scope.testing.fake_data.fixtures_fake_contact
import scope.testing.fake_data.fixtures_fake_life_area_contents
import scope.testing.fake_data.fixtures_fake_mood_log
import scope.testing.fake_data.fixtures_fake_mood_logs
import scope.testing.fake_data.fixtures_fake_patient_profile
import scope.testing.fake_data.fixtures_fake_provider_identity
import scope.testing.fake_data.fixtures_fake_referral_status
import scope.testing.fake_data.fixtures_fake_safety_plan
import scope.testing.fake_data.fixtures_fake_session
import scope.testing.fake_data.fixtures_fake_sessions
import scope.testing.fake_data.fixtures_fake_scheduled_activities
import scope.testing.fake_data.fixtures_fake_scheduled_assessments
import scope.testing.fake_data.fixtures_fake_values_inventory


def populate_database(
    *,
    database: pymongo.database.Database,
):
    # Faker instance
    faker_factory = faker.Faker(locale="la")

    #
    # Patient profile factory
    #
    fake_patient_profile_factory = scope.testing.fake_data.fixtures_fake_patient_profile.fake_patient_profile_factory(
        faker_factory=faker_factory,
    )

    #
    # Generate a persistent and populated patient for app development
    #
    # TODO: Remove when patient app includes authentication
    patient_persistent_identity = scope.database.patients.get_patient_identity(
        database=database, patient_id="persistent"
    )
    if patient_persistent_identity is None:
        profile = fake_patient_profile_factory()

        patient_identity_current = scope.database.patients.create_patient(
            database=database,
            patient_id="persistent",
            patient_name=profile["name"],
            patient_mrn=profile["MRN"],
        )
        patient_collection = database.get_collection(
            patient_identity_current["collection"]
        )

        _populate_patient(
            faker_factory=faker_factory,
            database=database,
            patient_collection=patient_collection,
            patient_id=patient_identity_current["patientId"],
            profile=profile,
        )

    #
    # Generate a persistent but empty patient for app development
    #
    # TODO: Remove when patient app includes authentication
    patient_persistentempty_identity = scope.database.patients.get_patient_identity(
        database=database, patient_id="persistentempty"
    )
    if patient_persistentempty_identity is None:
        profile = fake_patient_profile_factory()

        patient_identity_current = scope.database.patients.create_patient(
            database=database,
            patient_id="persistentempty",
            patient_name=profile["name"],
            patient_mrn=profile["MRN"],
        )

    #
    # Generate fully populated patients
    #
    for patient_count in range(6):
        profile = fake_patient_profile_factory()

        patient_identity_current = scope.database.patients.create_patient(
            database=database,
            patient_name=profile["name"],
            patient_mrn=profile["MRN"],
        )
        patient_collection = database.get_collection(
            patient_identity_current["collection"]
        )

        _populate_patient(
            faker_factory=faker_factory,
            database=database,
            patient_collection=patient_collection,
            patient_id=patient_identity_current["patientId"],
            profile=profile,
        )

    #
    # Generate empty patients
    #
    for patient_count in range(3):
        profile = fake_patient_profile_factory()

        patient_identity_current = scope.database.patients.create_patient(
            database=database,
            patient_name=profile["name"],
            patient_mrn=profile["MRN"],
        )

    #
    # Provider identity factory
    #
    fake_provider_identity_factory = scope.testing.fake_data.fixtures_fake_provider_identity.fake_provider_identity_factory(
        faker_factory=faker_factory,
    )

    generate_roles = [
        {
            "role_value": scope.testing.fake_data.enums.ProviderRole.Psychiatrist.value,
            "number_to_generate": 2,
        },
        {
            "role_value": scope.testing.fake_data.enums.ProviderRole.SocialWorker.value,
            "number_to_generate": 8,
        },
        {
            "role_value": scope.testing.fake_data.enums.ProviderRole.StudyStaff.value,
            "number_to_generate": 5,
        },
    ]
    for generate_current in generate_roles:
        for _ in range(generate_current["number_to_generate"]):
            provider_identity_current = fake_provider_identity_factory()

            provider_identity_current = scope.database.providers.create_provider(
                database=database,
                name=provider_identity_current["name"],
                role=generate_current["role_value"],
            )


def _populate_patient(
    *,
    faker_factory: faker.Faker,
    database: pymongo.database.Database,
    patient_id: str,
    patient_collection: pymongo.collection.Collection,
    profile: dict,
):
    ################################################################################
    # Store the full profile used to create this patient.
    # - It will need the current "_rev", because the profile will already exist.
    ################################################################################
    def _profile():
        rev_existing = scope.database.patient.patient_profile.get_patient_profile(
            collection=patient_collection,
        )["_rev"]

        copy_profile = copy.deepcopy(profile)
        copy_profile["_rev"] = rev_existing

        scope.database.patient.patient_profile.put_patient_profile(
            database=database,
            collection=patient_collection,
            patient_id=patient_id,
            patient_profile=copy_profile,
        )

    _profile()

    ################################################################################
    # These documents are simple and do not have any cross dependencies.
    ################################################################################

    def _clinical_history():
        existing_clinical_history = scope.database.patient.clinical_history.get_clinical_history(
            collection=patient_collection
        )

        fake_clinical_history_factory = scope.testing.fake_data.fixtures_fake_clinical_history.fake_clinical_history_factory(
            faker_factory=faker_factory,
        )
        fake_clinical_history = fake_clinical_history_factory()

        clinical_history = copy.deepcopy(existing_clinical_history)
        del clinical_history["_id"]
        clinical_history.update(fake_clinical_history)
        scope.database.patient.clinical_history.put_clinical_history(
            collection=patient_collection,
            clinical_history=clinical_history,
        )

    _clinical_history()

    def _case_reviews():
        fake_case_reviews_factory = scope.testing.fake_data.fixtures_fake_case_reviews.fake_case_reviews_factory(
            fake_case_review_factory=scope.testing.fake_data.fixtures_fake_case_review.fake_case_review_factory(
                faker_factory=faker_factory,
            ),
        )
        case_reviews = fake_case_reviews_factory()
        for case_review_current in case_reviews:
            scope.database.patient.case_reviews.post_case_review(
                collection=patient_collection,
                case_review=case_review_current,
            )

    _case_reviews()

    def _mood_logs():
        fake_mood_logs_factory = scope.testing.fake_data.fixtures_fake_mood_logs.fake_mood_logs_factory(
            fake_mood_log_factory=scope.testing.fake_data.fixtures_fake_mood_log.fake_mood_log_factory(
                faker_factory=faker_factory,
            ),
        )
        mood_logs = fake_mood_logs_factory()
        for mood_log_current in mood_logs:
            scope.database.patient.mood_logs.post_mood_log(
                collection=patient_collection,
                mood_log=mood_log_current,
            )

    _mood_logs()

    ################################################################################
    # Contacts are used only for safety plan.
    ################################################################################
    def _safety_plan():
        fake_contact_factory = (
            scope.testing.fake_data.fixtures_fake_contact.fake_contact_factory(
                faker_factory=faker_factory,
            )
        )
        fake_safety_plan_factory = (
            scope.testing.fake_data.fixtures_fake_safety_plan.fake_safety_plan_factory(
                faker_factory=faker_factory,
                fake_contact_factory=fake_contact_factory,
            )
        )
        scope.database.patient.safety_plan.put_safety_plan(
            collection=patient_collection,
            safety_plan=fake_safety_plan_factory(),
        )

    _safety_plan()

    ################################################################################
    # Referral status are used only for sessions.
    ################################################################################
    def _sessions():
        fake_referral_status_factory = scope.testing.fake_data.fixtures_fake_referral_status.fake_referral_status_factory(
            faker_factory=faker_factory,
        )
        fake_sessions_factory = scope.testing.fake_data.fixtures_fake_sessions.fake_sessions_factory(
            fake_session_factory=scope.testing.fake_data.fixtures_fake_session.fake_session_factory(
                faker_factory=faker_factory,
                fake_referral_status_factory=fake_referral_status_factory,
            ),
        )
        for session in fake_sessions_factory():
            scope.database.patient.sessions.post_session(
                collection=patient_collection,
                session=session,
            )

    _sessions()

    ################################################################################
    # Assessments required to create scheduled assessments.
    ################################################################################
    # def _assessments_and_scheduled_assessments():
    #     fake_assessments_factory = scope.testing.fake_data.fixtures_fake_assessments.fake_assessments_factory(
    #         faker_factory=faker_factory,
    #     )
    #     assessments = fake_assessments_factory()
    #
    #     for assessment_current in assessments:
    #         scope.database.patient.assessments.put_assessment(
    #             collection=patient_collection,
    #             assessment=assessment_current,
    #             set_id=assessment_current[scope.database.patient.assessments.SEMANTIC_SET_ID],
    #         )
    #
    #     fake_scheduled_assessments_factory = scope.testing.fake_data.fixtures_fake_scheduled_assessments.fake_scheduled_assessments_factory(
    #         faker_factory=faker_factory,
    #         fake_assessments=assessments,
    #     )
    #     scheduled_assessments = fake_scheduled_assessments_factory()
    #
    #     for scheduled_assessment_current in scheduled_assessments:
    #         scope.database.patient.scheduled_assessments.post_scheduled_assessment(
    #             collection=patient_collection,
    #             scheduled_assessment=scheduled_assessment_current,
    #         )
    #
    # _assessments_and_scheduled_assessments()

    ################################################################################
    # Life area contents is required to create a values inventory.
    # Values inventory is required to create activities.
    # - If a value inventory does not include include at least one value,
    #   then we cannot generate any associated activities.
    ################################################################################
    def _values_inventory_and_activities():
        # Create life areas
        fake_life_area_contents_factory = (
            scope.testing.fake_data.fixtures_fake_life_area_contents.fake_life_area_contents_factory()
        )
        life_area_contents = fake_life_area_contents_factory()

        # Create and store values inventory
        fake_values_inventory_factory = scope.testing.fake_data.fixtures_fake_values_inventory.fake_values_inventory_factory(
            faker_factory=faker_factory,
            life_areas=life_area_contents,
        )
        values_inventory = fake_values_inventory_factory()
        scope.database.patient.values_inventory.put_values_inventory(
            collection=patient_collection,
            values_inventory=values_inventory,
        )

        # Create and store activities
        if len(values_inventory.get("values", [])) > 1:
            fake_activities_factory = scope.testing.fake_data.fixtures_fake_activities.fake_activities_factory(
                fake_activity_factory=scope.testing.fake_data.fixtures_fake_activity.fake_activity_factory(
                    faker_factory=faker_factory,
                    values_inventory=values_inventory,
                )
            )
            activities = fake_activities_factory()
            for activity_current in activities:
                scope.database.patient.activities.post_activity(
                    collection=patient_collection,
                    activity=activity_current,
                )

    _values_inventory_and_activities()



# =======
#     fake_assessment_contents_factory = (
#         scope.testing.fake_data.fixtures_fake_assessment_contents.fake_assessment_contents_factory()
#     )
#
#     # Obtain fixed documents
#     fake_life_areas = fake_life_areas_factory()
#     fake_assessment_contents = fake_assessment_contents_factory()
# >>>>>>> 51479a0 (Added scheduled assessment and assessment log API)
#
#
# =======
#     fake_assessments_factory = (
#         scope.testing.fake_data.fixtures_fake_assessments.fake_assessments_factory(
#             faker_factory=faker_factory,
#             fake_assessment_contents=fake_assessment_contents,
# >>>>>>> 51479a0 (Added scheduled assessment and assessment log API)
#
#
# =======
#     fake_scheduled_assessments_factory = scope.testing.fake_data.fixtures_fake_scheduled_assessments.fake_scheduled_assessments_factory(
#         faker_factory=faker_factory,
#         fake_assessments=fake_assessments,
#     )
#     fake_scheduled_assessments = fake_scheduled_assessments_factory()
#
#     fake_assessment_logs_factory = scope.testing.fake_data.fixtures_fake_assessment_logs.fake_assessment_logs_factory(
#         faker_factory=faker_factory,
#         fake_scheduled_assessments=fake_scheduled_assessments,
#         fake_assessment_contents=fake_assessment_contents,
#     )
#     fake_assessment_logs = fake_assessment_logs_factory()
# >>>>>>> 51479a0 (Added scheduled assessment and assessment log API)
#
#
# =======
#     for scheduled_assessment in fake_scheduled_assessments:
#         scope.database.patient.scheduled_assessments.put_scheduled_assessment(
#             collection=patient_collection,
#             scheduled_assessment=scheduled_assessment,
#             set_id=scheduled_assessment[
#                 scope.database.patient.scheduled_assessments.SEMANTIC_SET_ID
#             ],
#         )
#
#     for assessment_log in fake_assessment_logs:
#         scope.database.patient.assessment_logs.post_assessment_log(
#             collection=patient_collection,
#             assessment_log=assessment_log,
# >>>>>>> 51479a0 (Added scheduled assessment and assessment log API)


# =======
#
#
#     # activities, scheduledActivities
#     fake_activities_factory = scope.testing.fake_data.fixtures_fake_activities.fake_activities_factory(
#         fake_activity_factory=scope.testing.fake_data.fixtures_fake_activity.fake_activity_factory(
# >>>>>>> fe17f3e (Updated all activity/assessment APIs)
#
#
#
#
# =======
#     )
#     fake_activities = fake_activities_factory()
#
#     fake_scheduled_activities_factory = scope.testing.fake_data.fixtures_fake_scheduled_activities.fake_scheduled_activities_factory(
#         faker_factory=faker_factory,
#         fake_activities=fake_activities,
#     )
#     fake_scheduled_activities = fake_scheduled_activities_factory()
#
#     fake_activity_logs_factory = (
#         scope.testing.fake_data.fixtures_fake_activity_logs.fake_activity_logs_factory(
#             faker_factory=faker_factory,
#             fake_scheduled_activities=fake_scheduled_activities,
#         )
#     )
#     fake_activity_logs = fake_activity_logs_factory()
#
#     if fake_values_inventory.get("values") not in [[], None]:
#         for activity in fake_activities:
#             # TODO: use `put` because semantic set id is present in the document
#             scope.database.patient.activities.put_activity(
#                 collection=patient_collection,
#                 activity=activity,
#                 set_id=activity[scope.database.patient.activities.SEMANTIC_SET_ID],
#             )
#         for scheduled_activity in fake_scheduled_activities:
#             # TODO: use `put` because semantic set id is present in the document
#             scope.database.patient.scheduled_activities.put_scheduled_activity(
#                 collection=patient_collection,
#                 scheduled_activity=scheduled_activity,
#                 set_id=scheduled_activity[
#                     scope.database.patient.scheduled_activities.SEMANTIC_SET_ID
#                 ],
#             )
#         for activity_log in fake_activity_logs:
#             scope.database.patient.activity_logs.post_activity_log(
#                 collection=patient_collection,
#                 activity_log=activity_log,
#             )
#
#     # assessments, scheduledAssessment, and assessmentLogs
#     fake_assessments_factory = (
#         scope.testing.fake_data.fixtures_fake_assessments.fake_assessments_factory(
#             faker_factory=faker_factory,
#             fake_assessment_contents=fake_assessment_contents,
# >>>>>>> fe17f3e (Updated all activity/assessment APIs)
#
#
#
# =======
#     fake_scheduled_assessments_factory = scope.testing.fake_data.fixtures_fake_scheduled_assessments.fake_scheduled_assessments_factory(
#         faker_factory=faker_factory,
#         fake_assessments=fake_assessments,
#     )
#     # Obtain fake scheduled assessments to pass it in fake_assessment_logs_factory
#     fake_scheduled_assessments = fake_scheduled_assessments_factory()
# >>>>>>> fe17f3e (Updated all activity/assessment APIs)
#
#
# =======
#     # assessments
#     for assessment in fake_assessments:
#         # TODO: use `put` because semantic set id is present in the document
#         scope.database.patient.assessments.put_assessment(
#             collection=patient_collection,
#             assessment=assessment,
#             set_id=assessment[scope.database.patient.assessments.SEMANTIC_SET_ID],
#         )
#     # scheduledAssessments
#     for scheduled_assessment in fake_scheduled_assessments:
#         # TODO: use `put` because semantic set id is present in the document
#         scope.database.patient.scheduled_assessments.put_scheduled_assessment(
#             collection=patient_collection,
#             scheduled_assessment=scheduled_assessment,
#             set_id=scheduled_assessment[
#                 scope.database.patient.scheduled_assessments.SEMANTIC_SET_ID
#             ],
#         )
#     # assessmentLogs
#     for assessment_log in fake_assessment_logs:
#         scope.database.patient.assessment_logs.post_assessment_log(
# >>>>>>> fe17f3e (Updated all activity/assessment APIs)
