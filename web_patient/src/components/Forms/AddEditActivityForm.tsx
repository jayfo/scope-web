import {
    DatePicker,
    TimePicker,
} from '@mui/lab';
import {
    Checkbox,
    Chip,
    // Dialog,
    // DialogContent,
    // DialogTitle,
    FormControlLabel,
    FormHelperText,
    FormGroup,
    Grid,
    // InputLabel,
    // List,
    // ListItem,
    // ListItemText,
    // ListSubheader,
    MenuItem,
    Select,
    SelectChangeEvent,
    Stack,
    Switch,
    TextField,
    Typography,
} from '@mui/material';
// import { compareAsc } from 'date-fns';
import { action } from 'mobx';
import { observer, useLocalObservable } from 'mobx-react';
import React, { Fragment, FunctionComponent } from 'react';
import {DayOfWeek, DayOfWeekFlags, daysOfWeekValues} from 'shared/enums';
import {clearTime, toUTCDateOnly} from 'shared/time';
import {IActivity, IActivitySchedule, IValue /* ILifeAreaValue, KeyedMap */} from 'shared/types';
import { IFormPage, FormDialog } from 'src/components/Forms/FormDialog';
import { FormSection, HelperText, SubHeaderText} from 'src/components/Forms/FormSection';
import { IFormProps } from 'src/components/Forms/GetFormDialog';
import { getRouteParameter, Parameters, ParameterValues } from "src/services/routes";
import { getString } from 'src/services/strings';
import { useStores } from 'src/stores/stores';
import {
    getDayOfWeek,
    // minDate,
} from 'shared/time';
import { AddEditValueDialog } from 'src/components/ValuesInventory/LifeAreaDetail';

export interface IAddEditActivityFormProps extends IFormProps {}

