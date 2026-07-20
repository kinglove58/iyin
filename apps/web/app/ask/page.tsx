import { AskForm } from "@/components/ask-form";
import { Header } from "@/components/site";

export const metadata = { title: "Ask the collection" };
export default async function AskPage({
  searchParams,
}: {
  searchParams: Promise<{ q?: string }>;
}) {
  const { q = "" } = await searchParams;
  return <><Header/><main><AskForm initialQuestion={q}/></main></>;
}
