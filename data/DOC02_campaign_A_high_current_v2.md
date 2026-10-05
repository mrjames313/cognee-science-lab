# High-Current Operation of the Helios-1 Compact Tokamak During Campaign A

**Daniel Nguyen, Mira Patel, Sofia Ortiz, and the Helios-1 Experimental Team**  
Aurora Fusion Research Laboratory  
AFRL Experimental Report ER-26-03  
8 April 2026

## Abstract

The first integrated physics campaign on the Helios-1 compact high-field tokamak was conducted from 10 to 21 March 2026. The campaign tested plasma formation, magnetic control, diagnostic reconstruction, and operation near the initial authorized plasma-current limit of 1.20 MA. A sequence of deuterium discharges was executed at a nominal toroidal field of 6.2 T with neutral beam heating and, on selected shots, auxiliary electron cyclotron heating. Discharge H1-1854 reached a reported plasma current of 1.20 MA and maintained the high-current phase for 4.8 s without disruption. The preliminary current uncertainty for this discharge is estimated at approximately ±0.02 MA using the calibration available during the campaign.

The objective of Campaign A was not to determine the maximum achievable plasma current of Helios-1. Rather, it was to establish a repeatable operational baseline at the authorized limit and to characterize control-system and diagnostic behavior as that limit was approached. The results show stable operation near 1.2 MA over multiple discharges and identify vertical-control authority and magnetic-calibration precision as priorities for subsequent work.

## 1. Introduction

Helios-1 is a compact high-field tokamak developed by the Aurora Fusion Research Laboratory (AFRL) for studies of plasma control, diagnostic reconstruction, and confinement physics in deuterium plasmas. The device has a major radius of 1.35 m, a nominal minor radius of 0.42 m, and a nominal toroidal field of 6.2 T [1]. The installed auxiliary-heating systems include 8 MW of neutral beam injection (NBI) and 4 MW of electron cyclotron heating (ECH).

Initial engineering operation during late 2025 and early 2026 established plasma formation and low-current control. Campaign A was the first coordinated physics campaign in which the power, vertical-control, fueling, and reconstruction systems were operated together over a sustained sequence of high-current discharges.

The campaign was performed under a 1.20 MA plasma-current authorization. This number was an operating limit set by the integrated machine-protection and control configuration. It was not intended to represent an inferred magnetohydrodynamic stability boundary or a fundamental device limit.

The principal goals were therefore: (1) to demonstrate repeatable current ramps to the authorization boundary; (2) to sustain a multi-second high-current phase; (3) to verify that the Vertical Control System (VCS) retained adequate authority at the highest commanded currents; and (4) to assess agreement among the Rogowski Current Monitor, magnetic reconstruction, and other relevant diagnostics.

## 2. Experimental configuration

### 2.1 Magnetic configuration and current control

All high-current shots reported here were performed near the nominal full-field condition of 6.2 T. Plasma current was driven through the standard central-solenoid and poloidal-field sequence, with the Plasma Current Power Supply (PCPS) providing the coordinated current-control waveform.

The VCS was operated at a 10 kHz update rate. It used fast magnetic estimates from the Magnetic Probe Array (MPA) and commanded the vertical-control coils to suppress displacement during the current ramp and flat-top. During tuning shots early in the campaign, the controller gains were adjusted to reduce a small vertical oscillation observed above approximately 0.9 MA. It responded well to the revised gain schedule, and the resulting parameters were held fixed for the principal high-current sequence. An operator note from this sequence records that “the controller caught the upward motion at 0.95 MA”; the associated coil-command trace shows the revised VCS gain schedule was active.

### 2.2 Heating and fueling

Neutral beam injection provided the dominant auxiliary heating for the high-current sequence. NBI power was normally increased after plasma formation and held between 4 and 6 MW through the high-current phase. For H1-1854, commanded beam power during the flat-top was 6 MW.

ECH was used on several development shots but was not required for the principal H1-1854 result. The heating configuration was intentionally kept simple to reduce shot-to-shot variation while current-control performance was evaluated.

Fueling was provided by preprogrammed gas injection with optional edge-density feedback. The Edge Density Controller (EDC) used interferometer and edge-density information to trim the gas command after startup. For the main high-current shots it served as a reproducibility aid rather than as an experimental variable. The density controller was enabled on H1-1854 after the plasma-current ramp began. It made small corrections to gas flow but did not determine the current waveform.

