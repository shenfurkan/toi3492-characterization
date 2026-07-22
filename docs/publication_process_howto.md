# TOI-3492.01 Publication Process How-To

Last project-state synchronization: 2026-07-22. Publication is currently
blocked by the scientific phases in `../currentproblem.md`. The versioned file
names below are procedural examples from the superseded release and must be
replaced only after a new version is assigned.

This is the operator runbook for publishing the TOI-3492.01 candidate
characterization. It covers:

- reserving and publishing a Zenodo DOI;
- submitting the reproducibility package to the AAS Journals Zenodo Community;
- obtaining arXiv endorsement and submitting the preprint;
- submitting a manuscript separately to an AAS journal;
- preserving versions, licenses, hashes, and scientific claim boundaries.

The procedures are deliberately separated because Zenodo, arXiv, and an AAS
journal publish different objects and assign different identifiers.

## 1. Current Release Scope

No current release is ready. The working draft supports, at most, a descriptive
candidate interpretation and fails the Phase 0 manuscript gate.

The publication-safe description is:

> TOI-3492.01 is an unvalidated and unconfirmed short-period, giant-planet-size
> transit candidate characterized with public TESS and catalog data. The
> inferred companion radius is conditional on the signal being planetary, on
> the transit occurring on the catalog target, and on the adopted stellar and
> dilution assumptions.

Do not describe the object as statistically validated, dynamically confirmed,
or as having a measured eccentricity. Do not report a formal FPP. The binding
machine-readable claim gate is `outputs/release_status.json`.

The principal release files are:

| Purpose | File |
|---|---|
| Canonical manuscript source | `toi3492_characterization.tex` |
| Compiled manuscript | `toi3492_characterization.pdf` after AASTeX rebuild |
| arXiv source package | New package to be built after final verification |
| Zenodo reproducibility package | New version to be assigned after remediation |
| Whole-ZIP checksum | Generate with the new reproducibility package |
| Citation metadata | `CITATION.cff` |
| License matrix | `LICENSES.md` |
| Scientific decision log | `currentproblem.md` |
| Machine-readable release gate | `outputs/release_status.json` |

No current package or checksum is release-ready. Generate the manifest, release
ZIP, and sidecar only after the scientific phases and final manuscript edits.

## 2. Understand the Three Publication Objects

### 2.1 Zenodo record

Zenodo archives the reproducibility package: code, compact inputs,
machine-readable outputs, figures, provenance, tests, and documentation.

- Zenodo assigns a DOI after the record is published.
- A DOI may be reserved while the record is still a draft, but it may not
  resolve publicly before publication.
- For this project, an unresolved historical reservation is not treated as a
  verified DOI and must not be inserted into public manuscript or citation
  metadata.
- The exact version DOI identifies the immutable `v1.0.1` record only after the
  intended record has been published and verified.
- Zenodo also maintains an all-versions or concept DOI when a record has
  versions.
- Cite the version DOI when exact reproducibility matters.
- Use the concept DOI when directing readers to the latest project release.

### 2.2 arXiv preprint

arXiv publishes the manuscript source and figures. It assigns an identifier
such as `arXiv:YYMM.NNNNN`; it does not normally assign a DOI.

The Zenodo DOI belongs to the reproducibility package, not to the manuscript.
Do not enter the Zenodo package DOI into arXiv's journal-article DOI field as if
it were the article DOI. Cite it in the manuscript's data/code availability
statement and, where appropriate, in the arXiv comments.

### 2.3 AAS journal article

An AAS journal submission is made through the AAS manuscript submission
portal. If accepted and published, the publisher assigns a separate article
DOI.

The AAS Journals Zenodo Community is a curation community for related data,
software, and research artifacts. It is not the journal manuscript submission
portal and does not imply peer review or acceptance of the paper.

## 3. Recommended Publication Order

Use this order unless a journal's dual-anonymous review requirements require an
unpublished and anonymized Zenodo draft:

1. Confirm author identity, ORCID, affiliation, title, version, and licenses.
2. Recompile the manuscript and run all scientific and publication tests.
3. Regenerate the provenance manifest and both release packages, then verify
   the final ZIP checksum.
4. Commit and tag the exact tested `v1.0.1` source when the repository is ready
   for a formal release.
5. Create or correct the Zenodo draft and enter `v1.0.1` metadata.
6. Reserve a DOI only for the intended corrected draft; keep it out of public
   metadata while it is unresolved.
