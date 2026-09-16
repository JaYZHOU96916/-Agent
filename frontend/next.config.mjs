/** @type {import('next').NextConfig} */
const config = {
  output: "standalone",
  poweredByHeader: false,
  images: { unoptimized: true },
  experimental: { cpus: 2 },
};
export default config;
