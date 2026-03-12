/**
 * Cron expression → Human-readable (English).
 */
export function cronToHuman(expr) {
  if (!expr || typeof expr !== "string") return "";
  const parts = expr.trim().split(/\s+/);
  if (parts.length < 5) return "Invalid expression";
  const [min, hour, dom, mon, dow] = parts;
  const dayNames = { 0: "Sun", 1: "Mon", 2: "Tue", 3: "Wed", 4: "Thu", 5: "Fri", 6: "Sat", 7: "Sun" };
  const monNames = { 1: "Jan", 2: "Feb", 3: "Mar", 4: "Apr", 5: "May", 6: "Jun", 7: "Jul", 8: "Aug", 9: "Sep", 10: "Oct", 11: "Nov", 12: "Dec" };
  let time = "";
  if (hour !== "*" && min !== "*") time = `at ${hour.padStart(2, "0")}:${min.padStart(2, "0")}`;
  else if (hour !== "*") time = `at hour ${hour}`;
  else time = "every minute";
  let days = "";
  if (dow !== "*") {
    const ranges = dow.split(",").map(d => {
      if (d.includes("-")) {
        const [a, b] = d.split("-");
        return `${dayNames[a] || a}–${dayNames[b] || b}`;
      }
      return dayNames[d] || d;
    });
    days = ranges.join(", ");
  }
  let months = "";
  if (mon !== "*") {
    months = mon.split(",").map(m => monNames[m] || m).join(", ");
  }
  let domStr = "";
  if (dom !== "*") domStr = `on the ${dom}${dom === "1" || dom === "21" || dom === "31" ? "st" : dom === "2" || dom === "22" ? "nd" : dom === "3" || dom === "23" ? "rd" : "th"}`;
  let result = time;
  if (days) result += ` (${days})`;
  if (domStr) result += ` ${domStr}`;
  if (months) result += ` in ${months}`;
  return result;
}
