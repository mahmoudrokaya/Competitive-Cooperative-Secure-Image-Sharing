# Reproducibility Guide

**Project:** Competitive–Cooperative Organizational Intelligence for Adaptive Secure Image Sharing over Heterogeneous Multipath Networks  
**Repository:** `Competitive-Cooperative-Secure-Image-Sharing`  
**Release:** Intended for the first archived research release (`v1.0.0`)

## 1. Scope and status

This document describes how to verify the experimental evidence reported in the associated manuscript. The study evaluates secure image-protection methods, packet recovery, competitive–cooperative task coordination, joint adaptive optimization, security constraints, and statistical robustness in controlled heterogeneous multipath simulations.

**Reproducibility status:** The published manuscript's experiment descriptions and results inform this guide. The repository's executable scripts, archive contents, file paths, dependency versions, and entry points have **not yet been audited**. Accordingly, this document does not invent commands or claim that an end-to-end rerun has been verified. Complete the items marked **TO VERIFY** against the actual repository before labeling the release fully reproducible.

A GitHub release and its Zenodo DOI identify a fixed archive; they do not independently verify reproducibility.

## 2. Required research materials

A complete reproducibility package should include:

1. The exact implementation used to produce each reported experiment.
2. Machine-readable configuration files and random seeds.
3. Dataset manifests identifying image sources, subsets, and preprocessing.
4. Instructions for obtaining externally hosted datasets, with license information.
5. Raw per-run results and, where applicable, logs of failures and constraint checks.
6. Analysis scripts that generate the paper's tables, figures, confidence intervals, and adjusted p-values.
7. Dependency versions and a record of the execution environment.
8. Checksums for important input files and archived outputs.

**TO VERIFY:** Which of these artifacts are present in `main`, which are stored in `.rar` archives, and which exist only on other GitHub branches. A release archive includes the tagged commit's tree; it does not automatically merge all branches.

## 3. Computing environment

The manuscript reports a Windows-based Python experimental environment. The hardware description is:

| Component | Reported environment |
|---|---|
| Operating system | 64-bit Windows |
| CPU | Intel Core Ultra 7 265KF |
| RAM | 32 GB |
| Installed GPU | NVIDIA GeForce RTX 5070 (12 GB) |
| Programming language | Python |

The installed GPU does **not** imply that the reported simulations used GPU acceleration.

**TO VERIFY:** Exact Windows build, Python version, package versions, CPU/GPU utilization, parallel-worker settings, and whether timing measurements include initialization or scheduling overhead. Hardware-dependent timing results should not be expected to match exactly on different systems.

### 3.1 Environment setup

From a clean checkout of the tagged release, create an isolated Python environment:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The current `requirements.txt` is **provisional**: it lists `Pillow` and `cryptography` based on manuscript-described components. It is not yet a verified, exhaustive dependency lockfile. Do not interpret a successful installation as proof that all experiment scripts can execute.

Before release, generate an import inventory from the actual scripts, resolve all dependencies, and record exact tested versions in a lockfile or environment manifest.

## 4. Image datasets and provenance

### 4.1 BSDS500

The experiments use images from the Berkeley Segmentation Dataset and Benchmark (BSDS500). The principal large-scale evaluation reports **200 images** and **201,600 transmission jobs**.

**Important:** These 200 images overlap with an earlier BSDS500 evaluation. They must **not** be described as an independent image holdout.

### 4.2 USC-SIPI

The external image-source evaluation uses **39 USC-SIPI images**, producing **39,312 transmission jobs**. This provides a separate image source, not validation over arbitrary image distributions or physical networks.

### 4.3 Dataset preparation checklist

For each experiment, preserve:

- Dataset name, provider, and retrieval date.
- Exact image identifiers and source partitions.
- File hashes, original dimensions, and color mode.
- Any resizing, conversion, binarization, or normalization.
- Image-to-job mapping and repetitions.
- Sampling seeds and split definitions, if applicable.

**TO VERIFY:** Dataset download locations, manifests, image hashes, and preprocessing commands. Do not redistribute third-party images without confirming the applicable terms.

## 5. Network and transport settings

The manuscript describes three heterogeneous paths and the following nominal settings:

| Parameter | Reported value |
|---|---|
| Path bandwidths | 20, 10, and 15 Mb/s |
| Path propagation delays | 10, 40, and 25 ms |
| Packet payload | 1,000 bytes |
| Packet header | 20 bytes |
| Evaluated packet-loss probabilities | 0%, 1%, 5%, 10%, and 20% |
| Burst-loss persistence | 0.85 |
| Path-failure scenario | Path 1 unavailable |
| FEC | One XOR parity packet per four data packets |
| ARQ | Up to three retransmissions |

Transport policies include no recovery, FEC, ARQ, and combined FEC+ARQ. Packet recovery must be distinguished from image reconstruction: successful packet delivery does not necessarily imply sufficient valid protected fragments for reconstruction.

