# Helios-1 Compact High-Field Tokamak: Technical Overview and Initial Operating Status

**Aurora Fusion Research Laboratory Technical Note AFRL-H1-2026-04**  
**Revision date:** 1 April 2026

## Executive summary

Helios-1 is a compact, high-field tokamak operated by the Aurora Fusion Research Laboratory (AFRL). The device was constructed to study high-field plasma control, diagnostic reconstruction, and confinement physics in deuterium plasmas at pulse lengths of several seconds. Helios-1 has a major radius of 1.35 m, a minor radius of 0.42 m, and a nominal toroidal magnetic field of 6.2 T. Its installed auxiliary-heating systems provide up to 8 MW of neutral beam injection (NBI) and 4 MW of electron cyclotron heating (ECH).

The first integrated experimental campaign was completed in March 2026. That campaign demonstrated repeatable operation near the original 1.20 MA plasma-current limit, including a 4.8 s high-current phase in discharge H1-1854. The purpose of this note is to summarize the device configuration as it existed at the end of Campaign A and to provide a common technical reference for later experimental reports. The operating limits described here are therefore those in force on 1 April 2026 and should not be interpreted as design limits for future upgraded configurations.

Helios-1 does not use tritium. All plasma experiments reported in this note use deuterium, and the facility is configured for research on plasma behavior and control rather than fusion-power production.

## 1. Program motivation and device concept

The Helios program was established to investigate whether compact, high-field devices can provide a useful platform for rapid plasma-control and diagnostic-development cycles. In contrast with larger long-pulse facilities, Helios-1 emphasizes relatively short experimental turnaround, dense magnetic instrumentation, and close integration between real-time control and post-shot reconstruction.

The machine is a conventional axisymmetric tokamak. Toroidal-field coils provide the dominant confining field, while poloidal-field coils shape and position the plasma. The vacuum vessel and magnetic geometry were sized around a major radius of 1.35 m and a minor radius of 0.42 m. At full field, the toroidal-field system is operated at a nominal 6.2 T. Reduced-field commissioning was also carried out: several early engineering pulses were run at 5.0 before the machine was returned to 6.2 for physics operation.

A principal design objective was to combine high magnetic field with sufficient actuator authority to explore aggressive current and density-control schemes. The initial operating envelope was intentionally conservative. During Campaign A the authorized plasma-current limit was 1.20 MA, even though several power and magnet subsystems had engineering margin beyond the conditions exercised in March.

For brevity, this note generally uses “Helios-1.” Engineering records and control-room logs also use “Helios 1,” “H-1,” and, where the context is unambiguous, “Helios” or “the machine.”

## 2. Magnetic and power systems

The toroidal-field system establishes the 6.2 T nominal field used for most physics shots. Poloidal-field circuits provide equilibrium shaping, vertical stabilization, and plasma-current support. The Plasma Current Power Supply (PCPS) coordinates the principal current-control waveform with the central solenoid and relevant poloidal-field circuits.

The vertical position of the plasma is regulated by the Vertical Control System (VCS). During Campaign A, the VCS operated with a 10 kHz control-update rate. The controller receives fast magnetic estimates derived from the Magnetic Probe Array and applies corrective commands to the vertical-control coils. It has separate gain schedules for startup, current ramp, and flat-top operation.

The VCS showed adequate stability margin over the March operating envelope, although several high-current shots approached the conservative actuator-rate threshold used by the protection system. Engineers therefore identified increased vertical-control bandwidth as a candidate improvement for a later campaign.

The PCPS is likewise a control and power subsystem rather than a diagnostic. During Campaign A its operating authorization limited commanded plasma current to 1.20 MA. This limit reflected the integrated behavior of the power supply, vertical-control response, and machine-protection settings, not a measured intrinsic current limit of the plasma.

## 3. Auxiliary heating

Helios-1 uses two principal auxiliary-heating systems. The Neutral Beam Injection System can provide up to 8 MW of injected power. The Electron Cyclotron Heating System provides up to 4 MW.

Campaign A generally used moderate NBI power during the current ramp and flat-top. Most high-current discharges were run between 4 and 6 MW of beam power. Brief operation at 8 was authorized during actuator checkout, but routine physics shots remained below that level.

The ECH system is used for startup assistance, profile-control experiments, and selected diagnostic studies. It was not the dominant heating actuator in the Campaign A high-current sequence.

## 4. Density control and fueling

Gas injection provides the primary particle source for routine Helios-1 operation. The Edge Density Controller (EDC) adjusts commanded gas flow using feedback from density measurements and selected edge diagnostics. The density controller was commissioned in a limited mode before Campaign A and was used primarily to maintain reproducible density trajectories rather than to test confinement hypotheses.

The controller has proportional and integral feedback paths with campaign-specific gain limits. It can be disabled on a shot-by-shot basis, allowing preprogrammed gas waveforms to be replayed without active feedback. In March, the EDC was generally enabled only after plasma formation. It was not used as an experimental variable in the principal high-current result reported for H1-1854.

The control-room log for several commissioning shots uses subsystem shorthand. During one VCS tuning sequence, an operator recorded that “the controller reduced vertical motion during the current ramp.” In a later density-control checkout, the note reads that “the controller increased gas flow as the edge density fell.” These entries are retained in the campaign log with the corresponding VCS and EDC signal groups.

## 5. Diagnostic systems and reconstruction

The diagnostic set was chosen to support both real-time control and post-shot plasma reconstruction.