7. Upload the exact tested ZIP, sidecar, README, and license matrix.
8. Associate the draft with the AAS Journals Zenodo Community if desired.
9. Review the Zenodo preview and publish the record.
10. Open the public DOI in a private browser, download the public files, and
    independently verify the checksum.
11. Only after that verification, add the DOI consistently to public citation
    metadata or issue a metadata-only/corrective version as Zenodo permits.
12. Complete arXiv endorsement if required.
13. Upload `arxiv_submission.zip` to arXiv and inspect arXiv's generated PDF.
14. After the arXiv identifier is issued, add it to the Zenodo record as a
    related identifier.
15. If pursuing journal publication, convert the manuscript to AASTeX and
    submit it separately through the AAS portal.
16. After journal publication, add the article DOI and journal reference to
    arXiv and Zenodo metadata.

## 4. Accounts and Information Needed

Prepare the following before opening a Zenodo draft:

- [ ] Zenodo account.
- [ ] ORCID iD connected to Zenodo if available.
- [ ] arXiv account using an Ankara University institutional email if
      available.
- [ ] Exact author form: `Furkan Şen`.
- [ ] Affiliation: `Department of Astronomy and Space Sciences, Ankara
      University`.
- [ ] ORCID URL, if available.
- [ ] GitHub repository URL:
      `https://github.com/shenfurkan/toi3492-characterization`.
- [x] Final local release version: `1.0.1`.
- [x] Final content-license decision: CC BY 4.0 for original content; MIT for
      software.
- [ ] Whether an AAS journal submission will use dual-anonymous review.
- [ ] arXiv endorsement link/code, if arXiv requests endorsement.

Never put account passwords, private Zenodo sharing links, API tokens, or an
active arXiv endorsement code in Git, the manuscript, a public issue, or the
Zenodo record.

## 5. License Gate Before Deposit

This step is complete for version `1.0.1`. On 2026-07-12 the author explicitly
approved CC BY 4.0 for the original manuscript, original figures, narrative
documentation, and original derived tables. The software remains under MIT.

Recommended license matrix:

| Artifact class | Approved license or treatment |
|---|---|
| Source code in `scripts/` and `tests/` | MIT, already granted in `LICENSE` |
| Manuscript, original figures, and narrative documentation | CC BY 4.0 |
| Original derived tables | CC BY 4.0 |
| TESS, Gaia, ExoFOP, NASA Exoplanet Archive, and other catalog material | Retains upstream terms; no ownership asserted |

The implemented license state must remain true before public deposit:

1. Keep the explicit CC BY 4.0 grant in `LICENSES.md`.
2. Keep the MIT license for software.
3. Keep all upstream-data acknowledgements and restrictions.
4. Reflect the same scope in the Zenodo Rights field and description.

Do not select a license in the Zenodo interface that falsely relicenses
third-party archive data or changes the MIT terms for the software. If Zenodo
allows multiple rights entries, add MIT and CC BY 4.0 and explain their scope.
If the interface permits only one prominent license, use the record description
and `LICENSES.md` to state the artifact-level license matrix unambiguously.

Do not change or broaden this license matrix during Zenodo entry without first
updating `LICENSES.md` and rebuilding the release.

## 6. Create the Zenodo Draft

1. Open `https://zenodo.org/` and sign in.
2. Connect ORCID under account settings if it is available and not already
   connected.
3. Select **New upload**.
4. Keep the record as a draft until every step below is complete.
5. Do not delete the draft after reserving a DOI; deleting it loses the
   reservation.

### 6.1 Select the resource type

For this release, use a software/research-compendium record rather than
pretending the archive DOI is the journal article DOI.

Recommended values:

- Resource type: **Software**.
- Title:
  `TOI-3492.01 Photometric Characterization: Reproducibility Package`.
- Version: `1.0.1`.
- Publication date: the actual date on which the Zenodo record will be
  published.
- Language: English.

The manuscript itself will be published through arXiv and, optionally, an AAS
journal. It may be included inside the reproducibility ZIP, but the Zenodo
record should remain clearly described as the supporting research compendium.

### 6.2 Enter creators

Use:

- Family name: `Şen`.
- Given name: `Furkan`.
- Affiliation: `Department of Astronomy and Space Sciences, Ankara University`.
- ORCID: enter the full ORCID iD if available.

Use the same spelling and ordering in Zenodo, ORCID, arXiv, the manuscript, and
future AAS metadata. ASCII `Sen` may remain where a machine format cannot safely
represent the Turkish character, but public metadata should use `Şen`.