**TO VERIFY:** Per-experiment overrides, random-loss generation, burst-model initialization, timeout rules, retry accounting, and exact event timing. The nominal settings above must not be assumed to apply unchanged to every experimental condition.

## 6. Protection methods

The study evaluates the following mechanisms:

1. XOR secret sharing (2,2).
2. OR visual cryptography (2,2).
3. Random-grid OR visual cryptography (2,2).
4. Shamir secret sharing over GF(256) (2,3).
5. AES-128-GCM with a preshared key.
6. X25519/HKDF with AES-128-GCM.
7. AES-GCM with XOR erasure coding (2,3).

**Measurement rule:** Record exact reconstruction separately from visual reconstruction or contrast-based quality. Erasure coding of authenticated ciphertext is not equivalent to threshold secret sharing.

**TO VERIFY:** Parameterization, key handling, nonce generation, reconstruction predicates, fragment accounting, and deterministic test vectors. Never publish real secrets or private keys in a reproducibility package.

## 7. Organizational and optimization configurations

The organizational evaluation compares static assignment, competitive bidding, protected ownership, cooperative assistance, failure-triggered reassignment, and full coordination. Operational checks include ownership, reservations, agent/path capacity, authorization, and cumulative fragment exposure.

The joint-adaptation comparison uses:

| Label | Strategy |
|---|---|
| J1 | Static configuration |
| J2 | Recovery adaptation |
| J3 | Organizational adaptation |
| J4 | Protection adaptation |
| J5 | Recovery and organizational adaptation |
| J6 | Joint adaptation |

For each strategy, preserve the candidate set, objective definition and weights, constraint checks, optimizer budget, tie-breaking rules, random seeds, and planning-time measurement procedure.

**TO VERIFY:** Actual configuration filenames and execution entry points. Do not infer that a strategy's label corresponds to a standalone script.

## 8. Execution sequence

Execute experiments in an order that permits component validation before integrated evaluation:

1. **Environment validation:** Check imports, versions, test images, and required files.
2. **Protection validation:** Confirm reconstruction behavior and fragment accounting.
3. **Transport validation:** Compare no recovery, FEC, ARQ, and FEC+ARQ.
4. **Organizational ablations:** Compare bidding, ownership, assistance, reassignment, and full coordination.
5. **Joint adaptation:** Evaluate J1–J6 under matched conditions.
6. **Security checks:** Run targeted negative tests and runtime constraint monitors.
7. **Dataset replication:** Run the BSDS500 and USC-SIPI evaluations using their specified manifests.
8. **Statistical analysis:** Recreate paired contrasts, confidence intervals, multiplicity adjustments, and sensitivity results.
9. **Paper-output regeneration:** Rebuild the tables and figures from the archived result records.

**No executable shell commands for these experiment stages are supplied here**, because the implementation's actual entry points have not been verified. Before publishing the release, add the real commands, working directories, expected output paths, and approximate runtime for every stage.

## 9. Reference results and acceptance checks

The following figures are reported in the manuscript and provide reference values for checking a rerun. Differences due to randomness, platform, or implementation changes must be investigated and documented rather than silently rounded away.

### 9.1 Packet-recovery comparison

| Recovery policy | Reported success |
|---|---:|
| No recovery | 24.29% |
| FEC | 37.62% |
| ARQ | 91.90% |
| FEC + ARQ | 97.14% |

These percentages belong to the reported packet-recovery comparison; do not pool them with other experimental populations.

### 9.2 Assistance under 20% packet loss

| Condition | Static completion | Assistance completion | Difference |
|---|---:|---:|---:|
| Independent loss | 92.06% | 98.85% | +6.79 percentage points |
| Burst loss | 90.85% | 98.44% | +7.59 percentage points |

Each comparison uses **4,800 jobs per condition**; the improvements correspond to **326** and **364** additional completed jobs, respectively.

### 9.3 Joint adaptation (672 jobs per strategy)

| Metric | J4: Protection adaptation | J6: Joint adaptation |
|---|---:|---:|
| Completed jobs | 644/672 | 671/672 |
| Completion | 95.83% | 99.85% |
| Mean objective | 0.2515 | 0.2114 |
| Mean wire ratio | 1.3482 | 1.2613 |
| Mean censored execution time | 395.53 ms | 276.41 ms |
| Median planning time | 19.08 ms | 139.43 ms |

J6 improved completion by **4.02 percentage points**, reduced the mean objective by **15.94%**, and reduced mean **censored** execution time by **30.12%** relative to J4. Planning overhead increased. Censored execution time includes unsuccessful and infeasible jobs and is **not** successful-transmission latency.

The static and recovery-only strategies each had **504 infeasible jobs**, which affects interpretation of their low completion rates.

### 9.4 Search-efficiency benchmark

Across **300 matched cases per search strategy**:

