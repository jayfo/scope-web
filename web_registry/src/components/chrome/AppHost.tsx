import { Box, CircularProgress, Fade, Typography } from '@mui/material';
import { observer } from 'mobx-react';
import {
    default as React,
    Fragment,
    FunctionComponent,
    useEffect,
    useState,
} from 'react';
import Splash from 'src/assets/splash-image.jpg';
import Login from 'src/components/chrome/Login';
import { useServices } from 'src/services/services';
import { IRootStore, RootStore } from 'src/stores/RootStore';
import { StoreProvider } from 'src/stores/stores';
import styled, { withTheme } from 'styled-components';

const RootContainer = styled.div({
    height: '100vh',
    width: '100vw',
    display: 'flex',
    flexDirection: 'row',
    position: 'absolute',
    top: 0,
});

const ImageContainer = withTheme(
    styled.div((props) => ({
        height: '100%',
        [props.theme.breakpoints.down('md')]: {
            width: '100%',
            position: 'absolute',
        },
        [props.theme.breakpoints.up('md')]: {
            width: '50%',
        },
    }))
);

const LoginContainer = withTheme(
    styled.div((props) => ({
        height: '100%',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        [props.theme.breakpoints.down('md')]: {
            width: '100%',
            position: 'absolute',
        },
        [props.theme.breakpoints.up('md')]: {
            width: '50%',
        },
    }))
);

const ProgressContainer = withTheme(
    styled.div((props) => ({
        width: 400,
        minHeight: 200,
        display: 'flex',
        flexDirection: 'column',
        justifyContent: 'center',
        alignItems: 'center',
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        borderRadius: props.theme.spacing(4),
        padding: props.theme.spacing(4),
        [props.theme.breakpoints.down('md')]: {
            padding: props.theme.spacing(8),
        },
    }))
);

const FailureContainer = withTheme(
    styled.div((props) => ({
        width: 400,
        backgroundColor: 'rgba(255, 255, 255, 0.9)',
        borderRadius: props.theme.spacing(4),
        padding: props.theme.spacing(4),
        [props.theme.breakpoints.down('md')]: {
            padding: props.theme.spacing(8),
        },
    }))
);

const SplashImage = styled.img({
    width: '100%',
    height: '100%',
    objectFit: 'cover',
});

export interface IAppHost {
    children: React.ReactNode;
}

export const AppHost: FunctionComponent<IAppHost> = observer((props) => {
    const { children } = props;

    const [store, setStore] = useState<IRootStore>();
    const [failed, setFailed] = useState(false);

    useEffect(() => {
        const { configService } = useServices();

        configService
            .getServerConfig()
            .then((serverConfig) => {
                // Create the RootStore
                const newStore = new RootStore(serverConfig);
                setStore(newStore);
                newStore.load();
            })
            .catch((error) => {
                console.error('Failed to retrieve server configuration', error);
                setFailed(true);
            });
    }, []);

    return (
        <Fragment>
            {store?.authStore.isAuthenticated && (
                <Fragment>
                    <StoreProvider store={store}>{children}</StoreProvider>
                </Fragment>
            )}
            <Fade in={!store?.authStore.isAuthenticated} timeout={500}>
                <RootContainer>
                    <ImageContainer>
                        <SplashImage src={Splash} />
                    </ImageContainer>
                    <LoginContainer>
                        {!!store ? (
                            <StoreProvider store={store}>
                                <Login />
                            </StoreProvider>
                        ) : !failed ? (
                            <ProgressContainer>
                                <CircularProgress />
                                <Box sx={{ height: 40 }} />
                                <Typography>
                                    Connecting to service...
                                </Typography>
                            </ProgressContainer>
                        ) : (
                            <FailureContainer>
                                <Typography variant="h1">Sorry!</Typography>
                                <Typography variant="h5">
                                    The registry is not available at this
                                    moment. Please try again later.
                                </Typography>
                            </FailureContainer>
                        )}
                    </LoginContainer>
                </RootContainer>
            </Fade>
        </Fragment>
    );
});

export default AppHost;