import { AuthenticationDetails, CognitoUser, CognitoUserPool, CognitoUserSession } from 'amazon-cognito-identity-js';
import { action, computed, makeAutoObservable, runInAction } from 'mobx';
import {IAppAuthConfig, IPatientUser} from 'shared/types';
import { PromiseQuery } from 'shared/promiseQuery';
import { useServices } from 'src/services/services';
import { getLogger } from 'shared/logger';
import { getLoadAndLogQuery } from 'shared/stores';

export enum AuthState {
    Initialized,
    NewPasswordRequired,
    Authenticated,
    AuthenticationFailed,
}

export interface IAuthStore {
    isAuthenticated: boolean;
    authState: AuthState;
    authStateDetail?: string;
    authUser?: CognitoUser;

    currentUserIdentity?: IPatientUser;
    login(username: string, password: string): Promise<void>;
    updateTempPassword(newPassword: string): Promise<void>;
    logout(): void;
}

const logger = getLogger('AuthStore');

export class AuthStore implements IAuthStore {
    public authConfig: IAppAuthConfig;

    public authState = AuthState.Initialized;

    // This is only used to keep state for temp password change
    public authUser?: CognitoUser;

    // Promise queries
    private readonly authQuery: PromiseQuery<IPatientUser>;

    private errorDetail = '';

    constructor(authConfig: IAppAuthConfig) {
        this.authConfig = authConfig;

        this.authQuery = new PromiseQuery<IPatientUser>(undefined, 'authQuery');

        makeAutoObservable(this);
    }

    @computed
    public get isAuthenticated() {
        return !!this.currentUserIdentity && !!this.currentUserIdentity.authToken;
    }

    @computed
    public get authStateDetail() {
        return this.authState == AuthState.AuthenticationFailed ? this.errorDetail : undefined;
    }

    @computed
    public get currentUserIdentity() {
        if (this.authState == AuthState.Authenticated) {
            return this.authQuery.value;
        }

        return undefined;
    }

    @action.bound
    public async login(username: string, password: string) {
        // Clear states
        this.authState = AuthState.Initialized;

        const authUser = new CognitoUser({
            Username: username,
            Pool: new CognitoUserPool({
                UserPoolId: this.authConfig.poolid,
                ClientId: this.authConfig.clientid,
            }),
        });

        const authDetails = new AuthenticationDetails({
            Username: username,
            Password: password,
        });

        const promise = new Promise<CognitoUserSession>((resolve, reject) => {
            authUser.authenticateUser(authDetails, {
                onSuccess: action((data) => {
                    logger.event('onLoginSuccess: ', { username });
                    resolve(data);

                    // Once the promise is resolved, set the correct states.
                    runInAction(() => {
                        this.authUser = authUser;
                    });
                }),
                onFailure: action((err) => {
                    logger.error(err, { username });
                    runInAction(() => {
                        this.authUser = undefined;
                        this.errorDetail = err.message;
                        this.authState = AuthState.AuthenticationFailed;
                    });
                    reject(err);
                }),
                newPasswordRequired: action((data: CognitoUser) => {
                    logger.event('newPasswordRequired', { username: data.getUsername() });
                    runInAction(() => {
                        this.authUser = authUser;
                        this.authState = AuthState.NewPasswordRequired;
                    });
                    reject('newPasswordRequired');
                }),
            });
        });

        const loadAndLogQuery = getLoadAndLogQuery(logger);
        await loadAndLogQuery(() => this.getIdentityFromSession(promise), this.authQuery);
    }

    @action.bound
    public async updateTempPassword(password: string) {
        const promise = new Promise<CognitoUserSession>((resolve, reject) => {
            this.authUser?.completeNewPasswordChallenge(
                password,
                {}, // No additional required fields to set/update
                {
                    onSuccess: action((data) => {
                        logger.event('onLoginSuccess', { username: this.authUser?.getUsername() || 'unknown' });
                        resolve(data);
                    }),
                    onFailure: action((err) => {
                        logger.error(err, { username: this.authUser?.getUsername() || 'unknown' });
                        runInAction(() => {
                            this.authUser = undefined;
                            this.errorDetail = err.message;
                            this.authState = AuthState.AuthenticationFailed;
                        });
                        reject(err);
                    }),
                },
            );
        });

        const loadAndLogQuery = getLoadAndLogQuery(logger);
        await loadAndLogQuery(() => this.getIdentityFromSession(promise), this.authQuery);
    }

    @action.bound
    public logout() {
        const { authToken, ...currentUser } = this.currentUserIdentity || { authToken: '' };
        this.authUser?.signOut();
        this.authState = AuthState.Initialized;
        this.authUser = undefined;

        logger.event('UserLoggedOut', { ...currentUser });
    }

    private getIdentityFromSession(promise: Promise<CognitoUserSession>) {
        const identifiedPromise = promise
            .then(async (session) => {
                // Once the promise is resolved, get the identity

                const { identityService } = useServices();
                var idToken = session?.getIdToken()?.getJwtToken();

                const patientIdentity = await identityService.getPatientIdentity(idToken);
                logger.event('UserLoggedIn', { ...patientIdentity });

                runInAction(() => {
                    this.authState = AuthState.Authenticated;
                });

                return {
                    ...patientIdentity,
                    authToken: idToken,
                } as IPatientUser;
            })
            .catch((err) => {
                logger.error(err);
                runInAction(() => {
                    this.authState = AuthState.AuthenticationFailed;
                });
            });

        return identifiedPromise;
    }
}
