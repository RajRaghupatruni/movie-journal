/** Existing provider algorithms remain in their components for the backend migration.
 * Never reactivate them with VITE_* credentials: everything in that namespace is public.
 */
export const legacyProviderSearchEnabled = false;

export async function legacyProviderRequest(_path: string): Promise<Response> {
  throw new Error('Provider search is temporarily unavailable.');
}
