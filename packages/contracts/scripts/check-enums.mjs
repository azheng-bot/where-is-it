import { readFileSync } from "node:fs";
const types = readFileSync(new URL("../src/api.ts", import.meta.url), "utf8");
const apiModels = readFileSync(new URL("../../../services/api/app/models.py", import.meta.url), "utf8");
for (const state of ["currently_detected", "not_currently_detected", "identity_uncertain"]) {
  if (!types.includes(state) || !apiModels.includes(state)) {
    throw new Error(`State enum mismatch: ${state}`);
  }
}
console.log("Contract state enums are aligned.");
