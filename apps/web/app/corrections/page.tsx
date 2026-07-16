import { CorrectionForm } from "@/components/correction-form";
import { PageIntro, PageShell } from "@/components/site";
export default function CorrectionsPage(){return <PageShell><PageIntro eyebrow="Accountability" title="Flag a source or interpretation for review." copy="Report attribution, date, duplication, copyright, removal, broken-link, or interpretive concerns."/><div className="mx-auto max-w-3xl px-5 py-12"><CorrectionForm/></div></PageShell>}
