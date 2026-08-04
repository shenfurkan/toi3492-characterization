# Candidate Feasibility (Seven-Day Kill Test)

Before committing months of effort to a target, produce a one-page go/no-go
report covering:

1. Inventory QLP, SPOC, and TESS-SPOC products; record sectors, cadences, and
   product identifiers.
2. Download the pixel cubes for the observed sectors with a cutout service.
3. Recover each candidate signal independently in every sector with BLS or TLS.
4. Try multiple apertures and detrending methods; the signal must not depend
   on the choice.
5. For ambiguous periods, test both P and 2P and compare evidence.
6. Run odd/even depth, secondary eclipse, centroid, and difference-image
   checks.
7. Compute the eclipse depth each neighboring catalog source would need to
   produce the observed signal through dilution.
8. Extract event-level transit times.
9. Perform a quick stellar SED and isochrone preview.
10. Write the one-page go/no-go report in the candidate's `docs/`.

## Stop Conditions

Do not continue when any of the following holds:

- The signal appears in a single sector only.
- The amplitude depends strongly on aperture or detrending choice.
- The difference-image centroid points away from the target toward a
  catalog neighbor.
- Odd/even depth or timing asymmetry matches an eclipsing binary.
- Transit durations are inconsistent with a common stellar density.
- A km/s-scale radial-velocity variation is confirmed in new reconnaissance
  spectra.
- A group with imaging or spectroscopic follow-up is already near publication
  on the same target.
- No contrast-imaging or reconnaissance-spectroscopy collaboration is
  available when the science plan requires one.

## Feasibility Output

The report states: signal summary per sector, vetted alias hypotheses, Gaia
neighbor census, required follow-up, remaining risks, and the decision
`GO`, `HOLD`, or `STOP`. The report is evidence for the `feasibility` phase in
the candidate's lifecycle, never a validation claim.