A short density dip near the start of the H1-1854 high-current phase was followed by a small increase in commanded gas. The control-room log notes that “the controller added gas after the density dip.” The gas-demand and density traces show the correction occurred after the EDC was enabled.

### 2.3 Diagnostics

Total plasma current was measured primarily by the Rogowski Current Monitor (RCM). The RCM calibration used during Campaign A was established from pulsed test-current measurements performed before the campaign. The preliminary absolute uncertainty in the high-current range was estimated at roughly 2%.

The Magnetic Probe Array supplied spatial magnetic measurements for both fast control and post-shot reconstruction. Post-shot equilibria were reconstructed with the Aurora Reconstruction Suite [1,3]. Aurora incorporates magnetic measurements, coil currents, and machine geometry to estimate the plasma boundary and related equilibrium quantities. The software configuration used for the campaign was maintained separately from the real-time control system.

Electron density was monitored with a two-color interferometer, and selected time slices were cross-checked using Thomson scattering. The edge reflectometer was recorded on most high-current shots but was not used to infer plasma current.

## 3. Campaign methodology

Campaign A was organized as a progression rather than a search for a single record discharge. The first phase established reproducible plasma formation and verified diagnostic timing. The second phase increased commanded current in approximately 0.1 MA increments while retaining conservative protection thresholds. The final phase repeated shots between 1.1 and 1.2 MA to evaluate reproducibility, control margin, and flat-top duration.

A shot was accepted for the high-current comparison set if it met four criteria: successful plasma formation, valid RCM data, valid magnetic reconstruction over the high-current interval, and no machine-protection termination before the planned end of the flat-top. Shots used only for actuator checkout or diagnostic timing were excluded from the comparison set.

The campaign did not include any commanded current above 1.20 MA. Measurements above 1.20 MA were therefore neither a study objective nor an unobserved failure of the machine; they were outside the authorized experiment.

The analysis in this report uses the calibration constants available at the end of Campaign A. A separate diagnostics activity led by Ortiz was initiated to quantify temperature sensitivity and slow drift in the RCM chain. Because that study was incomplete at the time of submission, the values below should be considered the campaign-reported estimates rather than final metrological values.

## 4. Results

### 4.1 High-current sequence

Table 1 lists representative accepted discharges from the final campaign sequence.

| Shot | Date | Reported peak plasma current | High-current duration | NBI power | Outcome |
|---|---|---:|---:|---:|---|
| H1-1829 | Mar 17 | 1.08 MA | 5.3 s | 5 MW | Completed |
| H1-1841 | Mar 18 | 1.14 MA | 5.1 s | 5 MW | Completed |
| H1-1854 | Mar 18 | 1.20 MA | 4.8 s | 6 MW | Completed |
| H1-1857 | Mar 18 | 1.18 MA | 5.1 s | 6 MW | Completed |
| H1-1883 | Mar 19 | 1.16 MA | 5.4 s | 5 MW | Completed |

H1-1854 produced the highest reported plasma current in the accepted Campaign A set. The RCM indicated 1.20 MA at the top of the current ramp, with an estimated preliminary uncertainty of ±0.02 MA. The discharge remained in the high-current phase for 4.8 s and terminated according to the planned waveform rather than through a disruption or protection event.

The neighboring shot H1-1857 reached a slightly lower reported peak current, 1.18 MA, but maintained the high-current interval for 5.1 s. Across the final sequence, the operating scale was therefore approximately 1.2 MA for about five seconds, although no single discharge combined exactly 1.20 MA with exactly 5.0 s.

### 4.2 Vertical-control performance

Vertical displacement remained bounded on all accepted high-current shots. As current increased above approximately 1.0 MA, the VCS required larger and faster corrective commands. No accepted discharge was lost because of vertical instability, but actuator-rate margin decreased near the authorization boundary.

Review of the vertical-position and coil-command traces showed the same trend across the final sequence: the controller retained sufficient authority at 1.2 MA, while the distance to the conservative protection threshold narrowed compared with lower-current operation. Campaign A therefore demonstrated adequate vertical control at the authorized limit but did not establish substantial margin for routine operation at higher current.

The control team recommended an increase in vertical-loop bandwidth before routine operation above 1.2 MA. The recommendation was based on VCS actuator-rate margin and did not involve the density-feedback loop.

### 4.3 Density and heating behavior

The accepted high-current shots were operated over a relatively narrow density range to simplify comparison. The EDC made modest gas-flow corrections when enabled. It did not produce a systematic confinement experiment because there was no matched set of otherwise identical EDC-on and EDC-off shots.