### 6.3 Copy-ready Zenodo description

Use or adapt the following description without strengthening the scientific
claims:

```text
This record archives the version 1.0.1 reproducibility package supporting the
manuscript “TOI-3492.01: A Short-Period Giant Planet Candidate Orbiting an
Evolved F-type Subgiant.”

The release contains the canonical manuscript, compact frozen TESS light-curve
products, machine-readable analysis outputs, figures, provenance metadata,
SHA-256 manifests, the Python analysis pipeline, and executable offline tests.
Large raw TESS/SPOC files are not redistributed; their archive identifiers,
sizes, and hashes are supplied for independent retrieval and verification.

The supported scientific scope is a photometric characterization of an
unvalidated and unconfirmed transit candidate. No calibrated population
false-positive probability, dynamical confirmation, measured mass, or measured
eccentricity is claimed. The machine-readable claim boundary is recorded in
outputs/release_status.json.

Software is licensed under the MIT License. The original manuscript, original
figures, narrative documentation, and original derived tables are licensed
under the Creative Commons Attribution 4.0 International License (CC BY 4.0),
as detailed in LICENSES.md. Upstream mission and catalog products retain their
original terms and acknowledgement requirements.
```

### 6.4 Keywords and subjects

Recommended keywords:

- `exoplanets`
- `TESS`
- `transit photometry`
- `planet candidates`
- `TOI-3492.01`
- `TIC 81077799`
- `reproducible research`
- `stellar evolution`

Use an astronomy/exoplanet subject from Zenodo's controlled vocabulary if one
is available. Do not use `confirmed planet`, `validated planet`, or
`eccentric planet` as keywords.

### 6.5 Related identifiers

Before arXiv publication, add the GitHub repository as a related resource:

`https://github.com/shenfurkan/toi3492-characterization`

After arXiv assigns an identifier, edit the Zenodo metadata and add the arXiv
URL, for example `https://arxiv.org/abs/YYMM.NNNNN`, as the related manuscript.
After journal publication, add the publisher article DOI as another related
identifier.

Do not mark the Zenodo package as identical to the article. It supports or
supplements the article but is a distinct research object.

### 6.6 Funding and contributors

- Enter funding only when there is a real award or funder identifier.
- Do not invent a grant number.
- Add contributors only when their actual contribution and consent justify it.
- The authorship of the Zenodo deposit need not match the article exactly, but
  it must accurately represent contributions to the deposited artifact.

## 7. Reserve the Zenodo DOI

While the record is still a draft:

1. Find the **Digital Object Identifier** field.
2. Answer **No** to “Do you already have a DOI for this upload?” because this is
   a new research-compendium record.
3. Select **Get a DOI now!**.
4. Copy the reserved DOI exactly, including its `10.5281/zenodo...` prefix.
5. Store it temporarily outside public Git while it remains unresolved.
6. Do not delete the draft.

A reserved DOI may not resolve publicly until the Zenodo record is published.
That is expected, but it also means the identifier has not yet passed this
project's public DOI gate. Do not reuse the historical reservation without
confirming that it belongs to the corrected `v1.0.1` draft.

### 7.1 Files to update after public DOI verification

Only after the published DOI resolves to the intended record and the downloaded
files pass hash verification, update:

- `CITATION.cff`: add the release DOI and repository/archive URL.
- `README.md`: add an archived-release citation section.
- `toi3492_characterization.tex`: add a data and software availability
  statement citing the Zenodo DOI.
- `LICENSES.md`: record the final content-license grant.

Recommended manuscript text:

```text
Data and Software Availability. The version 1.0.1 reproducibility package
supporting this work is archived on Zenodo at
https://doi.org/10.5281/zenodo.XXXXXXX. It contains compact frozen light-curve
products, machine-readable outputs, figures, provenance metadata, SHA-256
manifests, analysis scripts, and executable offline tests. Large raw TESS/SPOC
products are available from MAST and are not redistributed; the release records
their archive identifiers, sizes, and hashes.
```

Replace `XXXXXXX` only with the verified public DOI. Do not use a placeholder or
an unresolved historical reservation in a package that will be published.

Recommended `CITATION.cff` additions:

```yaml
doi: "10.5281/zenodo.XXXXXXX"
url: "https://doi.org/10.5281/zenodo.XXXXXXX"
repository-code: "https://github.com/shenfurkan/toi3492-characterization"
```