export const AddEditActivityForm: FunctionComponent<IAddEditActivityFormProps> = observer(() => {
    const routeParamForm = getRouteParameter(Parameters.form) as string;
    const routeParamAddSchedule = getRouteParameter(Parameters.addSchedule) == ParameterValues.addSchedule.true;

    const rootStore = useStores();
    const { patientStore, appContentConfig } = rootStore;
    // const { valuesInventory } = patientStore;
    const { lifeAreas } = appContentConfig;

    //
    // View state related to creating or editing an Activity
    //

    interface IActivityViewStateModeNone {
        mode: 'none';
    }
    interface IActivityViewStateModeAdd {
        mode: 'addActivity';
        valueId?: string;
    }
    interface IActivityViewStateModeEdit {
        mode: 'editActivity';
        editActivity: IActivity;
    }
    type IActivityViewModeState = IActivityViewStateModeNone | IActivityViewStateModeAdd | IActivityViewStateModeEdit;

    interface IActivityViewState {
        displayedName: string;

        name: string;
        lifeAreaId: string;
        valueId: string;
        enjoyment: number;
        importance: number;

        modeState: IActivityViewModeState;

        addValueOpen: boolean;
        addValueName: string;
    }

    const initialActivityViewState: IActivityViewState = ((): IActivityViewState => {
        const defaultViewState: IActivityViewState = {
            displayedName: '',

            name: '',
            lifeAreaId: '',
            valueId: '',
            enjoyment: -1,
            importance: -1,

            modeState: {
                mode: 'none',
            },

            addValueOpen: false,
            addValueName: '',
        };

        if (routeParamForm == ParameterValues.form.addActivity) {
            const routeValueId = getRouteParameter(Parameters.valueId);
            const valueIdAndLifeAreaId = (() => {
                if (!routeValueId) {
                    return {};
                }

                const value = patientStore.getValueById(routeValueId);
                console.assert(!!value, 'addActivity value not found');
                if (!value) {
                    return {};
                }

                return {
                    valueId: routeValueId,
                    lifeAreaId: value.lifeAreaId,
                }
            })();

            if(!valueIdAndLifeAreaId.valueId) {
                return defaultViewState;
            } else {
                return {
                    ...defaultViewState,

                    ...valueIdAndLifeAreaId,

                    modeState: {
                        mode: 'addActivity',
                        valueId: valueIdAndLifeAreaId.valueId,
                    },
                };
            }
        } else if (routeParamForm == ParameterValues.form.editActivity) {
            const routeActivityId = getRouteParameter(Parameters.activityId);
            console.assert(!!routeActivityId, 'editActivity parameter activityId not found');
            if (!routeActivityId) {
                return defaultViewState;
            }

            const editActivity = patientStore.getActivityById(routeActivityId);
            console.assert(!!editActivity, 'editActivity activity not found');
            if (!editActivity) {
                return defaultViewState;
            }

            const valueIdAndLifeAreaId = (() => {
                if (!editActivity.valueId) {
                    return {};
                }

                const value = patientStore.getValueById(editActivity.valueId);
                console.assert(!!value, 'editActivity value not found');
                if (!value) {
                    return {};
                }

                return {
                    valueId: editActivity.valueId,
                    lifeAreaId: value.lifeAreaId,
                }
            })();

            return {
                ...defaultViewState,

                displayedName: editActivity.name,

                name: editActivity.name,
                ...valueIdAndLifeAreaId,
                enjoyment: editActivity.enjoyment ? editActivity.enjoyment : defaultViewState.enjoyment,
                importance: editActivity.importance ? editActivity.importance : defaultViewState.importance,

                modeState: {
                    mode: 'editActivity',
                    editActivity: {
                        ...editActivity
                    }
                },
            };
        }

        return defaultViewState;
    })();

    const activityViewState = useLocalObservable<IActivityViewState>(() => initialActivityViewState);

    //
    // View state related to creating or editing an ActivitySchedule
    //

    interface IActivityScheduleViewStateModeNone {
        mode: 'none';
    }
    interface IActivityScheduleViewStateModeAdd {
        mode: 'addActivitySchedule';
        activityId: string;
    }
    interface IActivityScheduleViewStateModeEdit {
        mode: 'editActivitySchedule';
        editActivitySchedule: IActivitySchedule;
    }
    type IActivityScheduleViewModeState = IActivityScheduleViewStateModeNone | IActivityScheduleViewStateModeAdd | IActivityScheduleViewStateModeEdit;

    interface IActivityScheduleViewState {
        minValidDate: Date;

        displayedDate: Date | null;
        displayedTimeOfDay: Date | null;

        date: Date;
        timeOfDay: number;
        hasRepetition: boolean;
        repeatDayFlags: DayOfWeekFlags;

        modeState: IActivityScheduleViewModeState;
    }

    const initialActivityScheduleViewState: IActivityScheduleViewState = ((): IActivityScheduleViewState => {
        const _defaultDate = clearTime(new Date());
        const _defaultTimeOfDay = 9;
        const defaultViewState: IActivityScheduleViewState = {
            displayedDate: _defaultDate,
            minValidDate: clearTime(new Date()),
            displayedTimeOfDay: new Date(1, 1, 1, _defaultTimeOfDay, 0, 0),

            date: _defaultDate,
            timeOfDay: _defaultTimeOfDay,

            hasRepetition: false,
            repeatDayFlags: Object.assign(
                {},
                ...daysOfWeekValues.map((dayOfWeek: DayOfWeek) => ({
                    [dayOfWeek]: false,
                })),
            ),

            modeState: {
                mode: 'none',
            },
        };

        // ActivityScheduling can also be accessed when routeParamForm is ParameterValues.form.addActivity.
        // In that case, the viewState is updated after the activity is created.
        if (routeParamForm == ParameterValues.form.addActivitySchedule) {
            const routeActivityId = getRouteParameter(Parameters.activityId);
            console.assert(!!routeActivityId, 'editActivity parameter activityId not found');
            if (!routeActivityId) {
                return defaultViewState;
            }

            return {
                ...defaultViewState,
                modeState: {
                    mode: 'addActivitySchedule',
                    activityId: routeActivityId,
                }
            }
        } else if (routeParamForm == ParameterValues.form.editActivitySchedule) {
            // TODO Activity Refactor
        }

        return defaultViewState;
    })();

    const activityScheduleViewState = useLocalObservable<IActivityScheduleViewState>(() => initialActivityScheduleViewState);

    const handleSubmitActivity = action(async () => {
        try {
            if (activityViewState.modeState.mode == 'addActivity') {
                // Construct the activity that will be created
                const createActivity: IActivity = {
                    name: activityViewState.name,
                    enjoyment: activityViewState.enjoyment >= 0 ? activityViewState.enjoyment : undefined,
                    importance: activityViewState.importance >= 0 ? activityViewState.importance : undefined,
                    valueId: activityViewState.valueId ? activityViewState.valueId : undefined,

                    editedDateTime: new Date(),
                };

                // Create the activity
                const createdActivity = await patientStore.addActivity(createActivity);

                // Use the created activity to initiate creation of a schedule
                if (createdActivity?.activityId) {
                    activityScheduleViewState.modeState = {
                        mode: "addActivitySchedule",
                        activityId: createdActivity.activityId,
                    }
                }
            } else if (activityViewState.modeState.mode == 'editActivity') {
                // Update the existing activity with current view state
                const editActivity: IActivity = {
                    ...activityViewState.modeState.editActivity,

                    name: activityViewState.name,
                    enjoyment: activityViewState.enjoyment >= 0 ? activityViewState.enjoyment : undefined,
                    importance: activityViewState.importance >= 0 ? activityViewState.importance : undefined,
                    valueId: activityViewState.valueId ? activityViewState.valueId : undefined,

                    editedDateTime: new Date(),
                }

                await patientStore.updateActivity(editActivity);
            }

            return !patientStore.loadActivitiesState.error;
        } catch {
            return false;
        }
    });

    const handleSubmitActivitySchedule = action(async () => {
        try {
            if (activityScheduleViewState.modeState.mode == 'addActivitySchedule') {
                const createActivitySchedule: IActivitySchedule = {
                    activityId: activityScheduleViewState.modeState.activityId,
                    date: toUTCDateOnly(activityScheduleViewState.date),
                    timeOfDay: activityScheduleViewState.timeOfDay,

                    hasRepetition: activityScheduleViewState.hasRepetition,
                    repeatDayFlags: activityScheduleViewState.hasRepetition ? activityScheduleViewState.repeatDayFlags : undefined,

                    // TODO Future Support for Reminders
                    hasReminder: false,

                    editedDateTime: new Date(),
                };

                await patientStore.addActivitySchedule(createActivitySchedule);
            } else if (activityScheduleViewState.modeState.mode == 'editActivitySchedule') {
                const editActivitySchedule: IActivitySchedule = {
                    ...activityScheduleViewState.modeState.editActivitySchedule,

                    date: toUTCDateOnly(activityScheduleViewState.date),
                    timeOfDay: activityScheduleViewState.timeOfDay,

                    hasRepetition: activityScheduleViewState.hasRepetition,
                    repeatDayFlags: activityScheduleViewState.hasRepetition ? activityScheduleViewState.repeatDayFlags : undefined,

                    editedDateTime: new Date(),
                }

                await patientStore.updateActivitySchedule(editActivitySchedule);
            }

            return !patientStore.loadActivitySchedulesState.error;
        } catch {
            return false;
        }
    });

    const handleAddValueOpen = action(() => {
        activityViewState.addValueOpen = true;
        activityViewState.addValueName = '';
    });

    const handleAddValueCancel = action(() => {
        activityViewState.addValueOpen = false;
    });

    const handleAddValueChange = action((change: string) => {
        activityViewState.addValueName = change;
    });

    const handleAddValueSave = action(async () => {
        activityViewState.addValueOpen = false;

        const createValue: IValue = {
            name: activityViewState.addValueName,
            lifeAreaId: activityViewState.lifeAreaId,
            editedDateTime: new Date(),
        }

        const createdValue = await patientStore.addValue(createValue);
        if(createdValue) {
            activityViewState.valueId = createdValue.valueId as string;
        }
    });

    const handleActivityChangeName = action((event: React.ChangeEvent<HTMLInputElement>) => {
        // DisplayedName can only trimStart because full trim means never being able to add a space
        activityViewState.displayedName = event.target.value.trimStart();

        activityViewState.name = activityViewState.displayedName.trim();
    });

    const handleActivitySelectEnjoyment = action((event: SelectChangeEvent<number>) => {
        activityViewState.enjoyment = Number(event.target.value);
    });

    const handleActivitySelectImportance = action((event: SelectChangeEvent<number>) => {
        activityViewState.importance = Number(event.target.value);
    });

    const handleActivitySelectLifeArea = action((event: SelectChangeEvent<string>) => {
        activityViewState.lifeAreaId = event.target.value as string;

        // An empty string will fail validation
        // Default to the first item in the list
        activityViewState.valueId = (() => {
            const lifeAreaValues = patientStore.getValuesByLifeAreaId(activityViewState.lifeAreaId);
            if (lifeAreaValues.length) {
                const valueMin = lifeAreaValues.reduce((minimum, current) => {
                    return minimum.name.localeCompare(current.name, undefined, {sensitivity: 'base'}) < 0 ? minimum : current;
                }, lifeAreaValues[0]);

                return valueMin.valueId as string;
            } else {
                return '';
            }
        })();
    });

    const handleActivitySelectValue = action((event: SelectChangeEvent<string>) => {
        activityViewState.valueId = event.target.value as string;
    });

    const handleActivityScheduleChangeDate = action((date: Date | null) => {
        activityScheduleViewState.displayedDate = date;

        if (activityScheduleValidateDate(date).valid) {
            activityScheduleViewState.date = date as Date;
        }
    });

    const handleActivityScheduleChangeTimeOfDay = action((date: Date | null) => {
        activityScheduleViewState.displayedTimeOfDay = date;

        if (activityScheduleValidateTimeOfDay(date).valid) {
            activityScheduleViewState.timeOfDay = (date as Date).getHours();
        }
    });

    const handleActivityScheduleChangeHasRepetition = action((event: React.ChangeEvent<HTMLInputElement>) => {
        activityScheduleViewState.hasRepetition = event.target.checked;

        // Clear all flags back to false
        Object.assign(
            activityScheduleViewState.repeatDayFlags,
            ...daysOfWeekValues.map((dayOfWeek: DayOfWeek) => ({
                [dayOfWeek]: false,
            })),
        )

        // If we just enabled repetition, default to the day of week from the scheduled date
        if (activityScheduleViewState.hasRepetition) {
            activityScheduleViewState.repeatDayFlags[getDayOfWeek(activityScheduleViewState.date)] = true;
        }
    });

    const handleActivityScheduleChangeRepeatDays = action((event: React.ChangeEvent<HTMLInputElement>, dayOfWeek: DayOfWeek) => {
        activityScheduleViewState.repeatDayFlags[dayOfWeek] = event.target.checked;
    });

    const activityValidateNext = () => {
        // Name cannot be blank
        if (!activityViewState.name) {
            return {
                valid: false,
                error: true,
            };
        }

        // Name must validate
        const validateName = activityValidateName(activityViewState.name);
        if (validateName.error) {
            return validateName;
        }

        // ValueId must validate
        const validateValueId = activityValidateValueId(activityViewState.lifeAreaId, activityViewState.valueId);
        if (validateValueId.error) {
            return validateValueId;
        }

        // If editing an activity, something must have changed
        if (activityViewState.modeState.mode == 'editActivity') {
            const editActivity = activityViewState.modeState.editActivity;

            let changeDetected = false;
            changeDetected ||= activityViewState.name != editActivity.name;
            changeDetected ||= activityViewState.valueId != editActivity.valueId;
            changeDetected ||= activityViewState.enjoyment != (!!editActivity.enjoyment ? editActivity.enjoyment : -1);
            changeDetected ||= activityViewState.importance != (!!editActivity.importance ? editActivity.importance : -1);

            if(!changeDetected) {
                return {
                    valid: false,
                    error: true,
                };
            }
        }

        return {
            valid: true,
            error: false,
        }
    }

    const activityValidateName = (name: string) => {
        // Name must be unique, accounting for case-insensitive comparisons
        const nameIsUnique = patientStore.activities.filter((activity: IActivity): boolean => {
            // In case of edit, do not validate against the activity being edited
            if (activityViewState.modeState.mode == 'editActivity') {
                return activity.activityId != activityViewState.modeState.editActivity.activityId;
            }

            return true;
        }).findIndex((activity: IActivity): boolean => {
            // Search for a case-insensitive match
            return activity.name.toLocaleLowerCase() == name.toLocaleLowerCase();
        }) < 0;
        if(!nameIsUnique) {
            return {
                valid: false,
                error: true,
                errorMessage: getString('form_add_edit_activity_name_validation_not_unique'),
            };
        }

        return {
            valid: true,
            error: false,
        };
    }

    const activityValidateValueId = (lifeAreaId: string, valueId: string) => {
        if (lifeAreaId && !valueId) {
            return {
                valid: false,
                error: true,
                errorMessage: getString('form_add_edit_activity_valueid_validation_none_selected'),
            };
        }

        return {
            valid: true,
            error: false,
        };
    }

    const activityScheduleValidateNext = () => {
        // Date must validate
        const validateDate = activityScheduleValidateDate(activityScheduleViewState.displayedDate);
        if (validateDate.error) {
            return validateDate;
        }

        // Time must validate
        const validateTime = activityScheduleValidateTimeOfDay(activityScheduleViewState.displayedTimeOfDay);
        if (validateTime.error) {
            return validateTime;
        }

        // Repetition must validate
        const validateRepetition = activityScheduleValidateRepetition(activityScheduleViewState.hasRepetition, activityScheduleViewState.repeatDayFlags);
        if (validateRepetition.error) {
            return validateRepetition;
        }

        // If editing an activity schedule, something must have changed
        if (activityScheduleViewState.modeState.mode == 'editActivitySchedule') {
            const editActivitySchedule = activityScheduleViewState.modeState.editActivitySchedule;

            let changeDetected = false;
            changeDetected ||= activityScheduleViewState.date != editActivitySchedule.date;
            changeDetected ||= activityScheduleViewState.timeOfDay != editActivitySchedule.timeOfDay;
            changeDetected ||= activityScheduleViewState.hasRepetition != editActivitySchedule.hasRepetition;
            if (!changeDetected && activityScheduleViewState.hasRepetition && editActivitySchedule.hasRepetition) {
                const repeatDayFlagsChangeDetected = daysOfWeekValues.reduce((accumulator, dayOfWeek) => {
                    const reduceEditActivityScheduleRepeatDayFlags = editActivitySchedule.repeatDayFlags as DayOfWeekFlags;

                    return accumulator || (activityScheduleViewState.repeatDayFlags[dayOfWeek] != reduceEditActivityScheduleRepeatDayFlags[dayOfWeek]);
                }, false);

                changeDetected ||= repeatDayFlagsChangeDetected;
            }

            if(!changeDetected) {
                return {
                    valid: false,
                    error: true,
                };
            }
        }

        return {
            valid: true,
            error: false,
        }
    }

    const activityScheduleValidateDate = (date: Date | null) => {
        if (!date || date.toString() == "Invalid Date") {
            return {
                valid: false,
                error: true,
                errorMessage: getString('form_add_edit_activity_schedule_date_validation_invalid_format'),
            };
        }

        if (date < activityScheduleViewState.minValidDate) {
            return {
                valid: false,
                error: true,
                errorMessage: "Date must be on or after " +
                    activityScheduleViewState.minValidDate.toLocaleDateString() +
                    ".",
            };
        }

        return {
            valid: true,
            error: false,
        };
    }

    const activityScheduleValidateTimeOfDay = (date: Date | null) => {
        if (!date || date.toString() == "Invalid Date") {
            return {
                valid: false,
                error: true,
                errorMessage: getString('form_add_edit_activity_schedule_time_of_day_validation_invalid_format'),
            };
        }

        return {
            valid: true,
            error: false,
        };
    }

    const activityScheduleValidateRepetition = (hasRepetition: boolean, repeatDayFlags: DayOfWeekFlags) => {
        if (hasRepetition) {
            const numDaysRepeat = daysOfWeekValues.reduce((accumulator, dayOfWeek) => {
                return accumulator + (repeatDayFlags[dayOfWeek] ? 1 : 0);
            }, 0);

            if (numDaysRepeat == 0) {
                return {
                    valid: false,
                    error: true,
                    errorMessage: getString('form_add_edit_activity_schedule_repetition_validation_no_days'),
                };
            }
        }

        return {
            valid: true,
            error: false,
        };
    }

    /* TODO Activity Refactor: Abandoned Activity Import Code
    // const values = valuesInventory?.values || [];
    // const groupedActivities: KeyedMap<ImportableActivity[]> = {};
    // let activityCount = 0;

    // const values: ILifeAreaValue[] = [];
    // values.forEach((value) => {
    //     const lifearea = value.lifeareaId;
    //     if (!groupedActivities[lifearea]) {
    //         groupedActivities[lifearea] = [];
    //     }
    //
    //     value.activities.forEach((activity) => {
    //         groupedActivities[lifearea].push({
    //             activity: activity.name,
    //             value: value.name,
    //             lifeareaId: lifearea,
    //         });
    //
    //         activityCount += groupedActivities[lifearea].length;
    //     });
    // });

    const handleOpenImportActivity = action(() => {
        viewState.openImportActivity = true;
    });

    const handleImportActivityItemClick = action((activity: ImportableActivity | undefined) => {
        viewState.openActivityDialog = false;

        if (!!activity) {
            dataState.name = activity.activity;
            dataState.value = activity.value;
            dataState.lifeareaId = activity.lifeareaId;
        }
    });

    {activityCount > 0 && (
        <Grid container justifyContent="flex-end">
            <Chip
                sx={{ marginTop: 1 }}
                variant="outlined"
                color="primary"
                size="small"
                label={getString('Form_add_activity_describe_name_import_button')}
                onClick={handleOpenImportActivity}
            />
            <Dialog
                maxWidth="phone"
                open={viewState.openActivityDialog}
                onClose={() => handleImportActivityItemClick(undefined)}>
                <DialogTitle>
                    {getString('Form_add_activity_describe_name_import_dialog_title')}
                </DialogTitle>

                <DialogContent dividers>
                    <List disablePadding>
                        {Object.keys(groupedActivities).map((lifearea) => {
                            const lifeareaName =
                                lifeAreas.find((l) => l.id == lifearea)?.name || lifearea;
                            return (
                                <Fragment key={lifearea}>
                                    <ListSubheader disableGutters>{lifeareaName}</ListSubheader>
                                    {groupedActivities[lifearea].map((activity, idx) => (
                                        <ListItem
                                            disableGutters
                                            button
                                            onClick={() => handleImportActivityItemClick(activity)}
                                            key={idx}>
                                            <ListItemText primary={activity.activity} />
                                        </ListItem>
                                    ))}
                                </Fragment>
                            );
                        })}
                    </List>
                </DialogContent>
            </Dialog>
        </Grid>
    )}
    */

    // Validate name, not displayed name, because we want to ignore whitespace that will be trimmed
    const _activityPageValidateName = activityValidateName(activityViewState.name);
    const _activityPageValidateValueId = activityValidateValueId(activityViewState.lifeAreaId, activityViewState.valueId);
    const _hideLifeAreaAndValue = (
        activityViewState.modeState.mode == "addActivity" &&
        !!activityViewState.modeState.valueId
    );
    const activityPage = (
        <Stack spacing={4}>
            <FormSection
                prompt={getString('form_add_edit_activity_name_prompt')}
                help={getString('form_add_edit_activity_name_help')}
                content={
                    <Fragment>
                        <TextField
                            fullWidth
                            value={activityViewState.displayedName}
                            onChange={handleActivityChangeName}
                            variant="outlined"
                            multiline
                            error={_activityPageValidateName.error}
                            helperText={
                                _activityPageValidateName.error &&
                                _activityPageValidateName.errorMessage
                            }
                        />
                    </Fragment>
                }
            />

            {(!_hideLifeAreaAndValue && <FormSection
                addPaddingTop
                prompt={getString('form_add_edit_activity_life_area_value_prompt')}
                help={getString('form_add_edit_activity_life_area_value_help')}
                content={
                    <Fragment>
                        <SubHeaderText>{getString('form_add_edit_activity_life_area_label')}</SubHeaderText>
                        <HelperText>{getString('form_add_edit_activity_life_area_help')}</HelperText>
                        <Select
                            variant="outlined"
                            value={activityViewState.lifeAreaId}
                            onChange={handleActivitySelectLifeArea}
                            fullWidth
                        >
                            <MenuItem key='' value=''></MenuItem>
                            {/* TODO Activity Refactor: Sort life areas */}
                            {lifeAreas.map((lifeArea) => (
                                <MenuItem key={lifeArea.id} value={lifeArea.id}>
                                    {lifeArea.name}
                                </MenuItem>
                            ))}
                        </Select>
                        <SubHeaderText>{getString('form_add_edit_activity_value_label')}</SubHeaderText>
                        <FormHelperText
                            error={_activityPageValidateValueId.error}
                        >
                            {_activityPageValidateValueId.valid ? getString('form_add_edit_activity_value_help') : _activityPageValidateValueId.errorMessage}
                        </FormHelperText>
                        <Select
                            variant="outlined"
                            value={activityViewState.valueId}
                            onChange={handleActivitySelectValue}
                            fullWidth
                            disabled={!activityViewState.lifeAreaId || patientStore.getValuesByLifeAreaId(activityViewState.lifeAreaId).length == 0}
                        >
                            {activityViewState.lifeAreaId && (
                                patientStore.getValuesByLifeAreaId(activityViewState.lifeAreaId)
                                    .slice()
                                    .sort((a, b) => { return a.name.localeCompare(b.name, undefined, {sensitivity: 'base'}); })
                                    .map((value, idx) => (
                                    <MenuItem key={idx} value={value.valueId}>
                                        {value.name}
                                    </MenuItem>
                                ))
                            )}
                        </Select>
                        <Grid container justifyContent="flex-end">
                            <Chip
                                sx={{ marginTop: 1 }}
                                color="primary"
                                size="small"
                                label={getString('form_add_edit_activity_add_value_button')}
                                onClick={handleAddValueOpen}
                                disabled={!activityViewState.lifeAreaId}
                            />
                        </Grid>
                    </Fragment>
                }
            />)}

            <FormSection
                addPaddingTop
                prompt={getString('form_add_edit_activity_enjoyment_prompt')}
                help={getString('form_add_edit_activity_enjoyment_help')}
                content={
                    <Select
                        labelId="activity-enjoyment-label"
                        id="activity-enjoyment"
                        value={activityViewState.enjoyment}
                        onChange={handleActivitySelectEnjoyment}
                    >
                        <MenuItem key='' value='-1'></MenuItem>
                        {[...Array(11).keys()].map((v) => (
                            <MenuItem key={v} value={v}>
                                {v}
                            </MenuItem>
                        ))}
                    </Select>
                }
            />

            <FormSection
                addPaddingTop
                prompt={getString('form_add_edit_activity_importance_prompt')}
                help={getString('form_add_edit_activity_importance_help')}
                content={
                    <Select
                        labelId="activity-importance-label"
                        id="activity-importance"
                        value={activityViewState.importance}
                        onChange={handleActivitySelectImportance}
                    >
                        <MenuItem key='' value='-1'></MenuItem>
                        {[...Array(11).keys()].map((v) => (
                            <MenuItem key={v} value={v}>
                                {v}
                            </MenuItem>
                        ))}
                    </Select>
                }
            />

            { /* TODO: Cleanup Error and Loading Handlers */ }
            <AddEditValueDialog
                open={activityViewState.addValueOpen}
                isEdit={false}
                lifeArea={(() => {
                    const lifeAreaContent = rootStore.getLifeAreaContent(activityViewState.lifeAreaId);

                    if (lifeAreaContent) {
                        return lifeAreaContent.name;
                    } else {
                        return '';
                    }
                })()}
                value={activityViewState.addValueName}
                examples={(() => {
                    const lifeAreaContent = rootStore.getLifeAreaContent(activityViewState.lifeAreaId);

                    if (lifeAreaContent) {
                        return lifeAreaContent.examples.map((example) => {
                            return example.name;
                        });
                    } else {
                        return [];
                    }
                })()}
                error={patientStore.loadValuesInventoryState.error}
                loading={patientStore.loadValuesInventoryState.pending}
                handleCancel={handleAddValueCancel}
                handleChange={handleAddValueChange}
                handleSave={handleAddValueSave}
            />
        </Stack>
    );

    const _activitySchedulePageValidateDate = activityScheduleValidateDate(activityScheduleViewState.displayedDate);
    const _activitySchedulePageValidateTimeOfDay = activityScheduleValidateTimeOfDay(activityScheduleViewState.displayedTimeOfDay);
    const _activitySchedulePageValidateRepetition = activityScheduleValidateRepetition(activityScheduleViewState.hasRepetition, activityScheduleViewState.repeatDayFlags);
    const activitySchedulePage = (
        <Stack spacing={4}>
            <FormSection
                prompt={getString('form_add_edit_activity_schedule_when_prompt')}
                content={
                    <Fragment>
                        <SubHeaderText>{getString('form_add_edit_activity_schedule_date_label')}</SubHeaderText>
                        <HelperText>{getString('form_add_edit_activity_schedule_date_help')}</HelperText>
                        <DatePicker
                            value={activityScheduleViewState.date}
                            onChange={handleActivityScheduleChangeDate}
                            minDate={activityScheduleViewState.minValidDate}
                            renderInput={(params) => (
                                <TextField
                                    variant="outlined"
                                    margin="none"
                                    fullWidth
                                    {...params}
                                    InputLabelProps={{
                                        shrink: true,
                                        sx: { position: 'relative' },
                                    }}
                                    error={_activitySchedulePageValidateDate.error}
                                    helperText={
                                        _activitySchedulePageValidateDate.error &&
                                        _activitySchedulePageValidateDate.errorMessage
                                    }
                                />
                            )}
                        />
                        <SubHeaderText>{getString('form_add_edit_activity_schedule_time_of_day_label')}</SubHeaderText>
                        <HelperText>{getString('form_add_edit_activity_schedule_time_of_day_help')}</HelperText>
                        <TimePicker
                            value={new Date(1, 1, 1, activityScheduleViewState.timeOfDay, 0, 0)}
                            onChange={handleActivityScheduleChangeTimeOfDay}
                            renderInput={(params) => (
                                <TextField
                                    variant="outlined"
                                    margin="none"
                                    fullWidth
                                    {...params}
                                    InputLabelProps={{
                                        shrink: true,
                                        sx: { position: 'relative' },
                                    }}
                                    error={_activitySchedulePageValidateTimeOfDay.error}
                                    helperText={
                                        _activitySchedulePageValidateTimeOfDay.error &&
                                        _activitySchedulePageValidateTimeOfDay.errorMessage
                                    }
                                />
                            )}
                            ampm={true}
                            views={['hours']}
                        />
                    </Fragment>
                }
            />

            <FormSection
                addPaddingTop
                prompt={getString("form_add_edit_activity_schedule_has_repetition_prompt")}
                content={
                <Fragment>
                    <Grid container alignItems="center" spacing={1} justifyContent="flex-start">
                        <Grid item>
                            <Typography>{getString('Form_button_no')}</Typography>
                        </Grid>
                        <Grid item>
                            <Switch
                                checked={activityScheduleViewState.hasRepetition}
                                color="default"
                                onChange={handleActivityScheduleChangeHasRepetition}
                                name="onOff"
                            />
                        </Grid>
                        <Grid item>
                            <Typography>{getString('Form_button_yes')}</Typography>
                        </Grid>
                    </Grid>
                </Fragment>
                }
            />

            {activityScheduleViewState.hasRepetition && (
                <FormSection
                    addPaddingTop
                    prompt={getString('form_add_edit_activity_schedule_repeat_days_prompt')}
                    content={
                        <Fragment>
                            {_activitySchedulePageValidateRepetition.error && (
                                <FormHelperText error={true}>
                                    {_activitySchedulePageValidateRepetition.errorMessage}
                                </FormHelperText>
                            )}
                            <FormGroup>
                                {daysOfWeekValues.map((dayOfWeek) => {
                                    return (
                                        <FormControlLabel
                                            key={dayOfWeek}
                                            control={
                                                <Checkbox
                                                    checked={activityScheduleViewState.repeatDayFlags[dayOfWeek]}
                                                    onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
                                                        handleActivityScheduleChangeRepeatDays(event, dayOfWeek)
                                                    }
                                                    value={dayOfWeek}
                                                />
                                            }
                                            label={dayOfWeek}
                                        />
                                    );
                                })}
                            </FormGroup>
                        </Fragment>
                    }
                />
            )}
        </Stack>
    );

    { /* TODO Activity Refactor: Abandoned Schedule and Notification Code
    const reminderPage = (
        <Stack spacing={4}>
            <FormSection
                addPaddingTop
                prompt={getString(!!activity ? 'Form_add_activity_reminder_section' : 'Form_add_activity_reminder')}
                content={
                    <Grid container alignItems="center" spacing={1} justifyContent="flex-start">
                        <Grid item>
                            <Typography>{getString('Form_button_no')}</Typography>
                        </Grid>
                        <Grid item>
                            <Switch
                                checked={dataState.hasReminder}
                                color="default"
                                onChange={(event: React.ChangeEvent<HTMLInputElement>) =>
                                    handleValueChange('hasReminder', event.target.checked)
                                }
                                name="onOff"
                            />
                        </Grid>
                        <Grid item>
                            <Typography>{getString('Form_button_yes')}</Typography>
                        </Grid>
                    </Grid>
                }
            />
            {dataState.hasReminder && (
                <FormSection
                    addPaddingTop
                    prompt={getString(
                        !!activity ? 'Form_add_activity_reminder_time_label' : 'Form_add_activity_reminder_time',
                    )}
                    content={
                        <TimePicker
                            value={new Date(1, 1, 1, dataState.reminderTimeOfDay, 0, 0) || new Date()}
                            onChange={(date: Date | null) => handleValueChange('reminderTimeOfDay', date?.getHours())}
                            renderInput={(params) => (
                                <TextField
                                    variant="outlined"
                                    margin="none"
                                    fullWidth
                                    {...params}
                                    InputLabelProps={{
                                        shrink: true,
                                        sx: { position: 'relative' },
                                    }}
                                />
                            )}
                            ampm={true}
                            views={['hours']}
                        />
                    }
                />
            )}
        </Stack>
    );
    */ }

    const pages: IFormPage[] = [];
    if (
        (routeParamForm == ParameterValues.form.addActivity) ||
        (routeParamForm == ParameterValues.form.editActivity)
    ) {
        pages.push({
            content: activityPage,
            title: (() => {
                if (activityViewState.modeState.mode == "addActivity") {
                    return getString("form_add_activity_title");
                } else if (activityViewState.modeState.mode == "editActivity") {
                    return getString("form_edit_activity_title");
                } else {
                    return undefined;
                }
            })(),
            canGoNext: activityValidateNext().valid,
            onSubmit: handleSubmitActivity,
            submitToast: (() => {
                if (activityViewState.modeState.mode == "addActivity") {
                    return getString("form_add_activity_submit_success");
                } else if (activityViewState.modeState.mode == "editActivity") {
                    return getString("form_edit_activity_submit_success");
                } else {
                    return undefined;
                }
            })(),
        });
    }

    if (
        ((routeParamForm == ParameterValues.form.addActivity) && routeParamAddSchedule) ||
        (routeParamForm == ParameterValues.form.addActivitySchedule) ||
        (routeParamForm == ParameterValues.form.editActivitySchedule)
    ) {
        pages.push(
            {
                content: activitySchedulePage,
                title: (() => {
                    if (activityScheduleViewState.modeState.mode == "addActivitySchedule") {
                        return getString("form_add_activity_schedule_title");
                    } else if (activityScheduleViewState.modeState.mode == "editActivitySchedule") {
                        return getString("form_edit_activity_schedule_title");
                    } else {
                        return undefined;
                    }
                })(),
                canGoNext: activityScheduleValidateNext().valid,
                onSubmit: handleSubmitActivitySchedule,
                submitToast: (() => {
                    if (activityScheduleViewState.modeState.mode == "addActivitySchedule") {
                        return getString("form_add_activity_schedule_submit_success");
                    } else if (activityScheduleViewState.modeState.mode == "editActivitySchedule") {
                        return getString("form_edit_activity_schedule_submit_success");
                    } else {
                        return undefined;
                    }
                })(),
            }
        );
    }

    return (
        <FormDialog
            isOpen={true}
            canClose={false}
            loading={patientStore.loadActivitiesState.pending}
            pages={pages}
        />
    );
});

export default AddEditActivityForm;
