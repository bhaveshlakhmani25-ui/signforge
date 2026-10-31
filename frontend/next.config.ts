import type { NextConfig } from "next";

// GitHub Pages serves static files under /<repo>/, so that build is a static export with a base path.
const pages = process.env.GITHUB_PAGES === "true";
const basePath = pages ? "/signforge" : "";

const nextConfig: NextConfig = {
  ...(pages && { output: "export", basePath, trailingSlash: true }),
  env: { NEXT_PUBLIC_BASE_PATH: basePath },
  cacheComponents: !pages, // PPR cannot be combined with static export
  partialPrefetching: !pages,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
