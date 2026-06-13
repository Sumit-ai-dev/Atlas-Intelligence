"use client";
import React, { createContext, useContext, useState, useCallback } from "react";

interface GovernanceCtxType {
  version: number;
  bump: () => void;
}

const GovernanceCtx = createContext<GovernanceCtxType>({ version: 0, bump: () => {} });

export function GovernanceEventsProvider({ children }: { children: React.ReactNode }) {
  const [version, setVersion] = useState(0);
  const bump = useCallback(() => setVersion((v) => v + 1), []);
  return React.createElement(GovernanceCtx.Provider, { value: { version, bump } }, children);
}

export const useGovernanceEvents = () => useContext(GovernanceCtx);
