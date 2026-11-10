import "server-only";

import { cert, getApps, initializeApp, type App } from "firebase-admin/app";

type ServiceAccount = {
  project_id: string;
  client_email: string;
  private_key: string;
};

function readServiceAccount(): ServiceAccount {
  const inlineCredentials = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  if (!inlineCredentials) throw new Error("FIREBASE_SERVICE_ACCOUNT_JSON is not configured");
  return JSON.parse(inlineCredentials) as ServiceAccount;
}

export function getFirebaseAdminApp(): App {
  const existingApp = getApps()[0];
  if (existingApp) return existingApp;

  const serviceAccount = readServiceAccount();
  return initializeApp({
    credential: cert({
      projectId: serviceAccount.project_id,
      clientEmail: serviceAccount.client_email,
      privateKey: serviceAccount.private_key,
    }),
  });
}
