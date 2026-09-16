import { cookies } from "next/headers";
import { isLanguage, languageCookieName, type Language } from "./i18n";

export async function getServerLanguage(): Promise<Language> {
  const value = (await cookies()).get(languageCookieName)?.value ?? null;
  return isLanguage(value) ? value : "zh";
}
