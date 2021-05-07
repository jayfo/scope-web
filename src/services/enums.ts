export type OtherSpecify = 'Other';

export const patientSexValues = ['Male', 'Female'] as const;
export type PatientSex = typeof patientSexValues[number];

export const clinicCodeValues = [
    'Breast',
    'Endocrine',
    'GI',
    'GI – Pancreatic',
    'GU',
    'GYN',
    'HEME',
    'HEME – Sickle Cell',
    'HNL',
    'Immunotherapy',
    'Melanoma/Renal',
    'Neuro',
    'NW Hospital',
    'Sarcoma',
    'Transplant – Auto',
    'Transplant – Allo',
    'Transplant – CAR-T',
    'Transplant – LTFU',
    'Transplant – TTC',
] as const;
export type ClinicCode = typeof clinicCodeValues[number];

export type AllClinicCode = 'All Clinics';

export const treatmentStatusValues = [
    'Active',
    'Active Distressed',
    'Deceased',
    'Discharged',
    'Followed by Outside MHP ONLY',
    'Followed by Psych ONLY',
    'Relapse Prevention',
    'Inactive',
    'Continued',
] as const;
export type TreatmentStatus = typeof treatmentStatusValues[number];

export const followupScheduleValues = ['1-week follow-up', '2-week follow-up', '4-week follow-up'] as const;
export type FollowupSchedule = typeof followupScheduleValues[number];

export const discussionFlagValues = [
    'None',
    'Flag as safety risk',
    'Flag for discussion',
    'Flag for discussion & safety risk',
] as const;
export type DiscussionFlag = typeof discussionFlagValues[number];

export const treatmentRegimenValues = [
    'Surgery',
    'Chemotherapy',
    'Radiation',
    'Stem Cell Transplant',
    'Immunotherapy',
    'CAR-T',
    'Endocrine',
    'Surveillance',
] as const;
export type TreatmentRegimen = typeof treatmentRegimenValues[number] | OtherSpecify;

export const referralValues = [
    'None',
    'Psychiatry',
    'Psychology',
    'Pt Navigation',
    'Integrative Medicine',
    'Spiritual Care',
    'Palliative Care',
] as const;
export type Referral = typeof referralValues[number] | OtherSpecify;

export const sessionTypeValues = ['In person at clinic', 'Telehealth', 'Phone', 'Group', 'Home'] as const;
export type SessionType = typeof sessionTypeValues[number] | OtherSpecify;

export const treatmentPlanValues = [
    'Maintain current treatment',
    'Adjust treatment plan',
    'Monitor only',
    'No further follow-up',
    'Refer to community',
] as const;
export type TreatmentPlan = typeof treatmentPlanValues[number];

export const treatmentChangeValues = ['None', 'Medication', 'Counseling'] as const;
export type TreatmentChange = typeof treatmentChangeValues[number] | OtherSpecify;

export const behavioralActivationChecklistValues = [
    'Review of the BA model',
    'Values and goals assessment',
    'Activity scheduling',
    'Mood and activity monitoring',
    'Relaxation',
    'Contingency management',
    'Managing avoidance behaviors',
    'Problem-solving',
] as const;
export type BehavioralActivationChecklistItem = typeof behavioralActivationChecklistValues[number];

export const assessmentFrequencyValues = ['Daily', 'Once a week', 'Every 2 weeks', 'Monthly'] as const;
export type AssessmentFrequency = typeof assessmentFrequencyValues[number];

export const phq9ItemValues = [
    'Interest',
    'Feeling',
    'Sleep',
    'Tired',
    'Apetite',
    'Failure',
    'Concentrating',
    'Slowness',
    'Suicide',
] as const;
export type PHQ9Item = typeof phq9ItemValues[number];

export const gad7ItemValues = [
    'Anxious',
    'Constant worrying',
    'Worrying too much',
    'Trouble relaxing',
    'Restless',
    'Irritable',
    'Afraid',
] as const;
export type GAD7Item = typeof gad7ItemValues[number];