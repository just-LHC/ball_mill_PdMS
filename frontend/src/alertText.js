export function sanitizeAlertText(value) {
  return String(value || '').replace(/[\d.]+\s*%\s*Risk/gi, 'uncalibrated model score');
}