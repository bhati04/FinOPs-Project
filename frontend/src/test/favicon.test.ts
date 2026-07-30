import { existsSync, readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "..",
);

test("declares favicon assets that are present in the public directory", () => {
  const html = readFileSync(resolve(frontendRoot, "index.html"), "utf8");

  for (const asset of [
    "favicon.ico",
    "favicon-32x32.png",
    "apple-touch-icon.png",
  ]) {
    expect(html).toContain(`/${asset}`);
    expect(existsSync(resolve(frontendRoot, "public", asset))).toBe(true);
  }
});