Validate the YAML after editing. Keep `version: 1.0.1` synchronized with the
archive filename and Zenodo metadata.

Because adding a DOI changes manifest-listed files, regenerate the manifest,
release ZIP, and sidecar. If the DOI-free `v1.0.1` record is already immutable,
follow Zenodo's versioning rules rather than attempting to replace its files
silently.

## 8. Rebuild the Metadata-Bearing Release

Do not upload the current pre-DOI ZIP after modifying packaged metadata. Build
a new internally consistent archive.

Run all commands from the repository root, `D:\exoplanet`.

### 8.1 Confirm intended changes

```powershell
git status --short
git diff -- CITATION.cff README.md LICENSES.md toi3492_characterization.tex
```

Verify that no unsupported scientific claim was introduced. In particular,
search for validation, confirmation, FPP, eccentricity, and sigma wording.

### 8.2 Recompile the canonical manuscript

Run the complete bibliography cycle:

```powershell
pdflatex -interaction=nonstopmode -halt-on-error toi3492_characterization.tex
bibtex toi3492_characterization
pdflatex -interaction=nonstopmode -halt-on-error toi3492_characterization.tex
pdflatex -interaction=nonstopmode -halt-on-error toi3492_characterization.tex
```

Open `toi3492_characterization.pdf` and visually inspect:

- title and author;
- abstract;
- figures and captions;
- references;
- availability statement and, only if verified, the public DOI;
- page breaks and clipped content.

### 8.3 Run the scientific and publication gates

```powershell
python scripts/audit_science_consistency.py
python scripts/audit_manuscript_math.py
python -m pytest -q
```

Expected publication gate:

```text
SCIENTIFIC CONSISTENCY AND CLAIM-BOUNDARY AUDIT: PASS
MANUSCRIPT MATHEMATICS AUDIT: PASS
Math expressions inventoried: 276
Numeric tokens inventoried: 761
27 passed, 1 deselected
```

The exact count may increase when new tests are intentionally added, but no
test may fail.

If the re-downloadable raw SPOC FITS files are present, also run:

```powershell
python -m pytest -q -m integration -o addopts=""
```

The integration test is not required for an offline archive when the raw FITS
files are absent, but its omission must not be represented as a pass.

### 8.4 Commit the source state before the final manifest

For a formal release, commit the DOI, license, manuscript, and metadata changes
before generating the final provenance record. Inspect the diff and stage only
the intended files.

Do not use destructive Git commands. Do not amend or force-push solely to make
the history look cleaner.

After the intended release commit:

```powershell
git status --short
```

The command should produce no output before the final manifest is generated.

### 8.5 Generate provenance and packages

Run in this order:

```powershell
python scripts/generate_release_manifest.py
python scripts/build_arxiv_package.py
python scripts/build_release_package.py
```

The release builder performs all of the following:

- verifies every source file against `provenance/SHA256SUMS.json`;
- rejects duplicate or unsafe ZIP paths;
- checks ZIP CRC integrity;
- verifies every embedded file hash;
- extracts into a new empty temporary directory;
- runs the default offline test suite from the extracted archive;
- writes a new whole-archive SHA-256 sidecar.

Do not edit the ZIP manually after this command. Any manual change invalidates
the sidecar and the clean-room verification.

### 8.6 Verify the final local archive

Inspect the new sidecar:

```powershell
Get-Content .\toi3492_reproducible_release_v1.0.1.zip.sha256
```

Calculate the ZIP hash independently:

```powershell
Get-FileHash -Algorithm SHA256 .\toi3492_reproducible_release_v1.0.1.zip
```

The two hexadecimal hashes must match exactly, ignoring letter case.

Test both ZIP files:

```powershell
python -m zipfile -t arxiv_submission.zip
python -m zipfile -t toi3492_reproducible_release_v1.0.1.zip
```

Also confirm that `arxiv_submission.zip` contains only the canonical TeX file,
`references.bib`, and the six referenced figures. It must not contain local
paths, build logs, cached bytecode, chain files, literature PDFs, or secrets.

### 8.7 Tag the release

Use a signed tag if signing is already configured:

```powershell
git tag -s v1.0.1 -m "TOI-3492.01 reproducible release v1.0.1"
```

If signing is not configured, use an annotated tag rather than changing Git
configuration during release:

```powershell
git tag -a v1.0.1 -m "TOI-3492.01 reproducible release v1.0.1"
```

Push the commit and tag only after inspecting them:

```powershell
git show --stat v1.0.1
git push origin HEAD
git push origin v1.0.1
```

