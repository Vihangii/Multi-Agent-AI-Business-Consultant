import type { Metadata } from "next";
import { ConsultantApp } from "@/components/ConsultantApp";

export const metadata: Metadata = { title: "Workspace" };

export default function WorkspacePage() {
  return <ConsultantApp />;
}
