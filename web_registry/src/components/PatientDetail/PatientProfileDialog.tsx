import React, { FunctionComponent } from "react";

import { Grid } from "@mui/material";
import { action } from "mobx";
import { observer, useLocalObservable } from "mobx-react";
import {
  clinicCodeValues,
  DepressionTreatmentStatus,
  depressionTreatmentStatusValues,
  followupScheduleValues,
  patientEthnicityValues,
  patientGenderValues,
  patientPronounValues,
  patientRaceValues,
  patientSexValues,
  siteValues,
} from "shared/enums";
import { sortStringsCaseInsensitive } from "shared/sorting";
import { toLocalDateOnly, toUTCDateOnly } from "shared/time";
import { IPatientProfile, IProviderIdentity } from "shared/types";
import {
  GridDateField,
  GridDropdownField,
  GridMultiSelectField,
  GridTextField,
} from "src/components/common/GridField";
import StatefulDialog from "src/components/common/StatefulDialog";

interface IEditPatientProfileContentProps extends Partial<IPatientProfile> {
  availableCareManagerNames: string[];
  onCareManagerChange: (providerName: string) => void;
  onDepressionTreatmentStatusChange: (
    depressionTreatmentStatus?: DepressionTreatmentStatus,
  ) => void;
  onValueChange: (key: string, value: any) => void;
}

const EditPatientProfileContent: FunctionComponent<
  IEditPatientProfileContentProps
> = (props) => {
  const {
    name,
    MRN,
    clinicCode,
    depressionTreatmentStatus,
    followupSchedule,
    birthdate,
    race,
    ethnicity,
    sex,
    gender,
    pronoun,
    primaryOncologyProvider,
    primaryCareManager,
    availableCareManagerNames,
    site,
    enrollmentDate,
    onValueChange,
    onCareManagerChange,
    onDepressionTreatmentStatusChange,
  } = props;

  const sortedAvailableCareManagerNames = sortStringsCaseInsensitive(
    availableCareManagerNames,
  );

  const getTextField = (
    label: string,
    value: any,
    propName: string,
    required?: boolean,
  ) => (
    <GridTextField
      editable
      label={label}
      value={value}
      onChange={(text) => onValueChange(propName, text)}
      required={required}
    />
  );

  const getDropdownField = (
    label: string,
    value: any,
    options: any,
    propName: string,
  ) => (
    <GridDropdownField
      editable
      label={label}
      value={value}
      options={options}
      onChange={(text) => onValueChange(propName, text)}
    />
  );

  return (
    <Grid container spacing={2} alignItems="stretch">
      {getTextField("Patient Name", name, "name", true)}
      {getTextField("MRN", MRN, "MRN", true)}
      {getDropdownField(
        "Clinic Code",
        clinicCode || "",
        clinicCodeValues,
        "clinicCode",
      )}
      {getDropdownField("Site", site || "", siteValues, "site")}
      <GridDateField
        editable
        label="Date of Birth"
        value={birthdate}
        onChange={(text) => onValueChange("birthdate", text)}
      />
      <GridMultiSelectField
        sm={12}
        editable
        label="Race"
        flags={Object.assign(
          {},
          ...patientRaceValues.map((x) => ({ [x]: !!race?.[x] })),
        )}
        flagOrder={[...patientRaceValues]}
        onChange={(flags) => onValueChange("race", flags)}
      />
      {getDropdownField(
        "Ethnicity",
        ethnicity || "",
        patientEthnicityValues,
        "ethnicity",
      )}
      {getDropdownField("Sex", sex || "", patientSexValues, "sex")}
      {getDropdownField("Gender", gender || "", patientGenderValues, "gender")}
      {getDropdownField(
        "Pronouns",
        pronoun || "",
        patientPronounValues,
        "pronoun",
      )}
      {getTextField(
        "Primary Oncology Provider",
        primaryOncologyProvider,
        "primaryOncologyProvider",
      )}
      <GridDropdownField
        editable
        label={"Primary Social Worker"}
        value={primaryCareManager?.name || ""}
        options={sortedAvailableCareManagerNames}
        onChange={(text) => onCareManagerChange(text as string)}
      />
      <GridDropdownField
        editable
        label={"Treatment Status"}
        value={depressionTreatmentStatus || ""}
        options={depressionTreatmentStatusValues}
        onChange={(text) =>
          onDepressionTreatmentStatusChange(text as DepressionTreatmentStatus)
        }
      />
      {getDropdownField(
        "Follow-Up Schedule",
        followupSchedule || "",
        followupScheduleValues,
        "followupSchedule",
      )}
      <GridDateField
        editable
        label="Enrollment Date"
        value={enrollmentDate}
        onChange={(text) => onValueChange("enrollmentDate", text)}
      />
    </Grid>
  );
};

