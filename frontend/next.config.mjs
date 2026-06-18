/** @type {import('next').NextConfig} */
const nextConfig = {
  // Emit a self-contained server build for Docker/any-host deploys.
  output: "standalone",
};

export default nextConfig;
