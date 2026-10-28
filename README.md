# Competitive-Cooperative-Secure-Image-Sharing


**Competitive–Cooperative Organizational Intelligence for Adaptive Secure Image Sharing over Heterogeneous Multipath Networks**

## Overview

This repository accompanies the research paper *Competitive–Cooperative Organizational Intelligence for Adaptive Secure Image Sharing over Heterogeneous Multipath Networks*.

The research investigates how competitive task allocation and cooperative recovery can be integrated to improve secure image transmission over heterogeneous multipath networks.

Conventional approaches often address image protection, packet recovery, and transmission-resource allocation independently. However, these decisions interact under network failures, resource contention, and security restrictions.

The proposed framework addresses this challenge through a unified organizational intelligence model that coordinates:

- Competitive agent bidding and task allocation.
- Protected task ownership and commitment management.
- Resource-bounded cooperative assistance.
- Failure-triggered task reassignment.
- Adaptive image-protection selection.
- Packet-level recovery and multipath transmission.
- Joint optimization under security and resource constraints.

The framework is evaluated using controlled network simulations, organizational ablation studies, optimization benchmarks, security tests, and image datasets.

## Research Contributions

The principal contributions are:

**1. Competitive–Cooperative Organizational Intelligence**

A coordination mechanism integrating competitive task assignment with cooperative execution recovery. Agents compete for feasible transmission responsibilities and cooperate when network conditions threaten successful completion.

**2. Commitment-Aware Task Management**

An organizational model that establishes explicit task ownership, protects active commitments, and permits authorized assistance or reassignment without violating responsibility and resource constraints.

**3. Adaptive Secure Image Transmission**

Integration of image-protection mechanisms with packet recovery and heterogeneous multipath communication, allowing transmission configurations to accommodate different reliability, reconstruction, and communication requirements.

**4. Joint Adaptive Optimization**

A unified optimization formulation coordinating protection selection, transport recovery, and organizational resource allocation while respecting security, feasibility, and operational constraints.

**5. Experimental Validation**

A comprehensive evaluation examining reconstruction correctness, communication overhead, network reliability, organizational recovery, optimization performance, security enforcement, and statistical robustness.

## System Architecture

The framework consists of five interconnected stages.

| Stage | Description |
|---|---|
| Image preparation and protection | Selects an eligible protection mechanism and generates protected image fragments. |
| Organizational decision-making | Allocates transmission responsibilities through capability-aware bidding and protected commitments. |
| Secure multipath transmission | Distributes protected fragments over heterogeneous communication paths. |
| Monitoring and cooperative adaptation | Detects transmission problems and activates bounded assistance or authorized reassignment. |
| Reception and reconstruction | Recovers transmitted fragments and reconstructs the image according to method-specific requirements. |

A joint adaptive decision mechanism coordinates these stages to balance reliability, execution time, communication overhead, and resource utilization.

## Image Protection Mechanisms

The experimental framework evaluates seven protection mechanisms.

| Protection mechanism | Reconstruction characteristics |
|---|---|
| XOR secret sharing (2,2) | Exact reconstruction requiring both shares |
| OR visual cryptography (2,2) | Binary visual reconstruction |
| Random-grid OR (2,2) | Visual reconstruction evaluated using statistical contrast |
| Shamir secret sharing over GF(256) (2,3) | Exact reconstruction from sufficient shares |
| AES-128-GCM with preshared key | Authenticated encryption and exact reconstruction |
| X25519/HKDF with AES-128-GCM | Key agreement, authenticated encryption, and exact reconstruction |
| AES-GCM with XOR erasure coding (2,3) | Authenticated encryption with fragment-loss tolerance |

These mechanisms have different security assumptions, reconstruction requirements, computational costs, and communication overhead.

**Important:** Visual reconstruction is not equivalent to pixel-identical reconstruction. Additionally, erasure-coded ciphertext fragments should not be interpreted as independently confidential threshold shares.

## Network and Recovery Model

The experimental network contains three heterogeneous communication paths.

| Parameter | Configuration |
|---|---|
| Path bandwidths | 20, 10, and 15 Mb/s |
| Path propagation delays | 10, 40, and 25 ms |
| Packet payload | 1,000 bytes |
| Packet header | 20 bytes |
| Packet-loss probabilities | 0%, 1%, 5%, 10%, and 20% |
| Burst-loss persistence | 0.85 |
| Complete path-failure scenario | Path 1 unavailable |
| FEC configuration | One XOR parity packet per four data packets |
| ARQ configuration | Maximum of three retransmissions |

Four transport-recovery policies are evaluated:

1. No recovery.
2. Forward error correction (FEC).
3. Automatic repeat request (ARQ).
4. Combined FEC and ARQ.

