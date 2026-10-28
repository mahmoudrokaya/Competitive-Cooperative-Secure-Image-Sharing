# Experimental Inventory and Reproduction Map

**Project:** Competitive–Cooperative Organizational Intelligence for Adaptive Secure Image Sharing over Heterogeneous Multipath Networks  
**Repository:** `Competitive-Cooperative-Secure-Image-Sharing`  
**Status:** Manuscript-grounded experiment map. Script paths, archive contents, exact commands, and file checksums have **not** been independently verified.

## 1. Purpose and scope

This document connects the experiments reported in the accompanying manuscript to their research questions, evaluation units, metrics, and reference results. It is intended to guide inspection of the published code and results, not to imply that every experiment is already present in the repository's default branch.

The GitHub screenshot available when this document was prepared showed `Experiment A.rar` on `main` and 11 branches. Files present only on other branches are **not automatically included** in a release archive of `main`. Verify and consolidate the required materials before tagging a release.

## 2. Experiment-to-manuscript map

The manuscript consolidates results by research question rather than by experiment letter. The labels below are used only where identifiable from the manuscript; missing mappings must be confirmed from the original scripts and run logs.

| Experiment / evaluation | Focus | Manuscript location | Verified reported evidence |
|---|---|---|---|
| **A / component-level protection and transport** | Image-protection correctness, reconstruction, communication expansion, and packet recovery | §§3.1–3.2, 4.1; Tables 1, 2, 5 | Protection comparison: 7 methods; 3,696 transmission records. Separate fixed-policy impairment comparison: 924 records. Confirm whether local files call these evaluations “A” before naming scripts. |
| **B1** | BSDS500 organizational coordination comparisons | §4.4; Table 9 | Full-versus-static paired completion differences: AES128-GCM-PSK **+4.95 pp**; AESGCM-XOR-Erasure-2/3 **+0.51 pp**. |
| **B2** | Separate image-source evaluation on USC-SIPI | §4.4; Tables 8–9 | **39 images**, **38,296/39,312** successful jobs (**97.42%**); full-versus-static completion gains **+6.84 pp** (AES-PSK) and **+1.56 pp** (erasure). |
| **C** | Organizational configurations and constrained coordination | §4.2; §4.4 | Static completion **96.99%**; full coordination **99.63%**. |
| **D** | Targeted security and runtime enforcement | §4.4; Table 8 | **23/23** targeted security tests passed; runtime workload of **44 jobs**, with **30 successful jobs** and **28 security rejections** (different event counts; do not sum as disjoint jobs). |
| **E** | Constraint and statistical/sensitivity evaluation | §§4.2, 4.4; Tables 8–9 | **63,108 batches**, **44 conditions**, no recorded constraint violations; intervention-budget sensitivity reported. |
| **F** | **Mapping unverified** | — | Do not invent an experimental purpose, result, or command. Determine from repository files. |
| **G** | Organizational ablation and implementation-based recovery example | §§2.3, 4.2; Fig. 4 | Static **97.25%** versus assistance/reassignment **99.48%** in the reported factorial comparison; example **G12** recovered through assistance. |
| **H** | Organizational security preflight and runtime validation | §4.4; Table 8 | **110/110** preflight tests passed; **21,266/21,504** jobs completed (**98.89%**); no recorded ownership or capacity violations. |
| **I** | Larger BSDS500 organizational evaluation and loss-specific recovery | §§4.2, 4.4; Table 8 | **200 images**, **198,624/201,600** successful jobs (**98.52%**). At 20% independent loss: static **92.06%**, assistance **98.85%**; at 20% burst loss: **90.85%** versus **98.44%**. |
| **J / joint optimization** | Six adaptation strategies and separate search-efficiency benchmark | §4.3; Table 7; Figs. 8–9 | **672 jobs per strategy**; J6 joint adaptation **671/672 (99.85%)**. Search benchmark: **300 matched cases per search strategy**. Confirm local experiment-letter naming from files. |

**Naming caution:** The labels **A** and **J** above indicate likely component-level and joint-optimization groupings based on the paper's structure; their exact local archive names and the contents of Experiment F have not been verified. Do not treat this table as a filesystem inventory.

## 3. Shared experimental design

### 3.1 Image inputs

- **BSDS500:** 8-bit RGB images; the manuscript describes development and evaluation partitions.
- **USC-SIPI:** a separate image source for cross-dataset assessment.
- Preserve source image filename, partition, dimensions, and **SHA-256** digest in a machine-readable manifest.
- Visual-share methods use grayscale conversion with threshold **128**.

