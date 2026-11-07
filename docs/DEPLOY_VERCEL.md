# Hosting the interface on Vercel (static snapshot)

## Short answer: will the API work on Vercel?

**The Python API itself is not deployed. The interface works anyway, because it reads a saved copy of every answer the API gives.** Reasons the live API does not fit Vercel:

- It reads the organizers' data pack (`data/`, 105 MB, a link to a folder outside the repository) and the trained model files, none of which are in Git.
- The what-if simulator is the organizers' `retrofit_sim` package, and the live replay is a separate process that writes files. A serverless function has no persistent disk and a size limit that pandas, pyarrow and scikit-learn together come close to.

Because the API only reads recorded data, every answer for the recorded pumps can be saved once. `make snapshot` calls the real API routes in process and writes each answer to `web/public/snapshot/` (458 small JSON files, about 4 MB). The interface is built with `--mode snapshot` (`web/.env.snapshot`) and then asks for those files instead of `/api/...`. Same code, same answers.

| Works on Vercel | Does not |
|---|---|
| Overview, Alerts, Value, Proof, Retrofit; the data of the nine public pumps (charts, the "watch it happen" replay, data check, technical timeline) | The **live replay** strip (`make live-demo` needs a running process; the strip stays hidden) |
| Every alert's what-if simulation (26 alerts have one; the other answers say "not available", as locally) | New data or a re-run of the model: run `make snapshot` again and redeploy |
| The review log, export and theme (kept in the visitor's browser) | A shared review log between people (it is per browser) |

The snapshot contains **no telemetry of the test pumps** (PUMP-10, 11, 12), and the simulator is not run for them. Their alerts are the ones in the submission. `tests/test_snapshot.py` checks both.

## Data licence

The data are the organizers' synthetic benchmark, "RETROFIT AI 2026 synthetic pump benchmark, Since AI Hackathon 2026", CC BY 4.0. The attribution is in the page footer, `NOTICE` and `manifest.json`. The page says that nothing in it is field evidence.

## Deploy

The project root on Vercel is the `web` folder; `web/vercel.json` sets the install and build commands (`npm run build:snapshot`), the output (`dist`) and security headers. The page uses hash links, so no rewrite rules are needed.

### A. From the terminal

```bash
cd web
npx vercel login
npx vercel link --yes --project watchkeeper
npx vercel deploy --prod
```

### B. From GitHub

In Vercel choose **Add New, Project**, import the repository, set **Root Directory** to `web`, keep the detected Vite settings (they come from `vercel.json`) and deploy. Later pushes redeploy by themselves.

A production URL on the free plan is public to anyone with the link. If it should be private, turn on Vercel Authentication (or password protection) for the project.

## Refresh the snapshot

```bash
make snapshot        # needs the data pack and artifacts/alerts
git add web/public/snapshot && git commit -m "Refresh the static snapshot"
```

## Try it without a server

```bash
cd web && npm run build:snapshot && python3 -m http.server 4173 --directory dist
```

Open `http://localhost:4173`. No API is running there; if the pages show data, the snapshot works.
