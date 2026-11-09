import "server-only";

import { cert, getApps, initializeApp, type App } from "firebase-admin/app";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";

type ServiceAccount = {
  project_id: string;
  client_email: string;
  private_key: string;
};

function readServiceAccount(): ServiceAccount {
  const inlineCredentials = process.env.FIREBASE_SERVICE_ACCOUNT_JSON;
  if (inlineCredentials) {
    return JSON.parse(inlineCredentials) as ServiceAccount;
  }

  const configuredPath = process.env.FIREBASE_SERVICE_ACCOUNT_PATH ?? "../backend/service.json";
  return JSON.parse(readFileSync(resolve(process.cwd(), configuredPath), "utf8")) as ServiceAccount;
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