Do not recreate or move a public release tag. If a published artifact needs a
change, create a new release version.

## 9. Upload Files to the Zenodo Draft

Upload these as separate top-level files in the Zenodo record:

1. `toi3492_reproducible_release_v1.0.1.zip`
2. `toi3492_reproducible_release_v1.0.1.zip.sha256`
3. `README.md`
4. `LICENSES.md`

The ZIP already contains the canonical manuscript and release files. A separate
copy of `toi3492_characterization.pdf` is optional; if uploaded, clearly label
it as the manuscript associated with the reproducibility package and ensure it
is exactly the same final PDF referenced by the archive.

Do not upload:

- `papers/` literature PDFs;
- LaTeX `.aux`, `.log`, `.out`, `.blg`, or cache files;
- private email, endorsement codes, API tokens, or credentials;
- local raw TESS files that the compact release intentionally excludes;
- the former QA manuscript preserved only in
  `toi3492_legacy_material_20260722.zip`, which is noncanonical;
- obsolete outputs or unsupported-validation products outside the verified
  release ZIP.

After upload, compare the displayed filenames and sizes with the local files.
Do not rename only one side of the ZIP/sidecar pair.

## 10. Submit to the AAS Journals Zenodo Community

The official community is:

`https://zenodo.org/communities/aas`

In the Zenodo draft:

1. Open the Communities section.
2. Search for and select **AAS Journals**.
3. Submit the draft or record for community review using Zenodo's community
   review workflow.
4. Keep the record description complete; the community is not a substitute for
   file-level documentation.
5. Respond to curation requests by editing the draft before publication or by
   creating a new version if the record is already public.

Community inclusion and Zenodo publication are related but distinct states. Do
not claim that the AAS Journals Community has accepted or curated the record
until Zenodo displays that status.

For AAS data-curation questions, contact `data-editors@aas.org`. For manuscript
submission questions, contact `journals.manager@aas.org`.

### 10.1 Dual-anonymous journal review exception

If an AAS journal submission will use dual-anonymous review:

1. Do not publish an identifying Zenodo record solely to give reviewers data.
2. Create an unpublished, anonymized Zenodo draft.
3. Remove author-identifying filenames and metadata from the review copy.
4. Submit the draft to the AAS Journals Community for draft review.
5. Create a private Zenodo sharing link.
6. Place only that private sharing link in the anonymized manuscript.
7. Publish the named record only when the journal workflow permits it.

The current release and manuscript contain the author's identity, so they are
not suitable as-is for an anonymous-review package.

## 11. Final Zenodo Review Before Publishing

Treat **Publish** as an irreversible release gate. Before selecting it, confirm:

- [ ] Title identifies a reproducibility package, not a confirmed planet.
- [ ] Creator name, affiliation, and ORCID are correct.
- [ ] Version is `1.0.1` everywhere.
- [ ] Any DOI entered in public metadata resolves to this intended record; an
      unresolved reservation remains absent from public files.
- [ ] Publication date is correct.
- [ ] Description states unvalidated and unconfirmed candidate status.
- [ ] No FPP, confirmation, measured mass, or measured-eccentricity claim was
      introduced.
- [ ] License matrix is explicit and approved.
- [ ] Upstream-data terms are acknowledged.
- [ ] GitHub URL is correct.
- [ ] AAS Journals Community is selected or submitted for review as intended.
- [ ] ZIP and sidecar filenames match.
- [ ] Local SHA-256 verification passes.
- [ ] No confidential or copyrighted literature files are uploaded.
- [ ] The record is public rather than embargoed, unless there is a documented
      reason for an embargo.

Then select **Publish**.

Publishing activates the reserved DOI. Files in a published version should be
treated as immutable. Correct file content through a new Zenodo version rather
than silently replacing the archived version.

## 12. Verify the Public Zenodo Record

Do not stop after the web page says publication succeeded.

1. Open the DOI URL in a private/incognito browser window.
2. Confirm that it resolves to the intended public record.
3. Check title, creator, ORCID, affiliation, version, date, license, description,
   and community status.
4. Download the ZIP and `.sha256` sidecar from Zenodo into a new empty
   directory.
5. Verify the downloaded files, not the originals.

Example PowerShell verification in the download directory:

