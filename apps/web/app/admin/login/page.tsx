import Link from "next/link";
import { LoginForm } from "@/components/admin";
import { Notice } from "@/components/site";
export default function AdminLogin(){return <main className="grid min-h-screen place-items-center bg-[#eeeae0] px-5 py-12"><div className="w-full max-w-md rounded-2xl border border-[var(--line)] bg-[var(--card)] p-7 shadow-xl"><Link href="/" className="eyebrow no-underline">← Public library</Link><h1 className="mt-5 text-4xl">Research administrator</h1><p className="mt-3 text-sm leading-6 text-[var(--muted)]">Review candidates, control ingestion, inspect evidence, and audit system quality.</p><div className="my-6"><Notice compact/></div><LoginForm/></div></main>}
