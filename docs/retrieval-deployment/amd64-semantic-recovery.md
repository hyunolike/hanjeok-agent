# Interrupted Linux amd64 verification (2026-10-10)

The existing `hanjeok-semantic-amd64:task8-builder` image built successfully as **linux/amd64**, image ID `sha256:2069dee76d031e22f5b2b59d39d59ea8104919d6a5bba680b7f004d2e231e03c` (2,807,865,599 bytes). Recovery inspected the image and preserved its output; it did not repeat the build or restart the container. This is a builder image, not a release candidate.

| Stage | Evidence and result |
| --- | --- |
| Image build | Output ends with the exact image ID and `DONE`; inspection confirms Linux/amd64. |
| Python architecture | The executed script matches the preserved source byte-for-byte. Its initial `x86_64` assertion precedes the successful pip check and rebuild attempt. The output does not print a Python version. |
| Dependencies | `No broken requirements found.` All 43 wheel sizes and SHA256 hashes match the preserved wheel manifest. |
| Local model weights | The real loader reaches 100/100. This does not establish completed encoding or a validated index. |
| Input index | The builder retains the original Mac index `80dd5ab3b1ac4d73f74742ee880f2c5fdc04b2083079f19d17f07c37b00c95a5`, whose manifest pins torch `2.14.1`; Linux wheels pin `2.14.1+cpu`. |
| New index, health, fixtures and E2E | **Unconfirmed.** No final `/tmp/amd64-build-proof.json` exists in the stopped container. Output contains no final rebuilt-index or fixture result. No amd64 API/Neo4j/Kotlin success is claimed. |
| Recovery cleanup | Only `hanjeok-semantic-amd64-builder-task8` was stopped after preserving output. It is exited, not restarting, with exit 137 after a 20-second stop timeout. This records cleanup, not validation success. The stopped container/image and source files remain preserved. |

The earlier **ARM64** results remain distinct: real HYBRID and VECTOR each passed 35 fixtures / 105 request paths; API 19, builder 13 and JVM 339 tests passed. Those results do not prove amd64 success. Original ARM64 verification JSON snapshots predate this interrupted experiment: `amd64ImageRun=false` and `newPushOrPRCreated=false` describe that earlier snapshot, not this recovery or subsequent Draft PR publication.

Evidence: [recovery summary and original source hashes](amd64-semantic-recovery.json), [image build output](amd64-semantic-image-build.txt), [candidate output](amd64-candidate-execution.txt), [final stdout](amd64-container-stdout.txt), [final stderr](amd64-container-stderr.txt), [executed script](amd64-executed-candidate.py), [wheel manifest](amd64-semantic-wheel-manifest.json). Original logs were copied without modification. Full Docker inspection is retained locally and is not published.

A fresh validated amd64 index and final image/API checks remain prerequisites for a separately approved deployment. Production remains `ea47917` FULL. No operational merge/deploy, IAM or Neo4j ACL change, new credential, paid resource or external corpus upload was performed. The separate Hanjeok backend rollout remains held.
