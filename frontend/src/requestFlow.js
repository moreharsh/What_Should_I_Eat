// Request generation identity helper for overlapping frontend operations.
export function beginFlow(previous, cuisine = '') {
  previous?.controller?.abort();
  return {
    id: (previous?.id || 0) + 1,
    controller: new AbortController(),
    cuisine,
    pending: true,
  };
}

export function isActiveFlow(current, snapshot) {
  return current.id === snapshot.id && !snapshot.controller.signal.aborted;
}
