export function getBackendBaseUrl(backendUrl) {
  const pageUrl = new URL(window.location.href);
  let backendOrigin;

  if (backendUrl) {
    const normalizedUrl = /^[a-z]+:\/\//i.test(backendUrl)
      ? backendUrl
      : `${pageUrl.protocol}//${backendUrl}`;
    backendOrigin = new URL(normalizedUrl);
  } else if (import.meta.env.DEV) {
    return pageUrl.origin;
  } else {
    backendOrigin = new URL(pageUrl.origin);
    if (pageUrl.hostname.endsWith('.app.github.dev')) {
      backendOrigin.hostname = pageUrl.hostname.replace(/-\d+\.app\.github\.dev$/, '-8000.app.github.dev');
    } else {
      backendOrigin.port = '8000';
    }
  }

  backendOrigin.protocol = backendOrigin.protocol === 'https:' ? 'https:' : 'http:';
  return backendOrigin.origin;
}

export function getWebSocketBaseUrl(backendUrl) {
  const base = new URL(getBackendBaseUrl(backendUrl));
  base.protocol = base.protocol === 'https:' ? 'wss:' : 'ws:';
  return base.origin;
}