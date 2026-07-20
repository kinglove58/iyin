import Image from "next/image";
import Link from "next/link";

import { PageShell } from "@/components/site";
import { getTopics } from "@/lib/api";

const pathways = [
  {
    number: "01",
    eyebrow: "Founder experience",
    title: "Learn from the decisions behind the journey.",
    copy: "Explore the choices, setbacks, partnerships and turning points that shaped companies built from Africa for the world.",
    accent: "bg-[#f4b43f]",
  },
  {
    number: "02",
    eyebrow: "Belief & purpose",
    title: "Understand the convictions beneath the work.",
    copy: "Discover how faith, responsibility, ambition and service influence the way Iyin thinks about leadership and prosperity.",
    accent: "bg-[#dfeadf]",
  },
  {
    number: "03",
    eyebrow: "The next generation",
    title: "Turn hard-won lessons into your next move.",
    copy: "Find practical perspectives for young Africans choosing what to build, who to build with and how to keep going.",
    accent: "bg-[#ef7c4d]",
  },
];

const questions = [
  "What should young African founders be building now?",
  "How do you build conviction before the market agrees?",
  "What does faith change about entrepreneurship?",
  "How should founders think about talent and partnerships?",
];

const fallbackThemes = [
  { id: "building", slug: "", name: "Building from Africa" },
  { id: "leadership", slug: "", name: "Leadership & talent" },
  { id: "belief", slug: "", name: "Faith, purpose & service" },
  { id: "capital", slug: "", name: "Capital & conviction" },
  { id: "innovation", slug: "", name: "Innovation that matters" },
  { id: "next-generation", slug: "", name: "The next generation" },
];

