export function resolveMemoryArtwork({ mediaUrl, posterUrl, backdropUrl, fallback }: { mediaUrl?: string | null; posterUrl?: string | null; backdropUrl?: string | null; fallback: string }) {
  return {
    image: mediaUrl || backdropUrl || posterUrl || fallback,
    posterImage: mediaUrl || posterUrl || backdropUrl || fallback,
    backdropImage: mediaUrl || backdropUrl || posterUrl || fallback,
  }
}