**Source consistency check:** Manuscript §3.1 describes **14 selected USC-SIPI images**, whereas the reported B2 results use **39 images**. The released manifest and manuscript should explicitly explain this distinction before publication. The 200 BSDS500 images in Experiment I overlap an earlier BSDS500 evaluation and must **not** be called an independent image holdout.

### 3.2 Protection methods

1. XOR secret sharing (2,2).
2. OR visual cryptography (2,2).
3. Random-grid OR (2,2).
4. Shamir secret sharing over GF(256), threshold (2,3).
5. AES-128-GCM with preshared key.
6. X25519/HKDF plus AES-128-GCM.
7. AES-GCM with XOR erasure coding (2,3).

Record protection parameters, key handling, randomness/seeds, fragment sizes, reconstruction criteria, and authentication outcomes. **Visual reconstruction is not equivalent to byte-identical RGB reconstruction.** Erasure-coded ciphertext fragments are not independently confidential threshold shares.

### 3.3 Simulated network parameters

| Parameter | Reported setting |
|---|---|
| Path bandwidths | 20 / 10 / 15 Mb/s |
| Path propagation delays | 10 / 40 / 25 ms |
| Packet payload / header | 1,000 / 20 bytes |
| Independent and burst loss probabilities | 0, 0.01, 0.05, 0.10, 0.20 |
| Burst persistence | 0.85 |
| Failed path in complete-failure scenario | Path 1 |
| FEC | 1 XOR parity packet per 4 data packets |
| ARQ | Up to 3 retransmissions |
| Organizational loss probabilities | 0.01, 0.10, 0.20 |
| Failure time / detection delay | 180 / 80 ms |
| Job arrival gap / preemption interval | 5 / 250 ms |
| Conflict injection / timeout | 75% / 3,000 ms |

The manuscript identifies code-defined seeds **3401** for impairment simulation and **3501** for packet recovery. Additional experiment-specific seeds must be recovered from the code/configurations rather than assumed.

### 3.4 Organizational configurations

| Configuration | Bidding | Ownership | Assistance | Reassignment |
|---|---|---|---|---|
| C1 Static | No | No | No | No |
| C2 Competitive | Yes | No | No | No |
| C3 Protected | Yes | Yes | No | No |
| C4 Assistance | Yes | Yes | Yes | No |
| C5 Reassignment | Yes | Yes | No | Yes |
| C6 Full | Yes | Yes | Yes | Yes |

The initial organizational ablation uses **four competing jobs per batch**. These jobs share resources and must not be treated as independent statistical units.

## 4. Reference results and acceptance checks

The numbers below are **published-result comparison targets**, not guarantees of exact reproduction on a different environment.

### 4.1 Packet recovery

| Policy | Success |
|---|---:|
| No recovery | 204/840 (24.29%) |
| FEC | 316/840 (37.62%) |
| ARQ | 772/840 (91.90%) |
| FEC+ARQ | 816/840 (97.14%) |

Check that the same transmission conditions and denominators are used before comparing outputs.

### 4.2 Organizational recovery under 20% loss

| Condition | Static | Assistance | Difference |
|---|---:|---:|---:|
| Independent packet loss | 92.06% | 98.85% | +6.79 percentage points |
| Burst packet loss | 90.85% | 98.44% | +7.59 percentage points |

### 4.3 Joint adaptation

| Strategy | Successful jobs / 672 | Completion | Mean objective | Mean censored execution time (ms) | Median planning time (ms) |
|---|---:|---:|---:|---:|---:|
| J1 Static | 167 | 24.85% | 0.6519 | 2316.35 | 19.19 |
| J2 Recovery | 167 | 24.85% | 0.6424 | 2315.16 | 18.74 |
| J3 Organization | 633 | 94.20% | 0.3959 | 412.94 | 40.86 |
| J4 Protection | 644 | 95.83% | 0.2515 | 395.53 | 19.08 |
| J5 Recovery + organization | 632 | 94.05% | 0.3586 | 410.24 | 79.95 |
| J6 Joint | 671 | 99.85% | 0.2114 | 276.41 | 139.43 |

J6 improves completion over J4 by **4.02 percentage points**, reduces mean objective by **15.94%**, and reduces mean **censored** execution time by **30.12%**, with higher median planning time. Censored execution time is **not** the latency of successful transmissions alone.

### 4.4 Search-efficiency benchmark

| Search | Candidates evaluated per case | Median planning time (ms) | Mean objective |
|---|---:|---:|---:|
| Exhaustive | 2,952 | 20.2707 | 0.209284 |
| Bounded | 8 | 0.0829 | 0.209284 |
| Greedy | 8 | 0.0561 | 0.209284 |
| Random | 128 | 0.8451 | 0.209284 |
| Static | 1 | 0.0075 | 0.714551 |

