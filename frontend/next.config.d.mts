export type GitCommandRunner = (args: string[]) => string;

export function deterministicBuildId(gitRunner?: GitCommandRunner): string;

declare const nextConfig: {
  generateBuildId: () => string;
};

export default nextConfig;
