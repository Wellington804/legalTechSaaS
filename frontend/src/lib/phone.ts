function digitsOnly(value: string) {
  return value.replace(/\D/g, "");
}

function formatLocalPhone(digits: string) {
  const value = digits.slice(0, 11);
  if (!value) return "";
  if (value.length <= 2) return `(${value}`;
  const area = `(${value.slice(0, 2)})`;
  const subscriber = value.slice(2);
  const splitAt = value.length === 11 ? 5 : 4;
  return `${area} ${subscriber.length > splitAt ? `${subscriber.slice(0, splitAt)}-${subscriber.slice(splitAt)}` : subscriber}`;
}

export function formatBrazilianPhone(value: string) {
  const trimmed = value.trim();
  let digits = digitsOnly(trimmed);
  if (!digits) return trimmed.startsWith("+") ? "+" : "";

  if (trimmed.startsWith("+")) {
    if (!digits.startsWith("55")) return `+${digits}`;
    if (digits.length <= 2) return `+${digits}`;
    digits = digits.slice(2);
  } else if (digits.startsWith("55") && [12, 13].includes(digits.length)) {
    digits = digits.slice(2);
  } else if (digits.startsWith("0") && [11, 12].includes(digits.length)) {
    digits = digits.slice(1);
  }

  return formatLocalPhone(digits);
}
