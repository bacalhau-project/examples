'use client'
import React, {createContext, ReactNode, useContext} from 'react';
import env from '../public/env.json';

interface EnvVariables {
    GOOGLE_MAPS_API_KEY: string
}

const EnvContext = createContext<EnvVariables | null>(null);

interface EnvProviderProps {
    children: ReactNode;
}

export const EnvProvider = ({children}: EnvProviderProps) => {
    return (
        <EnvContext.Provider value={env as EnvVariables}>
            {children}
        </EnvContext.Provider>
    );
};

export const useEnv = (): EnvVariables => {
    const context = useContext(EnvContext);
    if (!context) {
        throw new Error("useEnv must be used within an EnvProvider");
    }
    return context;
};
