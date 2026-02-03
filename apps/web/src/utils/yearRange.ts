export const YEAR_RANGE_MIN = 1970;
export const YEAR_RANGE_MAX = new Date().getFullYear();

export const DEFAULT_YEAR_RANGE: [number, number] = [
  YEAR_RANGE_MIN,
  YEAR_RANGE_MAX,
];

export function getDefaultYearRange(): [number, number] {
  return [YEAR_RANGE_MIN, YEAR_RANGE_MAX];
}