interface IDialogProps {
  open: boolean;
  error?: boolean;
  loading?: boolean;
  onClose: () => void;
}

interface IEditPatientProfileDialogProps extends IDialogProps {
  careManagers: IProviderIdentity[];
  profile: IPatientProfile;
  onSavePatient: (patient: IPatientProfile) => void;
}

export interface IAddPatientProfileDialogProps extends IDialogProps {
  careManagers: IProviderIdentity[];
  onAddPatient: (patient: IPatientProfile) => void;
}

export const EditPatientProfileDialog: FunctionComponent<IEditPatientProfileDialogProps> =
  observer((props) => {
    const {
      profile,
      open,
      error,
      loading,
      onClose,
      onSavePatient,
      careManagers,
    } = props;

    const state = useLocalObservable<IPatientProfile>(() => {
      const existingProfile = { ...profile };

      if (profile.birthdate != undefined) {
        existingProfile.birthdate = toLocalDateOnly(profile.birthdate);
      }
      if (profile.enrollmentDate != undefined) {
        existingProfile.enrollmentDate = toLocalDateOnly(
          profile.enrollmentDate,
        );
      }

      return existingProfile;
    });

    const onValueChange = action((key: string, value: any) => {
      (state as any)[key] = value;
    });

    const onSave = action(() => {
      const updatedProfile = { ...state };

      if (!updatedProfile.birthdate) {
        // Necessary because an empty date is ""
        updatedProfile.birthdate = undefined;
      } else if (state.birthdate != undefined) {
        updatedProfile.birthdate = toUTCDateOnly(updatedProfile.birthdate);
      }
      if (!updatedProfile.enrollmentDate) {
        // Necessary because an empty date is ""
        updatedProfile.enrollmentDate = undefined;
      } else if (state.enrollmentDate != undefined) {
        updatedProfile.enrollmentDate = toUTCDateOnly(
          updatedProfile.enrollmentDate,
        );
      }

      onSavePatient(updatedProfile);
    });

    const onCareManagerChange = action((name: string) => {
      const found = careManagers.find((c) => c.name == name);
      if (!!name && found) {
        state.primaryCareManager = found;
      } else {
        state.primaryCareManager = undefined;
      }
    });

    const onDepressionTreatmentStatusChange = action(
      (depressionTreatmentStatus?: DepressionTreatmentStatus) => {
        state.depressionTreatmentStatus = depressionTreatmentStatus;

        if (depressionTreatmentStatus) {
          if (["D/C"].includes(depressionTreatmentStatus)) {
            state.followupSchedule = "As needed";
          }
        }
      },
    );

    const availableCareManagerNames = careManagers.map((c) => c.name);

    return (
      <StatefulDialog
        open={open}
        error={error}
        loading={loading}
        title="Edit Patient Information"
        content={
          <EditPatientProfileContent
            {...state}
            availableCareManagerNames={availableCareManagerNames}
            onValueChange={onValueChange}
            onCareManagerChange={onCareManagerChange}
            onDepressionTreatmentStatusChange={
              onDepressionTreatmentStatusChange
            }
          />
        }
        handleCancel={onClose}
        handleSave={onSave}
        disableSave={!state.name || !state.MRN}
      />
    );
  });
