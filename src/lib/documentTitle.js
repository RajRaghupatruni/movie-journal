export function getDocumentTitle(path, authStatus) {
  if (path === '/privacy') return 'Privacy — Tandem'
  if (authStatus === 'unauthenticated') return 'Login'
  if (authStatus !== 'authenticated') return 'Tandem'
  if (path.startsWith('/memory/')) return 'Memory — Tandem'
  return {
    '/': 'Today — Tandem',
    '/memories': 'Memories — Tandem',
    '/timeline': 'Memories — Tandem',
    '/explore': 'Memories — Tandem',
    '/calendar': 'Calendar — Tandem',
    '/tandem': 'Tandem — Settings',
    '/settings': 'Settings — Tandem',
    '/reactivate': 'Reactivate — Tandem',
  }[path] || 'Tandem'
}
