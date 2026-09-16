import Workspace from "@/components/workspace";
import { getServerLanguage } from "@/lib/server-language";

export default async function Page() {
  return <Workspace initialLanguage={await getServerLanguage()} />;
}
