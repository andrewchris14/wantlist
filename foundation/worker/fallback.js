// Isolated selection contract only. NOT imported by the Phase 3A frontend.
export function chooseSnapshot(live, saved) {
  const valid = data => data?.export_schema === 'wantlist-public-v1-foundation' &&
    Array.isArray(data.records) && typeof data.revision === 'string' &&
    Number.isFinite(Date.parse(data.updated_at));
  if (valid(live)) return { data: live, source: 'live', notice: null };
  if (valid(saved)) return {
    data: saved, source: 'saved',
    notice: `Showing a saved list updated ${saved.updated_at}. Live updates are temporarily unavailable.`,
  };
  return { data: null, source: 'unavailable', notice: 'The list is temporarily unavailable. Please try again.' };
}