Packet recovery and protection-level reconstruction are evaluated separately because recovering packets does not necessarily guarantee that sufficient valid fragments are available to reconstruct an image.

## Organizational Coordination

The organizational framework supports six experimental configurations.

| Configuration | Bidding | Ownership | Assistance | Reassignment |
|---|---|---|---|---|
| Static | No | No | No | No |
| Competitive | Yes | No | No | No |
| Protected | Yes | Yes | No | No |
| Assistance | Yes | Yes | Yes | No |
| Reassignment | Yes | Yes | No | Yes |
| Full coordination | Yes | Yes | Yes | Yes |

These configurations enable controlled comparisons of competitive allocation, commitment protection, cooperative recovery, and their combined effects.

### Competitive bidding

Eligible agents submit bids reflecting their estimated transmission costs, available resources, workload, and expected reliability.

### Protected ownership

Selected agents acquire explicit responsibility for assigned transmission tasks. Ownership and resource reservations are maintained through controlled commitment transitions.

### Cooperative assistance

When transmission difficulties occur, an eligible supporting agent may assist the current owner without transferring task responsibility.

### Dynamic reassignment

When an assignment becomes unsustainable, responsibility may be transferred to another eligible agent, subject to security, resource, and cumulative-exposure constraints.

## Joint Adaptive Optimization

The joint optimization component coordinates three decision dimensions:

- Image-protection mechanism.
- Packet-recovery policy.
- Organizational agent–path allocation.

Six adaptation strategies are compared.

| Strategy | Adaptation scope |
|---|---|
| J1 | Static configuration |
| J2 | Recovery adaptation |
| J3 | Organizational adaptation |
| J4 | Protection adaptation |
| J5 | Recovery and organizational adaptation |
| J6 | Joint adaptation |

The optimization objective balances reconstruction reliability, execution time, resource expenditure, and organizational intervention overhead.

Security and operational feasibility are enforced as constraints rather than treated as penalties that can be offset by improved performance elsewhere.

## Datasets

The experiments use images from two established collections.

### BSDS500

The Berkeley Segmentation Dataset and Benchmark is used for protection, transmission, organizational, and optimization experiments.

The principal large-scale evaluation includes 200 BSDS500 images.

### USC-SIPI

The USC-SIPI image collection provides an additional image source for evaluating organizational recovery across different image content.

The reported external evaluation includes 39 images.

### Dataset provenance

Dataset names, source partitions, image identifiers, dimensions, and SHA-256 hashes should be retained in the corresponding experimental manifests.

The 200-image BSDS500 evaluation overlaps with an earlier BSDS500 experiment and should not be described as an independent image holdout. USC-SIPI provides a separate image-source evaluation.

Original dataset redistribution is subject to the respective dataset providers' terms.

## Principal Experimental Results

### Packet recovery

Combined FEC+ARQ substantially improved transmission reliability.

| Recovery policy | Transmission success |
|---|---:|
| No recovery | 24.29% |
| FEC | 37.62% |
| ARQ | 91.90% |
| FEC+ARQ | 97.14% |

These results correspond to the reported packet-recovery evaluation and should not be interpreted as directly comparable with the protection-method reconstruction results.

### Cooperative recovery

Cooperative assistance improved transmission completion under severe network impairments.

| Network condition | Static | Assistance | Improvement |
|---|---:|---:|---:|
| 20% independent packet loss | 92.06% | 98.85% | +6.79 percentage points |
| 20% burst packet loss | 90.85% | 98.44% | +7.59 percentage points |

The corresponding improvements represent 326 and 364 additional successful jobs, respectively, out of 4,800 evaluated jobs per condition.

### Joint optimization

The integrated adaptation experiment compared six strategies over 672 transmission jobs per strategy.

| Metric | Protection adaptation (J4) | Joint adaptation (J6) |
|---|---:|---:|
| Completion rate | 95.83% | 99.85% |
| Successful jobs | 644/672 | 671/672 |
| Mean optimization objective | 0.2515 | 0.2114 |
| Mean wire ratio | 1.3482 | 1.2613 |
| Mean censored execution time | 395.53 ms | 276.41 ms |
| Median planning time | 19.08 ms | 139.43 ms |

Compared with protection adaptation, joint adaptation achieved:

- A 4.02-percentage-point increase in completion.
- A 15.94% reduction in the mean optimization objective.
- A 30.12% reduction in mean censored execution time.

These improvements were accompanied by increased planning overhead.

Censored execution time includes unsuccessful and infeasible executions; it should not be interpreted as successful-transmission latency.

### Search efficiency

A separate candidate-search experiment compared exhaustive, bounded, greedy, random, and static strategies over 300 matched cases per strategy.