```powershell
$zip = ".\toi3492_reproducible_release_v1.0.1.zip"
$sidecar = ".\toi3492_reproducible_release_v1.0.1.zip.sha256"
$expected = ((Get-Content $sidecar).Trim() -split "\s+")[0].ToLower()
$actual = (Get-FileHash -Algorithm SHA256 $zip).Hash.ToLower()
if ($actual -ne $expected) { throw "Zenodo download SHA-256 mismatch" }
python -m zipfile -t $zip
```

Record both identifiers:

- Version DOI: identifies exactly `v1.0.1`.
- Concept/all-versions DOI: identifies the evolving project, if Zenodo displays
  one.

Use the version DOI in the manuscript availability statement for this exact
release.

## 13. Obtain arXiv Endorsement

Zenodo publication and a DOI do not remove arXiv's first-submission endorsement
requirement.

1. Register or sign in at `https://arxiv.org/`.
2. Use an institutional Ankara University email if available.
3. Connect or claim existing arXiv-authored papers if applicable.
4. Start a new submission.
5. Select primary category `astro-ph.EP`.
6. Wait for arXiv's endorsement-request email.
7. Copy the generated private endorsement link/code.
8. Send it to one suitable endorser you know or whose work is directly relevant.
9. Attach the final manuscript PDF or provide a private manuscript link.
10. Do not mass-email potential endorsers or repeatedly pressure one person.

An eligible endorser can be found from a relevant recent arXiv abstract page by
using the **Which authors of this paper are endorsers?** link. Prefer an adviser,
departmental academic, collaborator, or directly relevant established author.

### 13.1 Copy-ready endorsement email

```text
Subject: Request for arXiv endorsement in astro-ph.EP - TOI-3492.01

Dear Professor [Surname],

My name is Furkan Şen, and I am affiliated with the Department of Astronomy
and Space Sciences at Ankara University.

I am preparing my first arXiv submission in the astro-ph.EP category. The
manuscript is entitled:

“TOI-3492.01: A Short-Period Giant Planet Candidate Orbiting an Evolved F-type
Subgiant”

The study presents a reproducible and conservative photometric
characterization of TOI-3492.01 using public TESS and catalog data. The object
is explicitly presented as an unvalidated and unconfirmed transit candidate;
the manuscript does not claim statistical validation or dynamical
confirmation.

Because this is my first submission in astro-ph.EP, arXiv requires an
endorsement from an established author in the field.

Endorsement link/code:
[PASTE THE PRIVATE ARXIV ENDORSEMENT LINK OR CODE HERE]

I have attached the manuscript for your consideration. I would be grateful if
you could endorse my submission if you find it appropriate for the astro-ph.EP
category. Please feel no obligation if you are unable to do so.

ORCID: [YOUR ORCID]
Institutional profile: [OPTIONAL LINK]

Thank you for your time and consideration.

Best regards,

Furkan Şen
Department of Astronomy and Space Sciences
Ankara University
Email: [YOUR INSTITUTIONAL EMAIL]
```

Replace every bracketed field. Never commit or publish the completed email with
the active endorsement code.

### 13.2 If the problem is technical rather than endorsement

Use arXiv's official contact route and include the complete error, account email,
category, submission ID, and screenshot. Do not send a password.

```text
Subject: Unable to complete first submission to astro-ph.EP

Dear arXiv Support,

I am unable to complete my first submission to the astro-ph.EP category.

Name: Furkan Şen
Account email: [ACCOUNT EMAIL]
Institution: Ankara University
Submission ID, if available: [SUBMISSION ID]
Category: astro-ph.EP

The exact message shown by the submission system is:

[PASTE THE COMPLETE ERROR MESSAGE HERE]

I have attached a screenshot of the error. Could you please clarify whether
this is an endorsement, account-verification, or technical submission issue?

Thank you for your assistance.

Best regards,
Furkan Şen
```

## 14. Submit to arXiv

Use `arxiv_submission.zip`, not the full reproducibility ZIP. arXiv prefers TeX
source and does not want a PDF generated from available TeX source submitted in
place of that source.

### 14.1 Submission metadata

Recommended values:

- Primary category: `astro-ph.EP`.
- Cross-list: none by default; add `astro-ph.SR` only if independently justified
  by the manuscript's stellar content and accepted by arXiv moderation.
- Title: `TOI-3492.01: Photometric Characterization of an Unvalidated and
  Unconfirmed Transit Candidate`.
- Author: `Furkan Şen`.
- Comments before DOI verification: use the final page and figure counts plus
  `photometric characterization of an unvalidated and unconfirmed transit candidate`.
