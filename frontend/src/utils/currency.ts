/**
 * currency.ts — Enterprise Indian Rupee (INR) & Indian Numbering Formatter for LAWGIC.
 *
 * Formats numbers according to the official Indian numbering system:
 *   1000000 -> ₹10,00,000
 *   92500   -> ₹92,500
 *   160000  -> ₹1,60,000
 *   -5000   -> -₹5,000
 */

export function formatINR(val: number | undefined | null, includeDecimals: boolean = false): string {
  if (val === undefined || val === null || isNaN(val)) return '₹0';
  const isNegative = val < 0;
  const absVal = Math.abs(val);
  const formatted = new Intl.NumberFormat('en-IN', {
    minimumFractionDigits: includeDecimals ? 2 : 0,
    maximumFractionDigits: includeDecimals ? 2 : 0,
  }).format(absVal);
  return `${isNegative ? '-' : ''}₹${formatted}`;
}

export function formatINRImpact(val: number | undefined | null): string {
  if (val === undefined || val === null || isNaN(val) || Math.round(val) === 0) return '₹0';
  const isPositive = val > 0;
  const absVal = Math.abs(val);
  const formatted = new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: 0,
  }).format(absVal);
  return `${isPositive ? '+' : '-'}₹${formatted}`;
}

export function formatIndianNumber(val: number | undefined | null): string {
  if (val === undefined || val === null || isNaN(val)) return '0';
  return new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: 2,
  }).format(val);
}
