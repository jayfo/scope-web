import axios, { AxiosInstance, AxiosRequestConfig, AxiosResponse } from 'axios';
import { handleDates } from 'shared/time';
import { KeyedMap } from 'shared/types';

export interface IServiceBase {
    applyAuth(authToken: string): void;
}

export class ServiceBase implements IServiceBase {
    protected readonly axiosInstance: AxiosInstance;
    private authRequestInterceptor: number | undefined;
    private revIds: KeyedMap<string> = {};

    constructor(baseUrl: string) {
        this.axiosInstance = axios.create({
            baseURL: baseUrl,
            timeout: 15000,
        });

        const handleDocuments = (body: any) => {
            if (body === null || body === undefined || typeof body !== 'object') {
                return body;
            }

            if (!!body._id && !!body._rev) {
                this.revIds[body._id] = body._rev;
            }

            for (const key of Object.keys(body)) {
                const value = body[key];
                if (typeof value === 'object') {
                    handleDocuments(value);
                }
            }
        };

        const handleResponse = (response: AxiosResponse) => {
            handleDates(response.data);
            handleDocuments(response.data);

            return response;
        };

        const handleRequest = (request: AxiosRequestConfig) => {
            if (request.method?.toLowerCase() === 'put' && request.data && request.data._id) {
                request.data._rev = this.revIds[request.data._id];
                delete request.data._id;
            }
            return request;
        };

        this.axiosInstance.interceptors.response.use(handleResponse);

        this.axiosInstance.interceptors.request.use(handleRequest);
    }

    public applyAuth(authToken: string) {
        if (this.authRequestInterceptor) {
            this.axiosInstance.interceptors.request.eject(this.authRequestInterceptor);
        }

        this.authRequestInterceptor = this.axiosInstance.interceptors.request.use(async (config) => {
            const bearer = `Bearer ${authToken}`;
            if (!!config.headers) {
                config.headers.Authorization = bearer;
            }

            return config;
        });
    }
}