- Add `reproducibility package available on Zenodo at [DOI URL]` only after the
  public DOI and downloaded package have been verified.
- Journal reference: leave blank until there is a real journal publication.
- Article DOI: leave blank until a publisher assigns an article DOI.

Paste the abstract from the final manuscript and check that TeX macros render
correctly in arXiv metadata.

### 14.2 Upload and compile

1. Select **Start New Submission**.
2. Select CC BY 4.0 for the manuscript, consistent with the author's explicit
   content-license grant recorded in `LICENSES.md`.
3. Upload `arxiv_submission.zip`.
4. Let arXiv detect `toi3492_characterization.tex` as the top-level file.
5. Select PDFLaTeX if it is not detected correctly.
6. Inspect arXiv's file warnings before accepting deletions.
7. Compile.
8. Read the compilation log for missing files, undefined citations, and
   undefined references.
9. Open arXiv's generated PDF and compare it with the final local PDF.
10. Verify all final figures, bibliography, author name, availability statement,
    final page count, and any DOI only if it has passed the public gate.
11. Complete metadata and preview the abstract page.
12. Select **Submit Article** only after the preview is correct.

Windows is case-insensitive but arXiv is case-sensitive. Figure filenames in
the TeX source must match the ZIP entries exactly, including capitalization.

### 14.3 After arXiv submission

- Save the submission ID and confirmation email.
- Moderation may delay announcement; submission is not public until announced.
- If an error is found before announcement, use **Unsubmit**, fix the existing
  submission, and resubmit it. Do not create a duplicate submission.
- After announcement, record the permanent arXiv identifier.
- Add the arXiv URL to Zenodo related identifiers.
- Add the Zenodo DOI to the arXiv comments only if the interface permits an
  accurate supporting-artifact reference; do not misuse the article DOI field.
- For later corrections, submit a replacement version to the same arXiv record.

## 15. Submit Separately to an AAS Journal

The AAS manuscript portal is:

`https://aas.msubmit.net/cgi-bin/main.plex`

Do not send `arxiv_submission.zip` to the AAS Journals Zenodo Community as a
substitute for journal submission. The objects have separate destinations:

| Object | Destination |
|---|---|
| Reproducibility ZIP, checksum, README, licenses | Zenodo, optionally curated by the AAS Journals Community |
| Preprint source and figures | arXiv |
| Journal manuscript, figures, cover letter, submission metadata | AAS manuscript portal |

### 15.1 Prepare the AAS manuscript

The current canonical manuscript is designed for the preprint release. Before
an AAS journal submission:

1. Select the appropriate AAS journal based on scope, not only speed.
2. Read that journal's current author instructions and pre-submission checklist.
3. Convert the manuscript to the current supported AASTeX class and format.
4. Preserve the conservative candidate terminology during conversion.
5. Include the Zenodo version DOI in the Data and Software Availability section
   only after it resolves to the verified corrected record.
6. Prepare machine-readable tables when required.
7. Ensure figures meet journal format, resolution, accessibility, and labeling
   requirements.
8. Prepare author ORCID, affiliation, funding, acknowledgements, conflicts,
   suggested reviewers, and cover letter.
9. Decide whether review is single-anonymous or dual-anonymous before exposing
   identity through review-only links.
10. Upload through the AAS portal and answer all submission questions
    accurately.

The AAS journal article DOI is assigned by the publisher after acceptance and
publication. It cannot be obtained by uploading the project to the AAS Zenodo
Community.

### 15.2 Data and software handling for AAS

AAS Journals encourage persistent repositories for code and related artifacts.
The Zenodo record should therefore be cited formally in the manuscript's
reference list or availability statement according to the selected journal's
instructions.

If the journal requests Data Behind the Figure material, prepare one documented
archive per figure as instructed by the AAS Data Guide. Do not automatically
upload raw NASA archive products that are already publicly available; cite the
archive and provide identifiers instead.

## 16. Metadata Updates After Publication

### 16.1 After arXiv announcement

Update Zenodo metadata with:

- the arXiv URL;
- the arXiv identifier;
- a relation indicating that the Zenodo record supports the manuscript.

Metadata-only corrections may be possible without changing archived files.
Do not create a new version merely to alter punctuation unless Zenodo requires
it. If the archived file content changes, create a new version.

### 16.2 After journal acceptance and publication

1. Add the journal citation and publisher DOI to the arXiv record through
   arXiv's journal reference/DOI update feature.
