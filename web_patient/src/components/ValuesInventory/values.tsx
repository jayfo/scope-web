import React from "react";

import EmojiNatureIcon from "@mui/icons-material/EmojiNature";
import HelpIcon from "@mui/icons-material/Help";
import ListAltIcon from "@mui/icons-material/ListAlt";
import PendingActionsIcon from "@mui/icons-material/PendingActions";
import SpaIcon from "@mui/icons-material/Spa";
import SupervisorAccountIcon from "@mui/icons-material/SupervisorAccount";
import WorkIcon from "@mui/icons-material/Work";
import { LifeAreaIdOther } from "shared/enums";
import { getString } from "src/services/strings";

export const getLifeAreaIcon = (lifeAreaId: string) => {
  switch (lifeAreaId) {
    case "relationship":
      return <SupervisorAccountIcon fontSize="large" />;
    case "education":
      return <WorkIcon fontSize="large" />;
    case "recreation":
      return <EmojiNatureIcon fontSize="large" />;
    case "mindbody":
      return <SpaIcon fontSize="large" />;
    case "responsibilities":
      return <ListAltIcon fontSize="large" />;
    case LifeAreaIdOther:
      return <PendingActionsIcon fontSize="large" />;
    default:
      return <HelpIcon fontSize="large" />;
  }
};

export const getValuesCountString = (valueCount: number) => {
  return `${valueCount} ${
    valueCount == 1
      ? getString("values_inventory_value_count_singular")
      : getString("values_inventory_value_count_plural")
  }`;
};

export const getActivitiesCountString = (activityCount: number) => {
  return `${activityCount} ${
    activityCount == 1
      ? getString("values_inventory_activity_count_singular")
      : getString("values_inventory_activity_count_plural")
  }`;
};

export const getActivityDetailText = (
  enjoyment: number | undefined,
  importance: number | undefined,
) => {
  return `${getString("values_inventory_value_activity_enjoyment")}: ${
    enjoyment != undefined ? enjoyment : -1
  } / ${getString("values_inventory_value_activity_importance")}: ${
    importance != undefined ? importance : -1
  }`;
};