Bounded and greedy search evaluated eight candidates per case and achieved the same reported mean objective as exhaustive enumeration, which evaluated 2,952 candidates per case.

This result demonstrates computational efficiency within the evaluated candidate space, not universal equivalence to exhaustive optimization.

### Large-scale evaluation

| Dataset | Successful jobs | Completion rate |
|---|---:|---:|
| BSDS500 | 198,624/201,600 | 98.52% |
| USC-SIPI | 38,296/39,312 | 97.42% |

The results support consistency across the evaluated image sources and simulated network conditions.

## Security Validation

Security validation addresses:

- Cryptographic correctness and authenticated decryption.
- Rejection of tampered authenticated ciphertext.
- Reconstruction restrictions for insufficient shares or fragments.
- Authorized task ownership and reassignment.
- Resource-capacity and reservation constraints.
- Cumulative fragment-exposure restrictions.
- Security-aware cooperative assistance.

All 23 targeted security tests passed.

A separate constraint-validation evaluation covered 63,108 batches across 44 conditions without recorded constraint violations.

These results demonstrate enforcement of the tested implementation constraints. They do not constitute a formal proof of confidentiality or security against arbitrary adversaries.

## Statistical Evaluation

The research includes paired statistical comparisons, confidence intervals, multiplicity adjustments, and sensitivity analyses.

The principal statistical findings indicate that:

- Full coordination improved completion for both evaluated protection methods on BSDS500 and USC-SIPI.
- Completion improvements were larger for AES128-GCM-PSK than for the erasure-protected configuration.
- Additional organizational mechanisms did not always produce statistically distinguishable improvements.
- Communication and execution costs depended on the protection method.
- Intervention availability was particularly important under severe burst-loss conditions.

Statistical interpretation should preserve the experimental unit, pairing structure, confidence-interval procedure, and multiple-testing correction used in each analysis.

## Reproducibility

The research uses controlled simulations rather than physical-network measurements.

Reproduction requires the relevant implementation, configuration files, input images, dependency versions, random seeds, and experimental records.

The manuscript identifies the following software components:

- Python
- Pillow
- `cryptography`
- Custom simulation, optimization, and logging routines

The reported execution environment includes:

| Component | Specification |
|---|---|
| Operating system | 64-bit Windows |
| Processor | Intel Core Ultra 7 265KF |
| Memory | 32 GB RAM |
| GPU installed | NVIDIA GeForce RTX 5070, 12 GB |
| Programming language | Python |

The presence of a GPU does not imply that the experiments used GPU acceleration.

### Running the experiments

The exact installation and execution commands depend on the files included in the published repository.

Before reproducing the results:

1. Obtain the datasets from their authorized sources.
2. Verify the expected image identifiers and hashes.
3. Install the dependency versions recorded by the implementation.
4. Review the experiment configuration and random seeds.
5. Execute the relevant experimental scripts.
6. Compare generated outputs against the reported results.

Executable commands should be added once the final repository structure and entry-point scripts have been verified.

## Interpretation and Limitations

The experiments support the effectiveness of cooperative recovery and joint adaptive decision-making within the evaluated simulation environment.

Several limitations should be considered:

- Network conditions are simulated rather than measured on physical multipath networks.
- The security evaluation verifies implemented checks but does not establish unrestricted adversarial security.
- The BSDS500 large-scale evaluation is not an independent image holdout.
- Assistance and reassignment do not consistently provide additive improvements.
- Joint optimization introduces additional planning overhead.
- Candidate-search findings are specific to the evaluated search space.
- Execution-time measurements do not fully isolate cryptographic processing and network signaling costs.

Future work may investigate real-network deployment, larger heterogeneous agent populations, more demanding security models, independently collected datasets, and computationally efficient adaptation under dynamic operating conditions.

## Associated Publication

**Title:** Competitive–Cooperative Organizational Intelligence for Adaptive Secure Image Sharing over Heterogeneous Multipath Networks

**Authors:** To be added upon publication.

**Journal:** To be added upon publication.

**DOI:** To be added upon publication.

### Citation

Please cite the associated research article when using this repository.

The final bibliographic citation and BibTeX entry will be added after publication.

## Data and Code Availability

The repository is intended to support verification and reproduction of the experimental framework described in the associated manuscript.

Availability of individual datasets, scripts, configurations, and result files should be determined from the files included in the published repository.

Original image datasets may require separate retrieval from their respective providers.

## License

The repository license should be specified before public release.

Software code, experimental outputs, documentation, and externally sourced datasets may be subject to different licensing conditions.

## Research Scope

This repository is intended for academic research, reproducibility, and experimental evaluation of secure multipath communication and distributed organizational intelligence.

The reported results should not be interpreted as certification for production security systems or as evidence of performance in untested physical-network environments.