| Search strategy | Candidates evaluated per case | Median planning time | Mean objective |
|---|---:|---:|---:|
| Exhaustive | 2,952 | 20.2707 ms | 0.209284 |
| Bounded | 8 | 0.0829 ms | 0.209284 |
| Greedy | 8 | 0.0561 ms | 0.209284 |
| Random | 128 | 0.8451 ms | 0.209284 |
| Static | 1 | 0.0075 ms | 0.714551 |

Equality of observed mean objectives in this finite benchmark does not establish global optimization equivalence.

### 9.5 Image-source evaluations

| Image source | Completed / total jobs | Completion |
|---|---:|---:|
| BSDS500 (200 images) | 198,624 / 201,600 | 98.52% |
| USC-SIPI (39 images) | 38,296 / 39,312 | 97.42% |

### 9.6 Security and organizational checks

- **23/23** targeted security tests passed.
- **110/110** organizational security preflight tests passed.
- The organizational security workload completed **21,266/21,504** jobs (**98.89%**).
- **63,108** batches across **44** constraint conditions had no recorded constraint violations.
- No ownership or resource-capacity violations were recorded in the evaluated workloads.

A rejected unauthorized operation is evidence of enforcement, not an ownership violation. Passing these tests does not prove security against every adversary.

## 10. Statistical reproduction

Reproduce statistical comparisons from **paired per-run observations**, not only aggregated completion percentages. Record:

- The unit of analysis (job, image, batch, or matched case).
- The pairing keys and grouping variables.
- The bootstrap or resampling procedure, seed, and number of replicates.
- Confidence intervals, effect definitions, and directions.
- Testing families and Holm multiplicity adjustments.
- The handling of failed or infeasible executions.

Selected reported paired completion effects for full coordination versus static operation are:

| Dataset | Protection method | Completion effect | 95% confidence interval |
|---|---|---:|---|
| BSDS500 | AES128-GCM-PSK | +4.95 pp | [+4.64, +5.27] pp |
| BSDS500 | AESGCM-XOR-Erasure-2/3 | +0.51 pp | [+0.40, +0.63] pp |
| USC-SIPI | AES128-GCM-PSK | +6.84 pp | [+5.40, +8.39] pp |
| USC-SIPI | AESGCM-XOR-Erasure-2/3 | +1.56 pp | [+0.89, +2.38] pp |

The USC-SIPI erasure-method wire-ratio contrast was **not significant after Holm correction** (reported adjusted *p* = 0.1703). Do not infer adjusted significance from an unadjusted confidence interval alone.

## 11. Output provenance and verification

For each reported result, retain a traceable chain:

`input manifest → configuration → run log → per-job records → aggregate summary → statistical output → manuscript table/figure`

Recommended minimum columns for per-job records include: experiment ID, dataset, image ID, seed, protection method, transport policy, coordination strategy, network condition, completion status, infeasibility reason, wire bytes/ratio, censored execution time, planning time, and any security/constraint event indicators.

These are **recommended schema fields**, not a claim that existing files already contain them. Keep original result formats and document transformations instead of modifying historical data to fit this suggested schema.

Before release, verify that the published tables and figures can be regenerated from the archived records and note any figures assembled manually.

## 12. Known limits on reproducibility and generalization

- The reported network is simulated, not a physical multipath deployment.
- Timing measurements may be hardware- and implementation-dependent.
- The 200-image BSDS500 evaluation overlaps with an earlier BSDS500 evaluation.
- USC-SIPI provides an additional image source but not universal generalization.
- Assistance and reassignment do not always provide additive gains.
- The joint strategy incurs additional planning cost.
- Security tests establish tested constraint enforcement, not a formal adversarial guarantee.
- Candidate-search conclusions apply to the evaluated finite search space.

## 13. Release checklist

Before tagging `v1.0.0`, confirm:

- [ ] All intended experiment scripts and outputs are present in the tagged `main` commit.
- [ ] Archive contents have been inspected; no required experiment exists only on another branch.
- [ ] `requirements.txt` has been validated against imports and tested versions are recorded.
- [ ] Dataset manifests, licenses, and download instructions are complete.
- [ ] Exact per-experiment commands and expected output paths are documented.
- [ ] Random seeds and simulation configurations are preserved.
- [ ] Raw results and analysis scripts regenerate reported metrics.
- [ ] Statistical code reproduces pairing, confidence intervals, and adjusted tests.
- [ ] Security test inputs and expected rejections are documented without exposing secrets.
- [ ] A clean-environment smoke test has passed.
- [ ] `README.md`, `CITATION.cff`, and `LICENSE` match the released contents.
- [ ] Third-party datasets and source-code licensing are handled separately where required.
- [ ] The GitHub release is published and its Zenodo archive is checked.

## 14. Citation and contact

Please cite the associated research article and the **version-specific Zenodo DOI** for the exact repository release used. Author details, article DOI, and repository DOI should be entered in `CITATION.cff` once verified.

For questions about reproduction, open a GitHub issue describing the release tag, operating environment, command executed, and relevant non-sensitive logs.
