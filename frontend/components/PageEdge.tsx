"use client";

import { usePathname } from "next/navigation";
import { useEffect } from "react";

/** The story page at / is black edge to edge (overscroll, below the footer). Next keeps the previous route mounted but
 *  hidden after a client navigation, so this follows the address instead of whether the landing page exists in the DOM. */
export default function PageEdge() {
  const path = usePathname();
  useEffect(() => {
    document.documentElement.classList.toggle("landing-edge", path === "/");
  }, [path]);
  return null;
}