The Rogowski Current Monitor (RCM) provides the principal measurement of total plasma current. The magnetic signal is integrated and calibrated against pulsed test currents before major campaigns. During Campaign A, the reported current values used the calibration set available in March. A dedicated post-campaign calibration study was already planned when this note was prepared.

The Magnetic Probe Array (MPA) contains distributed magnetic sensors around the vacuum vessel. Its measurements are used for fast control estimates and for higher-fidelity post-shot equilibrium analysis. The RCM and MPA serve related but distinct purposes; the probe array is not treated as an independent direct measurement of total plasma current.

Line-integrated electron density is measured with a two-color interferometer. Thomson scattering provides spatially resolved electron-temperature and electron-density profiles at discrete times during a discharge. An edge reflectometer measures fluctuation behavior and density structure near the plasma edge.

Post-shot magnetic reconstruction is performed using the Aurora Reconstruction Suite. Aurora combines calibrated magnetic measurements, coil-current data, and machine geometry to estimate plasma boundary and equilibrium quantities. The suite is maintained by the diagnostics and controls group and is versioned separately from the real-time control software.

The suite was used to reconstruct the Campaign A discharges discussed in Nguyen et al. [2]. It also provides the common equilibrium representation used when magnetic, interferometric, and Thomson-scattering data are compared after a shot.

## 6. Initial operating envelope

Table 1 summarizes selected Helios-1 parameters as of the end of Campaign A.

| Parameter | Value | Notes |
|---|---:|---|
| Major radius | 1.35 m | Geometric machine parameter |
| Minor radius | 0.42 m | Nominal plasma minor radius |
| Nominal toroidal field | 6.2 T | Full-field operation |
| Authorized plasma-current limit | 1.20 MA | Campaign A setting |
| Neutral beam capacity | 8 MW | Installed |
| Electron cyclotron heating capacity | 4 MW | Installed |
| VCS update rate | 10 kHz | Campaign A configuration |
| Typical full-field pulse length | 5–6 s | Experimental, not hard machine limit |

These entries mix stable device properties and operational settings. The geometric dimensions and installed heating capacities are expected to change only through major hardware modifications. By contrast, the authorized current limit and control-update rate are configuration-dependent and should be quoted with the applicable campaign or configuration date.

## 7. Campaign A operating status

Campaign A ran from 10 March through 21 March 2026 and focused on repeatable high-current operation. The campaign included plasma-formation studies, controller tuning, diagnostic cross-checks, and a sequence of shots approaching the 1.20 MA authorization boundary.

Discharge H1-1854 on 18 March reached a reported plasma current of 1.20 MA and sustained its high-current phase for 4.8 s. The same result is described in greater detail in the Campaign A experimental report [2]. Other accepted discharges reached slightly lower peak current but, in several cases, maintained the flat-top for longer intervals.

The result established that the integrated power, magnetic-control, and diagnostic systems could support operation at approximately 1.2 MA under the campaign conditions. It should not be interpreted as evidence that 1.20 MA is a fundamental stability threshold. No attempt was made during Campaign A to operate above the authorized limit.

The Campaign A report quoted an approximate 2% uncertainty for the plasma-current measurement on H1-1854. That value reflects the calibration state available during the campaign. Subsequent calibration work may revise both the central estimate and its uncertainty; precision comparisons should use the applicable diagnostics calibration report.

## 8. Known limitations and planned development

Several limitations were identified after Campaign A. First, the vertical-control system had less actuator-rate margin at the highest currents than desired for routine operation above 1.2 MA. Second, post-campaign review identified small calibration drifts in the Rogowski measurement chain. Third, the Edge Density Controller had not yet been exercised as an independent experimental variable, so no confinement conclusions should be drawn from its use during commissioning.

Planned work included an upgrade to plasma-current power regulation, higher-bandwidth vertical control, a dedicated magnetic-calibration study, and later experiments in which the EDC would be deliberately enabled and disabled in matched discharges.

No statistically meaningful claim about improved energy confinement is made in this note. The density controller was introduced as an operational subsystem, not as evidence for a confinement mechanism.

## 9. Summary

As of 1 April 2026, Helios-1 had completed its first integrated physics campaign and demonstrated repeatable operation near a 1.20 MA authorized plasma-current limit at a nominal toroidal field of 6.2 T. The machine combines high-field magnetic operation with 8 MW of installed NBI, 4 MW of ECH, fast magnetic control, and a diagnostic suite designed for detailed post-shot reconstruction.

The March results establish a baseline rather than a final performance envelope. The current limit and VCS update rate are configuration-dependent, while the plasma-current estimate depends on the calibration revision used in analysis. Geometric properties, installed actuator capacities, and diagnostic roles are expected to remain stable unless the corresponding hardware or analysis chain is modified.

## References

[1] M. Patel et al., “Design and Commissioning Basis of the Helios-1 Compact High-Field Tokamak,” AFRL Design Report DR-25-17, 2025.

[2] D. Nguyen et al., “High-Current Operation of the Helios-1 Compact Tokamak During Campaign A,” AFRL Experimental Report ER-26-03, 2026.

[3] S. Ortiz et al., “Magnetic Reconstruction and Plasma-Current Calibration for Helios-1,” AFRL Diagnostics Report, in preparation, 2026.

[4] L. Park et al., “Edge Density Feedback Architecture for Short-Pulse High-Field Tokamaks,” Proceedings of the 2025 Workshop on Plasma Control Systems, 2025.

[5] Aurora Fusion Research Laboratory, “Helios-1 Machine Protection and Operating Authorization Manual,” Rev. 3, 2026.
