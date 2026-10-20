import fs from "node:fs";

// Defensive licensing hygiene (historical WFO-2). Shipped Schedule UI is a custom
// CSS grid — these strings must not appear even as transitive deps.
const files = ["package.json", "pnpm-lock.yaml"];
const banned = [
  "@" + "fullcalendar/",
  "fullcalendar-" + "scheduler",
  "fullcalendar-" + "resource",
];
const hay = files.map((file) => fs.readFileSync(file, "utf8")).join("\n");

for (const needle of banned) {
  if (hay.includes(needle)) {
    console.error(`Forbidden dependency reference: ${needle}`);
    process.exit(1);
  }
}

console.log("OK: no banned premium calendar package strings in frontend lockfile");
