import { Divider, Paper, Typography, withTheme } from '@material-ui/core';
import { action } from 'mobx';
import { observer } from 'mobx-react';
import React, { FunctionComponent } from 'react';
import { ContentsMenu, IContentItem } from 'src/components/common/ContentsMenu';
import BAInformation from 'src/components/PatientDetail/BAInformation';
import PatientInformation from 'src/components/PatientDetail/PatientInformation';
import ProgressInformation from 'src/components/PatientDetail/ProgressInformation';
import { useStores } from 'src/stores/stores';
import { sortAssessment } from 'src/utils/assessment';
import styled from 'styled-components';

const DetailPageContainer = withTheme(
    styled.div({
        display: 'flex',
        flexDirection: 'row',
        alignItems: 'stretch',
        height: '100%',
        overflow: 'hidden',
    })
);

const LeftPaneContainer = withTheme(
    styled(Paper)({
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'stretch',
        height: '100%',
        overflow: 'hidden',
    })
);

const PatientCard = withTheme(
    styled.div((props) => ({
        padding: props.theme.spacing(2.5),
    }))
);

const ContentContainer = withTheme(
    styled.div((props) => ({
        flex: 1,
        padding: props.theme.spacing(3),
        overflowX: 'hidden',
        overflowY: 'auto',
    }))
);

const Section = withTheme(
    styled.div((props) => ({
        marginBottom: props.theme.spacing(5),
        minHeight: 600,
    }))
);

const SectionTitle = styled(Typography)({
    minHeight: 48,
    textTransform: 'uppercase',
});

type IContent = IContentItem & { content?: React.ReactNode };

export const PatientDetailPage: FunctionComponent = observer(() => {
    const rootStore = useStores();
    const { currentPatient } = rootStore;

    React.useEffect(
        action(() => {
            rootStore.currentPatient?.getPatientData();
        }),
        []
    );

    const contentMenu: IContent[] = [];

    const patientInfoMenu = [
        {
            hash: 'patient',
            label: 'Patient',
            top: true,
            content: <PatientInformation />,
        },
        {
            hash: 'medical',
            label: 'Medical information',
        },
        {
            hash: 'psychiatry',
            label: 'Psychiatry information',
        },
        {
            hash: 'treatment',
            label: 'Treatment information',
        },
        {
            hash: 'sessions',
            label: 'Sessions',
        },
        {
            hash: 'assessments',
            label: 'Assessments',
        },
    ] as IContent[];
    contentMenu.push.apply(contentMenu, patientInfoMenu);

    if (currentPatient?.assessments && currentPatient?.assessments.length > 0) {
        const progressMenu = [
            {
                hash: 'progress',
                label: 'Progress',
                top: true,
                content: <ProgressInformation />,
            },
        ] as IContent[];

        progressMenu.push.apply(
            progressMenu,
            currentPatient?.assessments
                .slice()
                .sort(sortAssessment)
                .map(
                    (a) =>
                        ({
                            hash: a.assessmentType.replace('-', '').replace(' ', '_').toLocaleLowerCase(),
                            label: a.assessmentType,
                        } as IContent)
                )
        );
        contentMenu.push.apply(contentMenu, progressMenu);
    }

    const baMenu = [
        {
            hash: 'behavioral',
            label: 'Behavioral Activation',
            top: true,
            content: <BAInformation />,
        },
        {
            hash: 'checklist',
            label: 'Checklist',
        },
        {
            hash: 'activities',
            label: 'Activities',
        },
    ] as IContent[];
    contentMenu.push.apply(contentMenu, baMenu);

    return (
        <DetailPageContainer>
            <LeftPaneContainer elevation={3} square>
                <PatientCard>
                    <Typography variant="h5">{currentPatient?.name}</Typography>
                    <Typography variant="body1">{`MRN: ${currentPatient?.MRN}`}</Typography>
                </PatientCard>
                <Divider variant="middle" />
                <ContentsMenu contents={contentMenu} contentId="#scroll-content" />
            </LeftPaneContainer>
            <ContentContainer id="scroll-content">
                {contentMenu
                    .filter((c) => c.top)
                    .map((c) => (
                        <Section id={c.hash} key={c.hash}>
                            <SectionTitle variant="h6">{c.label}</SectionTitle>
                            {c.content ? c.content : null}
                        </Section>
                    ))}
            </ContentContainer>
        </DetailPageContainer>
    );
});

export default PatientDetailPage;