These are results on **300 matched cases per strategy**; matching the exhaustive objective in this finite benchmark does not prove global optimality in other search spaces.

### 4.5 Security and generalization

- **D:** 23/23 targeted security tests passed.
- **E:** 63,108 evaluated batches across 44 conditions; zero recorded constraint violations.
- **H:** 110/110 preflight tests passed; 21,266/21,504 successful jobs.
- **I / BSDS500:** 198,624/201,600 successful jobs (98.52%).
- **B2 / USC-SIPI:** 38,296/39,312 successful jobs (97.42%).

The security evidence establishes behavior under the **tested scenarios**, not formal confidentiality guarantees against arbitrary adversaries.

## 5. Statistical reproduction

Retain the pairing keys and the original experimental unit for each analysis:

- Protection: **image × repetition**.
- Transport: **matched transmission scenario**.
- Organization: **four-job batch**, not individual jobs treated as independent.
- Joint optimization: **matched image–network–workload scenario**.

Preserve raw observations and scripts needed to reproduce confidence intervals, paired effects, and Holm-adjusted significance results. Report confidence intervals and adjusted p-values within their original testing families. A non-significant adjusted comparison must not be described as statistically established merely because its point estimate is positive.

## 6. Repository file inventory — to complete from actual files

The following is a **documentation checklist**, not a claim that these paths exist:

| Material | Required verification |
|---|---|
| Experiment archives / directories | Exact name, branch, archive format, contents, size, SHA-256 |
| Python entry points | Exact relative path and supported command-line arguments |
| Dependency files | Actual imports and tested package versions |
| Configuration files | Network settings, protection choices, seeds, objective weights |
| Dataset manifests | Source, image IDs, partitions, dimensions, SHA-256 |
| Raw run records | Row counts, schema, scenario IDs, failure outcomes |
| Summary tables | Derivation scripts and linkage to manuscript tables |
| Statistical scripts | Resampling unit, bootstrap count, multiplicity correction |
| Figures | Source data and reproducible generation scripts |
| Security test logs | Test identifiers, expected rejection behavior, pass/fail records |

For each experiment, document its verified location using a record such as:

```text
Experiment identifier: <A, B1, B2, ...>
Repository path: <verified relative path>
Branch or release: <verified branch/tag>
Entry point: <verified Python script>
Command: <tested command>
Inputs: <verified manifests/configuration>
Outputs: <verified files and expected row counts>
Seed(s): <verified from source>
Manuscript link: <section/table/figure>
```

**Do not substitute guessed filenames or commands for these records.**

## 7. Recommended reproduction sequence

1. Clone or download the **specific tagged release** associated with the DOI.
2. Confirm all required experiment files are included in that release, not only in non-default branches.
3. Validate dataset provenance, file hashes, and license permissions.
4. Create a Python environment using versions verified from the original execution environment.
5. Run protection correctness and transport-recovery tests.
6. Run organizational ablations and compare matched batches.
7. Run targeted security checks and constraint-validation workloads.
8. Run joint optimization and the separate search-efficiency benchmark.
9. Regenerate statistical comparisons, tables, and figures from raw records.
10. Record deviations from reference metrics, including hardware and software differences.

The root `requirements.txt` is provisional until its contents are verified against all experiment scripts. The companion `REPRODUCIBILITY.md` provides broader methodological guidance.

## 8. Release-readiness checks

Before creating the Zenodo DOI release:

- [ ] Verify the complete experiment inventory, including the purpose of **F** and local naming of **A/J**.
- [ ] Consolidate release-relevant materials onto the tagged commit.
- [ ] Verify whether large archives fit GitHub/Zenodo release limits; do not assume other branches are archived.
- [ ] Resolve/document the **14 versus 39 USC-SIPI image** discrepancy.
- [ ] Confirm dataset redistribution permissions; link externally when redistribution is prohibited.
- [ ] Verify all dependency versions, entry points, and execution commands.
- [ ] Preserve raw results, run configurations, seeds, and statistical analysis scripts.
- [ ] Validate `CITATION.cff`, `LICENSE`, and README metadata.
- [ ] Tag an immutable release (for example, `v1.0.0`) and check the resulting Zenodo record.

## 9. Citation

Cite the associated manuscript and the **version-specific Zenodo DOI** for the exact repository release used. See `CITATION.cff` once author details and DOI metadata have been finalized.
