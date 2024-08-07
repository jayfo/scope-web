import React, { FunctionComponent } from "react";

import { Grid } from "@mui/material";
import {
  GridColDef,
  GridColumnHeaderParams,
  GridRowHeightParams,
  GridRowParams,
} from "@mui/x-data-grid";
import { CaseReviewEntryType, SessionType } from "shared/enums";
import { formatDateOnly } from "shared/time";
import {
  ICaseReview,
  IReferralStatus,
  ISession,
  ISessionOrCaseReview,
  isSession,
  KeyedMap,
} from "shared/types";
import {
  renderMultilineCell,
  Table,
  TableRowHeight_3RowsNoScroll,
  TableRowHeight_5RowsNoScroll,
} from "src/components/common/Table";
import { usePatient } from "src/stores/stores";
import styled from "styled-components";

const ColumnHeader = styled.div({
  whiteSpace: "initial",
  fontWeight: 500,
  lineHeight: "1rem",
  textAlign: "center",
});

const renderHeader = (props: GridColumnHeaderParams) => (
  <ColumnHeader>{props.colDef.headerName}</ColumnHeader>
);

const NA = "--";

interface ISessionTableData {
  id: string;
  date: string;
  type: SessionType | CaseReviewEntryType;
  billableMinutes: number | string;
  flag: string;
  medications: string;
  behavioralStrategies: string;
  referrals: string;
  otherRecommendations: string;
  note: string;
}

export interface ISessionReviewTableProps {
  sessionOrReviews: ReadonlyArray<ISessionOrCaseReview>;
  onSessionClick?: (sessionId: string) => void;
  onReviewClick?: (caseReviewId: string) => void;
}

export const SessionReviewTable: FunctionComponent<ISessionReviewTableProps> = (
  props,
) => {
  const currentPatient = usePatient();

  const { sessionOrReviews, onSessionClick, onReviewClick } = props;

  const onRowClick = (param: GridRowParams) => {
    const id = param.row["id"] as string;

    if (param.row["type"] == "Case Review") {
      onReviewClick && onReviewClick(id);
    } else {
      onSessionClick && onSessionClick(id);
    }
  };

  // Column names map to IPatientStore property names
  const columns: GridColDef[] = [
    {
      // Hidden by columnVisibilityModel
      field: "id",
      headerName: "Id",
      renderHeader,
      headerAlign: "center",
    },
    {
      field: "date",
      headerName: "Date",
      width: 65,
      renderHeader,
      align: "center",
      headerAlign: "center",
    },
    {
      field: "type",
      headerName: "Type",
      width: 80,
      renderHeader,
      align: "center",
      headerAlign: "center",
    },
    {
      field: "billableMinutes",
      headerName: "Bill Min",
      width: 25,
      renderHeader,
      align: "center",
      type: "number",
      headerAlign: "center",
    },
    {
      field: "medications",
      headerName: "Med Changes / Notes",
      width: 150,
      renderHeader,
      renderCell: renderMultilineCell,
      headerAlign: "center",
    },
    {
      field: "behavioralStrategies",
      headerName: "Behavioral Strategies",
      width: 150,
      renderHeader,
      renderCell: renderMultilineCell,
      headerAlign: "center",
    },
    {
      field: "referrals",
      headerName: "Referrals",
      width: 150,
      renderHeader,
      renderCell: renderMultilineCell,
      headerAlign: "center",
    },
    {
      field: "otherRecommendations",
      headerName: "Other Rec / Action Items",
      width: 200,
      renderHeader,
      renderCell: renderMultilineCell,
      headerAlign: "center",
    },
    {
      field: "note",
      headerName: "Note",
      minWidth: 200,
      flex: 1,
      renderHeader,
      renderCell: renderMultilineCell,
      headerAlign: "center",
    },
  ];

  const generateFlagText = (
    flags: KeyedMap<boolean | string>,
    other: string,
  ) => {
    var concatValues = Object.keys(flags)
      .filter((k) => flags[k] && k != "Other")
      .join(", ");
    if (flags["Other"]) {
      concatValues = [concatValues, other || "Other"].join(", ");
    }

    return concatValues;
  };

  const generateReferralText = (referrals: IReferralStatus[]) => {
    return referrals
      .map((ref) =>
        ref.referralType == "Other" ? ref.referralOther : ref.referralType,
      )
      .join(", ");
  };

  const getSessionData = (session: ISession): ISessionTableData => ({
    id: session.sessionId || "--",
    date: `${formatDateOnly(session.date, "MM/dd/yy")}`,
    type: session.sessionType,
    billableMinutes: session.billableMinutes,
    flag: "TBD",
    medications: session.medicationChange,
    behavioralStrategies: generateFlagText(
      session.behavioralStrategyChecklist,
      session.behavioralStrategyOther,
    ),
    referrals: generateReferralText(session.referrals),
    otherRecommendations: session.otherRecommendations,
    note: session.sessionNote,
  });

  const getReviewData = (review: ICaseReview): ISessionTableData => ({
    id: review.caseReviewId || "--",
    date: `${formatDateOnly(review.date, "MM/dd/yy")}`,
    type: "Case Review",
    billableMinutes: NA,
    flag: "TBD",
    medications: review.medicationChange,
    behavioralStrategies: review.behavioralStrategyChange,
    referrals: review.referralsChange,
    otherRecommendations: review.otherRecommendations,
    note: review.reviewNote,
  });

  const data = sessionOrReviews.map((p) => {
    if (isSession(p)) {
      return getSessionData(p);
    } else {
      return getReviewData(p as ICaseReview);
    }
  });

  const getRowHeight = React.useCallback((param: GridRowHeightParams) => {
    const id = param.id as string;

    const data = (() => {
      const review = currentPatient.getCaseReviewById(id);
      if (!!review) {
        return getReviewData(review);
      }

      const session = currentPatient.getSessionById(id);
      if (!!session) {
        return getSessionData(session);
      }

      throw new Error("Invalid row id");
    })();

    if (data.otherRecommendations.length > 200 || data.note.length > 400) {
      return TableRowHeight_5RowsNoScroll;
    }

    return undefined;
  }, []);

  return (
    <Grid container alignItems="stretch">
      <Table
        rows={data}
        columns={columns.map((c) => ({
          sortable: false,
          filterable: false,
          editable: false,
          hideSortIcons: true,
          disableColumnMenu: true,
          ...c,
        }))}
        // These heights are similar to a 'density' of 'compact'.
        // But density is multiplied against these, so do not also apply it.
        headerHeight={36}
        // Default to allow 3 rows.
        rowHeight={TableRowHeight_3RowsNoScroll}
        // getRowHeight aims to detect situations where more height is needed.
        getRowHeight={getRowHeight}
        onRowClick={onRowClick}
        autoHeight={true}
        isRowSelectable={() => false}
        pagination
        rowsPerPageOptions={[10, 25, 50, 100]}
        initialState={{
          pagination: {
            pageSize: 25,
          },
          columns: {
            columnVisibilityModel: {
              id: false,
            },
          },
        }}
      />
    </Grid>
  );
};

export default SessionReviewTable;
