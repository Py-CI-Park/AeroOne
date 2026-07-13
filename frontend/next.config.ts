import { execFileSync } from 'node:child_process';

export type GitCommandRunner = (args: string[]) => string;

const defaultGitCommandRunner: GitCommandRunner = (args) =>
  execFileSync('git', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });

export function deterministicBuildId(
  gitRunner: GitCommandRunner = defaultGitCommandRunner,
): string {
  let inGitWorktree: string;
  try {
    inGitWorktree = gitRunner(['rev-parse', '--is-inside-work-tree']).trim();
  } catch {
    // Offline/package stages may not include git metadata.
    return process.env.AEROONE_BUILD_ID?.trim() || 'offline-v1.13.0';
  }
  if (inGitWorktree !== 'true') throw new Error('git metadata is not a worktree');

  const sha = gitRunner(['rev-parse', 'HEAD']).trim();
  if (!/^[a-f0-9]{40}$/.test(sha)) throw new Error('git HEAD is not an exact SHA');
  const status = gitRunner(['status', '--porcelain']);
  if (status.trim() !== '') throw new Error('git worktree is dirty');
  return sha;
}

const nextConfig = { generateBuildId: () => deterministicBuildId() };

export default nextConfig;
