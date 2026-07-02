"use client";

import { use } from "react";
import ProjectDetail from "../detail";

export default function ProjectPage({ params }) {
  const { id } = use(params);
  return <ProjectDetail projectId={id} />;
}
