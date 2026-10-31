"use client";

import { useEffect, useState } from "react";
import { api, chooseProject, currentProject, type Project } from "@/lib/api";

/** Switches every page to another project (e.g. the INCLUDE simulation project). Hidden while there is only one. */
export default function ProjectSwitcher() {
  const [projects, setProjects] = useState<Project[]>([]);
  const [current, setCurrent] = useState<number | null>(null);
  useEffect(() => {
    Promise.all([api<Project[]>("/api/projects"), currentProject()])
      .then(([ps, p]) => { setProjects(ps); setCurrent(p?.id ?? null); })
      .catch(() => {}); // pages show their own "backend unavailable" error
  }, []);
  if (projects.length < 2 || current == null) return null;
  return (
    <label className="block px-3 pb-3 text-xs text-lavender">
      Project
      <select value={current} className="mt-1 block w-full border border-lavender/40 bg-navy px-2 py-1.5 text-sm text-white"
              onChange={(e) => { chooseProject(Number(e.target.value)); location.reload(); }}>
        {projects.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
      </select>
    </label>
  );
}
