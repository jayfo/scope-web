import { List, ListItem, ListItemIcon, ListItemText, ListSubheader } from '@material-ui/core';
import InsertDriveFileIcon from '@material-ui/icons/InsertDriveFile';
import { action } from 'mobx';
import { observer } from 'mobx-react';
import React, { FunctionComponent } from 'react';
import { useHistory } from 'react-router';
import { Link } from 'react-router-dom';
import { DetailPage } from 'src/components/common/DetailPage';
import { getResourceLink } from 'src/services/routes';
import { getString } from 'src/services/strings';
import { useStores } from 'src/stores/stores';

export const ResourcesHome: FunctionComponent = observer(() => {
    const rootStore = useStores();
    const { resources } = rootStore.appConfig;
    const history = useHistory();

    const handleGoBack = action(() => {
        history.goBack();
    });

    return (
        <DetailPage title={getString('Resources_title')} onBack={handleGoBack}>
            {resources.map((r) => (
                <List
                    key={r.name}
                    component="nav"
                    aria-labelledby="nested-list-subheader"
                    subheader={
                        <ListSubheader component="div" id="nested-list-subheader">
                            {r.name}
                        </ListSubheader>
                    }>
                    {r.resources.map((resource) => (
                        <ListItem button component={Link} to={getResourceLink(resource.filename)} target="_blank">
                            <ListItemIcon>
                                <InsertDriveFileIcon />
                            </ListItemIcon>
                            <ListItemText primary={resource.name} />
                        </ListItem>
                    ))}
                </List>
            ))}
        </DetailPage>
    );
});

export default ResourcesHome;