export default async function Home() {
  const topics = await getTopics();
  const visibleTopics = topics.length ? topics.slice(0, 8) : fallbackThemes;

  return (
    <PageShell>
      <section className="relative isolate min-h-[760px] overflow-hidden bg-[#0c3929] text-white lg:min-h-[830px]">
        <Image
          src="/images/iyinoluwa-aboyeji.webp"
          alt="Iyinoluwa Aboyeji"
          fill
          priority
          sizes="100vw"
          className="object-cover object-[64%_center] opacity-90 saturate-[.75] lg:object-[center_42%]"
        />
        <div className="absolute inset-0 bg-[linear-gradient(90deg,rgba(7,43,31,.98)_0%,rgba(7,43,31,.94)_38%,rgba(7,43,31,.55)_67%,rgba(7,43,31,.12)_100%)]" />
        <div className="absolute inset-0 bg-[linear-gradient(0deg,rgba(7,43,31,.82)_0%,transparent_38%)] lg:bg-none" />
        <div className="absolute left-[48%] top-0 hidden h-full w-px bg-white/20 lg:block" />

        <div className="relative mx-auto flex min-h-[760px] max-w-[1500px] items-center px-5 py-20 lg:min-h-[830px] lg:px-12 xl:px-20">
          <div className="max-w-[850px]">
            <p className="text-xs font-bold uppercase tracking-[.2em] text-[#f6c663]">
              African Founder Studies
            </p>
            <h1 className="mt-7 text-5xl leading-[.96] text-[#fffaf0] sm:text-6xl md:text-7xl lg:text-[5.7rem] xl:text-[6.6rem]">
              Ideas are easier to understand when the{" "}
              <em className="text-[#f6c663]">evidence stays visible.</em>
            </h1>
            <p className="mt-8 max-w-2xl text-lg leading-8 text-[#d7e6dc] md:text-xl">
              Explore the experiences, convictions and practical lessons shared
              across public conversations—and follow every idea back to its
              original source.
            </p>
            <div className="mt-10 flex flex-wrap gap-3">
              <Link
                href="/ask"
                className="group inline-flex items-center gap-4 rounded-full bg-[#f4b43f] px-7 py-4 font-bold text-[#102d22] no-underline transition hover:-translate-y-0.5 hover:bg-white"
              >
                Ask Iyin&apos;s public ideas
                <span
                  aria-hidden="true"
                  className="grid h-7 w-7 place-items-center rounded-full bg-[#102d22]/10 transition group-hover:translate-x-1"
                >
                  →
                </span>
              </Link>
              <Link
                href="/topics"
                className="inline-flex items-center rounded-full border border-white/50 bg-white/5 px-7 py-4 font-bold text-white no-underline backdrop-blur-sm transition hover:border-white hover:bg-white hover:text-[#102d22]"
              >
                Explore the lessons
              </Link>
            </div>
          </div>
        </div>
      </section>

      <section className="bg-[#f4b43f] text-[#12251c]">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 py-16 lg:grid-cols-[.72fr_1.28fr] lg:px-8 lg:py-24">
          <p className="eyebrow self-start !text-[#12251c]">
            Ideas worth building with
          </p>
          <h2 className="max-w-4xl text-4xl leading-[1.05] md:text-6xl">
            Africa&apos;s future will be shaped by people who move from
            inspiration to disciplined action.
          </h2>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 lg:px-8 lg:py-28">
        <div className="flex flex-wrap items-end justify-between gap-6">
          <div className="max-w-3xl">
            <p className="eyebrow">What you can explore</p>
            <h2 className="mt-4 text-4xl leading-tight md:text-6xl">
              Lessons for people building the next Africa.
            </h2>
          </div>
          <p className="max-w-sm text-base leading-7 text-[var(--muted)]">
            Not a highlight reel. A clearer view of the thinking, trade-offs and
            principles behind the work.
          </p>
        </div>

        <div className="mt-14 grid gap-5 lg:grid-cols-3">
          {pathways.map((item) => (
            <article
              key={item.number}
              className={`${item.accent} group flex min-h-[430px] flex-col rounded-[2rem] p-7 transition duration-300 hover:-translate-y-2 md:p-9`}
            >
              <div className="flex items-center justify-between">
                <span className="serif text-3xl">{item.number}</span>
                <span className="grid h-12 w-12 place-items-center rounded-full border border-current text-xl transition group-hover:rotate-45">
                  ↗
                </span>
              </div>
              <div className="mt-auto">
                <p className="text-xs font-bold uppercase tracking-[.18em]">
                  {item.eyebrow}
                </p>
                <h3 className="mt-4 text-3xl leading-tight">{item.title}</h3>
                <p className="mt-5 leading-7 text-[#32453b]">{item.copy}</p>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="overflow-hidden bg-[var(--forest)] text-white">
        <div className="mx-auto grid max-w-7xl gap-14 px-5 py-20 lg:grid-cols-[.9fr_1.1fr] lg:px-8 lg:py-28">
          <div>
            <p className="text-xs font-bold uppercase tracking-[.18em] text-[#f6c663]">
              Ask better questions
            </p>
            <h2 className="mt-5 max-w-xl text-4xl leading-tight md:text-6xl">
              Go beyond biography. Explore how a builder thinks.
            </h2>
            <p className="mt-6 max-w-xl text-lg leading-8 text-[#cadbd1]">
              Ask about building, leadership, faith, talent, capital or
              Africa&apos;s future. The answer is drawn from his publicly shared
              words and includes links you can open for yourself.
            </p>
            <Link
              href="/ask"
              className="mt-9 inline-flex rounded-full bg-[#f4b43f] px-7 py-4 font-bold text-[#12251c] no-underline transition hover:bg-white"
            >
              Start a conversation →
            </Link>
          </div>
          <div className="grid content-center gap-3">
            {questions.map((question, index) => (
              <Link
                key={question}
                href={`/ask?q=${encodeURIComponent(question)}`}
                className="group flex items-center justify-between gap-5 rounded-2xl border border-white/15 bg-white/[.06] px-5 py-5 text-lg text-white no-underline transition hover:border-[#f6c663] hover:bg-white/[.1] md:px-7 md:py-6 md:text-xl"
              >
                <span>
                  <span className="mr-4 text-sm text-[#f6c663]">
                    0{index + 1}
                  </span>
                  {question}
                </span>
                <span className="transition group-hover:translate-x-1">→</span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 lg:px-8 lg:py-28">
        <div className="grid gap-10 lg:grid-cols-[.55fr_1.45fr]">
          <div>
            <p className="eyebrow">Follow your curiosity</p>
            <h2 className="mt-4 text-4xl leading-tight">
              Explore the ideas shaping the collection.
            </h2>
          </div>
          <div className="grid gap-px overflow-hidden rounded-[2rem] border border-[var(--line)] bg-[var(--line)] sm:grid-cols-2">
            {visibleTopics.map((topic, index) => (
              <Link
                key={topic.id}
                href={topic.slug ? `/topics/${topic.slug}` : "/topics"}
                className="group min-h-44 bg-[var(--card)] p-6 no-underline transition hover:bg-[#f4b43f] md:p-8"
              >
                <span className="text-xs font-bold text-[var(--ochre)]">
                  0{index + 1}
                </span>
                <h3 className="mt-8 text-2xl leading-tight">{topic.name}</h3>
                <span className="mt-5 inline-block text-sm font-bold text-[var(--forest)] transition group-hover:translate-x-1">
                  Explore →
                </span>
              </Link>
            ))}
          </div>
        </div>
      </section>

      <section className="px-5 pb-8 lg:px-8">
        <div className="mx-auto max-w-7xl overflow-hidden rounded-[2rem] bg-[#ef7c4d] px-6 py-14 md:px-12 md:py-20">
          <div className="flex flex-wrap items-end justify-between gap-8">
            <div className="max-w-3xl">
              <p className="text-xs font-bold uppercase tracking-[.18em]">
                For Africa&apos;s next generation
              </p>
              <h2 className="mt-4 text-4xl leading-tight md:text-6xl">
                Let experience shorten the distance between your idea and your
                action.
              </h2>
            </div>
            <Link
              href="/ask"
              className="rounded-full bg-[#12251c] px-7 py-4 font-bold text-white no-underline transition hover:bg-white hover:text-[#12251c]"
            >
              Ask your question →
            </Link>
          </div>
        </div>
      </section>
    </PageShell>
  );
}
