import { AskForm } from "@/components/ask-form";
import { Notice, PageIntro, PageShell } from "@/components/site";

export const metadata = { title: "Ask the collection" };
export default function AskPage() { return <PageShell><PageIntro eyebrow="Evidence-grounded assistant" title="Ask the public record, not a simulated person." copy="Questions are answered exclusively from approved evidence, with exact source cards and cautious language."/><div className="mx-auto max-w-7xl px-5 py-12 lg:px-8"><Notice compact/><div className="mt-8"><AskForm/></div></div></PageShell>; }
