import { getTopics } from "@/lib/api";
import { EmptyState, PageIntro, PageShell } from "@/components/site";

export default async function TopicPage({params}:{params:Promise<{slug:string}>}) { const {slug}=await params; const topic=(await getTopics()).find(item=>item.slug===slug); return <PageShell><PageIntro eyebrow="Research topic" title={topic?.name ?? "Topic not found"} copy={topic?.description ?? "This topic is not in the current taxonomy."}/><div className="mx-auto max-w-7xl px-5 py-12 lg:px-8"><EmptyState title="No approved evidence is linked yet" copy="Sources appear here after approval, ingestion, topic classification, and human review. The interface does not generate a theme overview without evidence."/></div></PageShell>; }