2. Add the publisher DOI and journal relation to Zenodo metadata.
3. Update the GitHub README and `CITATION.cff` on the development branch.
4. If peer review changes the archived files or scientific results, issue a new
   Zenodo release version and arXiv replacement rather than altering `v1.0.1`.
5. Preserve the old Zenodo version; do not delete the scholarly record simply
   because a newer version exists.

## 17. Versioning and Correction Policy

Use semantic release versions for the reproducibility package:

- `1.0.1`: documentation, metadata, or packaging correction with no scientific
  result change.
- `1.1.0`: backward-compatible new analysis or expanded diagnostics.
- `2.0.0`: material scientific/model change or incompatible pipeline redesign.

Every new Zenodo version must include:

- a new immutable ZIP;
- a matching new SHA-256 sidecar;
- updated `CITATION.cff`;
- updated `outputs/release_status.json` when claim gates change;
- updated `currentproblem.md` explaining the decision and phase status;
- rerun tests and clean-room verification;
- a new Git tag matching the package version.

Use an arXiv replacement for corrections to the same paper. Do not make a new
arXiv submission for a corrected version of the same work.

## 18. Stop Conditions

Stop and do not publish when any of the following is true:

- content licensing is unresolved;
- an unresolved or mismatched DOI appears in Zenodo, CFF, README, or manuscript;
- the local ZIP hash does not match its sidecar;
- the downloaded Zenodo ZIP hash does not match its sidecar;
- the default offline tests fail;
- the scientific consistency audit fails;
- arXiv's generated PDF differs materially from the local final PDF;
- a file path, private token, endorsement code, or personal credential is
  present in a public archive;
- metadata calls TOI-3492.01 validated, confirmed, or eccentric;
- the selected AAS review mode conflicts with a public identifying deposit;
- uploaded files differ from the files that were tested and tagged.

If a problem appears after Zenodo publication, do not silently replace files.
Document it and publish a corrected version. If a problem appears before arXiv
announcement, unsubmit and correct the existing submission.

## 19. Fast Path Checklist

This compact checklist is only for use after reading the full runbook.

### Zenodo

- [x] Approve and record the content license: CC BY 4.0 for original content;
      MIT for software.
- [ ] Create Software record draft.
- [ ] Enter creator, ORCID, affiliation, version, description, and keywords.
- [ ] Reserve a DOI only for the intended corrected draft and keep it private
      while unresolved.
- [ ] Recompile, audit, test, manifest, and rebuild the `v1.0.1` package.
- [ ] Commit and tag exact release source.
- [ ] Upload ZIP, sidecar, README, and LICENSES.
- [ ] Select/submit to AAS Journals Community.
- [ ] Review preview and publish.
- [ ] Download and verify public ZIP hash.
- [ ] Only after public verification, add the DOI consistently to CFF, README,
      manuscript, and applicable submission metadata.

### arXiv

- [ ] Start `astro-ph.EP` submission.
- [ ] Obtain endorsement request if required.
- [ ] Send one personalized endorsement email.
- [ ] Upload `arxiv_submission.zip`.
- [ ] Check top-level TeX and PDFLaTeX.
- [ ] Inspect log and generated PDF.
- [ ] Complete conservative metadata.
- [ ] Leave journal DOI blank.
- [ ] Submit and save the identifier.
- [ ] Add arXiv relation to Zenodo.

### AAS journal

- [ ] Choose journal and review mode.
- [ ] Convert to current AASTeX format.
- [ ] Cite the Zenodo version DOI.
- [ ] Prepare journal-specific files and metadata.
- [ ] Submit manuscript through the AAS portal.
- [ ] Do not confuse AAS Community curation with journal submission.
- [ ] After publication, connect article DOI, arXiv, Zenodo, and GitHub records.

## 20. Official References

Check these pages again immediately before submission because interfaces and
policies can change:

- Zenodo DOI reservation:
  `https://help.zenodo.org/docs/deposit/describe-records/reserve-doi/`
- AAS Journals Zenodo Community:
  `https://zenodo.org/communities/aas`
- AAS Journals Data Guide:
  `https://journals.aas.org/data-guide/`
- AAS manuscript submission:
  `https://journals.aas.org/submission/`
- AAS submission portal:
  `https://aas.msubmit.net/cgi-bin/main.plex`
- arXiv endorsement guidance:
  `https://info.arxiv.org/help/endorsement.html`
- arXiv submission guidance:
  `https://info.arxiv.org/help/submit/`
- arXiv contact route:
  `https://info.arxiv.org/help/contact.html`
