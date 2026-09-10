export function resolveMemoryTimezone({ tandemTimezone, userTimezone, browserTimezone }: { tandemTimezone?: string | null; userTimezone?: string | null; browserTimezone?: string | null } = {}): string {
  if (tandemTimezone) return tandemTimezone
  if (userTimezone) return userTimezone
  if (browserTimezone) return browserTimezone
  return 'UTC'
}
