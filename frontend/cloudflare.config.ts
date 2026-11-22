import { bindings, defineConfig, defineWorker } from "cf/config";

export default defineConfig({
  accountId: "96dc7e6d07c8cb414af597acfec30146",
  worker: defineWorker({
    name: "hanjeok-agent",
    entrypoint: "vinext/server/fetch-handler",
    compatibilityDate: "2026-11-21",
    assets: {
      htmlHandling: "none",
      notFoundHandling: "none",
      runWorkerFirst: ["/*", "!/_next/static/*", "!/*/_next/static/*"],
    },
    env: {
      ASSETS: bindings.assets(),
    },
  }),
});