For H1-1854, the interferometer showed a stable density trajectory through most of the flat-top. The short density dip near the start of the high-current phase was followed by a small increase in commanded gas, after which the measured density returned toward its pre-dip trajectory. No measurable interruption of the plasma-current waveform accompanied the correction.

Neutral beam power for the final sequence was typically 5–6 MW. The beam system had higher installed capacity, but the campaign did not require operation at its 8 MW limit.

### 4.4 Diagnostic consistency

The campaign-reported RCM estimate and the Aurora magnetic reconstruction were mutually consistent at the level required for operational decisions. The reconstruction was not treated as an independent primary measurement of total plasma current; instead, it served as a consistency check using a broader set of magnetic signals.

A small shot-to-shot offset was observed between the current inferred using alternative calibration subsets. The effect was within the preliminary 2% uncertainty assigned during the campaign. However, because the offset appeared correlated with measurement-chain temperature, the diagnostics team initiated a dedicated calibration study after Campaign A.

No correction from that later work is applied in the present report. Thus the value 1.20 ± 0.02 MA for H1-1854 should be understood as the result reported under the March calibration, not as a claim that later analysis cannot revise the estimate.

## 5. Discussion

Campaign A achieved its primary objective: Helios-1 operated repeatably near the initial 1.20 MA authorization boundary with stable magnetic control and multi-second high-current phases. The most prominent result, H1-1854, is best viewed as a system-integration milestone rather than a search for maximum device performance.

Three qualifications are important when interpreting the campaign results. First, the 1.20 MA authorization was configuration-dependent and should not be treated as a permanent device property or a fundamental plasma stability limit. Second, the H1-1854 current value and uncertainty correspond to the March 2026 calibration state; a later calibration may revise the estimate without changing the physical discharge that occurred on 18 March. Third, the VCS and EDC served different control functions during the campaign: the VCS acted on vertical position through coil commands, while the EDC acted on gas flow using density feedback.

Installed actuator capacity should likewise be distinguished from the power used in a particular experiment. Helios-1 has 8 MW of installed NBI capacity, while the H1-1854 flat-top used 6 MW.

## 6. Limitations

The campaign duration was short, and the accepted high-current set was designed around operational progression rather than statistical characterization of plasma performance. The results do not establish a confinement scaling law, a disruption boundary, or a maximum achievable current.

The current measurement carries a preliminary calibration uncertainty. Although the RCM and magnetic reconstruction were consistent for operational purposes, a later metrology study may alter the best numerical estimate for H1-1854.

The EDC was used only as a supporting control subsystem. No statistically significant claim about improved energy confinement can be made from Campaign A, and the report does not establish that density feedback reduces edge turbulence or causes any confinement change.

Similarly, no conclusion should be drawn from the absence of shots above 1.20 MA. They were not attempted.

## 7. Conclusions

Helios-1 completed its first integrated high-current campaign in March 2026. Under a nominal 6.2 T toroidal field and a 1.20 MA operating authorization, the device demonstrated repeatable high-current operation. H1-1854 reached a campaign-reported plasma current of 1.20 ± 0.02 MA and sustained the high-current phase for 4.8 s.

The VCS maintained vertical stability throughout the accepted sequence, although reduced actuator-rate margin near the authorization boundary motivated a planned bandwidth upgrade. The EDC provided modest density corrections on selected shots but was not evaluated as a confinement-control mechanism.

The Campaign A data establish an operational baseline for later upgrades and experiments. Subsequent reports should identify the applicable machine configuration and current-calibration revision when comparing these results with later campaigns.

## References

[1] M. Patel et al., “Design and Commissioning Basis of the Helios-1 Compact High-Field Tokamak,” AFRL Design Report DR-25-17, 2025.

[2] Aurora Fusion Research Laboratory, “Helios-1 Compact High-Field Tokamak: Technical Overview and Initial Operating Status,” Technical Note AFRL-H1-2026-04, 2026.

[3] S. Ortiz et al., “Magnetic Reconstruction and Plasma-Current Calibration for Helios-1,” AFRL Diagnostics Report, in preparation, 2026.

[4] Aurora Fusion Research Laboratory, “Helios-1 Machine Protection and Operating Authorization Manual,” Rev. 3, 2026.

[5] L. Park et al., “Edge Density Feedback Architecture for Short-Pulse High-Field Tokamaks,” Proceedings of the 2025 Workshop on Plasma Control Systems, 2025.
