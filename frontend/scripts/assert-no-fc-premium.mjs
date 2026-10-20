import fs from "node:fs";

const files = ["package.json", "pnpm-lock.yaml"];
const banned = ["@" + "fullcalendar/resource", "fullcalendar-" + "scheduler"];
const hay = files.map((file) => fs.readFileSync(file, "utf8")).join("\n");

for (const needle of banned) {
  if (hay.includes(needle)) {
    console.error(`Forbidden dependency reference: ${needle}`);
    process.exit(1);
  }
}

console.log("OK: no FullCalendar Premium");
