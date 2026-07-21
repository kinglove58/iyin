import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";

import { PageShell } from "@/components/site";

export const metadata: Metadata = {
  title: "About Elijah Obafemi",
  description:
    "Meet Elijah Obafemi, the software engineer and AI builder behind African Founder Studies.",
};

export default function AboutPage() {
  return (
    <PageShell>
      <section className="relative isolate min-h-[780px] overflow-hidden bg-[#071b14] text-white lg:min-h-[820px]">
        <Image
          src="/images/obafemi.png"
          alt=""
          fill
          priority
          sizes="100vw"
          className="object-cover object-[center_16%] sm:object-[center_18%]"
        />
        <div className="absolute inset-0 bg-[#071b14]/65 mix-blend-multiply" />
        <div className="absolute inset-0 bg-gradient-to-b from-[#071b14]/85 via-[#071b14]/25 to-[#071b14]/90" />
        <div className="absolute inset-0 bg-gradient-to-r from-[#071b14]/45 via-transparent to-[#071b14]/45" />

        <div className="relative mx-auto flex min-h-[780px] max-w-7xl flex-col items-center px-5 pb-10 pt-24 text-center lg:min-h-[820px] lg:px-8 lg:pb-12 lg:pt-28">
          <p className="text-xs font-bold uppercase tracking-[.26em] text-[#f6c663]">
            The person behind the project
          </p>
          <h1 className="mt-7 max-w-5xl text-5xl leading-[.95] text-white sm:text-6xl md:text-7xl lg:text-[6.5rem]">
            I am Elijah
            <br />
            Obafemi.
          </h1>
          <p className="mt-7 max-w-2xl text-base leading-7 text-white/90 sm:text-lg sm:leading-8 lg:text-xl">
            A software engineer, AI builder and entrepreneur using technology to
            turn difficult problems into useful products for Africa.
          </p>

          <div className="mt-9 flex flex-wrap justify-center gap-3">
            <a
              href="mailto:obafemielijahsunday@gmail.com"
              className="rounded-full bg-[#f4b43f] px-6 py-3.5 font-bold text-[#102d22] no-underline transition hover:bg-white"
            >
              Write to me
            </a>
            <a
              href="https://www.linkedin.com/in/obafemi-techking/"
              target="_blank"
              rel="noreferrer"
              className="rounded-full border border-white/60 bg-[#071b14]/25 px-6 py-3.5 font-bold text-white no-underline backdrop-blur-sm transition hover:bg-white hover:text-[#102d22]"
            >
              Connect on LinkedIn ↗
            </a>
          </div>

          <div className="mt-auto flex w-full items-end justify-between border-t border-white/45 pt-5 text-left">
            <p className="max-w-[12rem] text-[.65rem] font-bold uppercase leading-5 tracking-[.2em] text-[#f6c663] sm:max-w-none sm:text-xs">
              Software Engineer · AI Builder
            </p>
            <p className="max-w-[9rem] text-right text-[.65rem] font-bold uppercase leading-5 tracking-[.2em] text-white/80 sm:max-w-none sm:text-xs">
              Building from Nigeria for Africa
            </p>
          </div>
        </div>
      </section>

      <section className="bg-[#f4b43f] text-[#102d22]">
        <div className="mx-auto grid max-w-7xl gap-10 px-5 py-16 lg:grid-cols-[.6fr_1.4fr] lg:px-8 lg:py-24">
          <p className="text-xs font-bold uppercase tracking-[.2em]">
            Why I built this
          </p>
          <h2 className="text-4xl leading-[1.08] md:text-6xl">
            This project began with a simple desire: to learn from someone whose
            journey made possibility feel closer.
          </h2>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-20 lg:px-8 lg:py-28">
        <div className="grid gap-14 lg:grid-cols-[.72fr_1.28fr]">
          <div>
            <p className="eyebrow">A personal note</p>
          </div>
          <div className="max-w-3xl space-y-7 text-lg leading-9 text-[#39453e]">
            <p>
              I have followed Iyinoluwa Aboyeji&apos;s journey as a builder,
              investor and believer in Africa&apos;s potential. What stayed with
              me was not only the scale of what he helped build, but the courage
              to begin early, think beyond familiar limits and keep directing
              attention toward the next generation.
            </p>
            <p>
              I wanted to understand the thinking behind that journey—not as
              scattered clips and quotes, but as a collection a young builder
              could question, study and return to. That desire became African
              Founder Studies.
            </p>
            <p>
              I built it with code, but also with hope: hope that the lessons
              shared by experienced African founders can travel farther; hope
              that someone at the beginning of their journey can find direction
              here; and, personally, hope that one day I may sit with Iyinoluwa,
              show him what his example inspired me to create, and hear his
              feedback on it.
            </p>
            <p className="serif border-l-4 border-[#ef7c4d] pl-6 text-3xl leading-snug text-[var(--ink)]">
              If this project reaches him, I hope he sees more than a website. I
              hope he sees a young African builder who listened, learned and
              chose to act.
            </p>
          </div>
        </div>
      </section>

      <section className="px-5 py-20 lg:px-8 lg:py-28">
        <div className="mx-auto max-w-7xl overflow-hidden rounded-[2rem] bg-[#102d22] px-6 py-14 text-white md:px-12 md:py-20">
          <div className="grid gap-12 lg:grid-cols-[1.25fr_.75fr] lg:items-end">
            <div>
              <p className="text-xs font-bold uppercase tracking-[.2em] text-[#f6c663]">
                My mission
              </p>
              <h2 className="mt-5 text-4xl leading-tight md:text-6xl">
                To use software and artificial intelligence to build lasting
                value for African businesses and communities.
              </h2>
            </div>
            <div className="grid gap-3">
              <a
                href="tel:+234816079990"
                className="rounded-full border border-white/25 px-5 py-3.5 text-white no-underline transition hover:bg-white hover:text-[#102d22]"
              >
                +234 816 079 990
              </a>
              <a
                href="mailto:obafemielijahsunday@gmail.com"
                className="break-all rounded-full border border-white/25 px-5 py-3.5 text-white no-underline transition hover:bg-white hover:text-[#102d22]"
              >
                obafemielijahsunday@gmail.com
              </a>
              <a
                href="https://www.linkedin.com/in/obafemi-techking/"
                target="_blank"
                rel="noreferrer"
                className="rounded-full bg-[#f4b43f] px-5 py-3.5 font-bold text-[#102d22] no-underline transition hover:bg-white"
              >
                LinkedIn profile ↗
              </a>
            </div>
          </div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-5 py-14 text-center lg:px-8">
        <p className="text-sm leading-7 text-[var(--muted)]">
          Thank you for taking the time to understand the person behind this
          work.
        </p>
        <Link
          href="/ask"
          className="mt-4 inline-block font-bold text-[var(--forest)]"
        >
          Explore what the project can do →
        </Link>
      </section>
    </PageShell>
  );
}
