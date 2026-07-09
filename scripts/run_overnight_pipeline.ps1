param(
    [string]$RunId = "",
    [int]$TriceratopsDraws = 50000,
    [int]$TriceratopsStressDraws = 100000,
    [bool]$RunStressTriceratops = $true,
    [bool]$CompileLatex = $true,
    [int]$CoolDownSeconds = 60,
    [int]$DefaultTimeoutMinutes = 180,
    [switch]$DryRun,
    [switch]$AllowApproximateLimbDarkening
)

$ErrorActionPreference = "Stop"

$Root = (Resolve-Path -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath "..")).Path
Set-Location -LiteralPath $Root

if ([string]::IsNullOrWhiteSpace($RunId)) {
    $RunId = Get-Date -Format "yyyyMMdd_HHmmss"
}

$RunDir = Join-Path -Path $Root -ChildPath ("outputs\night_runs\" + $RunId)
$LogDir = Join-Path -Path $RunDir -ChildPath "logs"
$SnapshotDir = Join-Path -Path $RunDir -ChildPath "snapshots"
$MasterLog = Join-Path -Path $RunDir -ChildPath "master.log"
$StepCsv = Join-Path -Path $RunDir -ChildPath "steps.csv"
$StepJson = Join-Path -Path $RunDir -ChildPath "steps.json"
$SummaryMd = Join-Path -Path $RunDir -ChildPath "morning_summary.md"

foreach ($dir in @($RunDir, $LogDir, $SnapshotDir)) {
    if (-not (Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }
}

Set-Content -LiteralPath (Join-Path -Path $Root -ChildPath "outputs\night_runs\latest_run.txt") -Value $RunId -Encoding ASCII

$script:StepIndex = 0
$script:StepResults = @()
$script:NonCriticalFailures = 0
$script:TimeoutFailures = 0
$script:ExecutionStateEnabled = $false

function Write-Log {
    param([string]$Message)
    $line = "[{0}] {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $Message
    Write-Host $line
    Add-Content -LiteralPath $MasterLog -Value $line -Encoding ASCII
}

function Enable-KeepAwake {
    if ($DryRun) {
        Write-Log "DryRun: keep-awake guard not enabled."
        return
    }

    try {
        Add-Type @"
using System;
using System.Runtime.InteropServices;
public static class OvernightExecutionState {
    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern uint SetThreadExecutionState(uint esFlags);
    public const uint ES_CONTINUOUS = 0x80000000;
    public const uint ES_SYSTEM_REQUIRED = 0x00000001;
    public const uint ES_DISPLAY_REQUIRED = 0x00000002;
}
"@
        [void][OvernightExecutionState]::SetThreadExecutionState(
            [OvernightExecutionState]::ES_CONTINUOUS -bor
            [OvernightExecutionState]::ES_SYSTEM_REQUIRED -bor
            [OvernightExecutionState]::ES_DISPLAY_REQUIRED
        )
        $script:ExecutionStateEnabled = $true
        Write-Log "Keep-awake guard enabled for system + display."
    }
    catch {
        Write-Log "WARNING: could not enable keep-awake guard: $($_.Exception.Message)"
    }
}

function Disable-KeepAwake {
    if ($script:ExecutionStateEnabled) {
        try {
            [void][OvernightExecutionState]::SetThreadExecutionState([OvernightExecutionState]::ES_CONTINUOUS)
            Write-Log "Keep-awake guard released."
        }
        catch {
            Write-Log "WARNING: could not release keep-awake guard: $($_.Exception.Message)"
        }
    }
}

function Resolve-Executable {
    param(
        [string]$Name,
        [string[]]$Fallbacks = @()
    )

    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    foreach ($fallback in $Fallbacks) {
        if (-not [string]::IsNullOrWhiteSpace($fallback) -and (Test-Path -LiteralPath $fallback)) {
            return $fallback
        }
    }

    return $null
}

function Add-StepResult {
    param(
        [string]$Name,
        [string]$Status,
        [int]$ExitCode,
        [double]$DurationMinutes,
        [string]$StdoutLog,
        [string]$StderrLog,
        [string]$Note
    )

    $script:StepResults += [pscustomobject]@{
        index = $script:StepIndex
        name = $Name
        status = $Status
        exit_code = $ExitCode
        duration_minutes = [math]::Round($DurationMinutes, 3)
        stdout_log = $StdoutLog
        stderr_log = $StderrLog
        note = $Note
    }

    $script:StepResults | Export-Csv -LiteralPath $StepCsv -NoTypeInformation -Encoding ASCII
    $script:StepResults | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $StepJson -Encoding ASCII
}

function Get-SafeName {
    param([string]$Name)
    return ($Name -replace '[^A-Za-z0-9_.-]+', '_').Trim('_')
}

function Invoke-LoggedCommand {
    param(
        [string]$Name,
        [string]$FilePath,
        [string[]]$ArgumentList = @(),
        [int]$TimeoutMinutes = $DefaultTimeoutMinutes,
        [bool]$Critical = $true,
        [bool]$IgnoreFailure = $false,
        [bool]$CoolDown = $false,
        [string]$WorkingDirectory = $Root
    )

    $script:StepIndex += 1
    $safe = Get-SafeName $Name
    $stdout = Join-Path -Path $LogDir -ChildPath ("{0:D2}_{1}.stdout.log" -f $script:StepIndex, $safe)
    $stderr = Join-Path -Path $LogDir -ChildPath ("{0:D2}_{1}.stderr.log" -f $script:StepIndex, $safe)
    $displayArgs = ($ArgumentList -join " ")

    Write-Log ("STEP {0:D2}: {1}" -f $script:StepIndex, $Name)
    Write-Log ("Command: {0} {1}" -f $FilePath, $displayArgs)

    if ($DryRun) {
        Set-Content -LiteralPath $stdout -Value "DryRun: command not executed." -Encoding ASCII
        Set-Content -LiteralPath $stderr -Value "" -Encoding ASCII
        Add-StepResult -Name $Name -Status "DRYRUN" -ExitCode 0 -DurationMinutes 0 -StdoutLog $stdout -StderrLog $stderr -Note "not executed"
        return $true
    }

    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $exitCode = -1
    $status = "FAILED"
    $note = ""

    try {
        $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -WorkingDirectory $WorkingDirectory -RedirectStandardOutput $stdout -RedirectStandardError $stderr -PassThru
        $timeoutMs = [int]($TimeoutMinutes * 60 * 1000)
        $finished = $process.WaitForExit($timeoutMs)
        if (-not $finished) {
            $script:TimeoutFailures += 1
            $note = "timeout after $TimeoutMinutes minutes"
            Write-Log "TIMEOUT: $Name exceeded $TimeoutMinutes minutes; killing process."
            try {
                Stop-Process -Id $process.Id -Force -ErrorAction SilentlyContinue
            }
            catch {
            }
            $exitCode = -999
            $status = "TIMEOUT"
        }
        else {
            $exitCode = [int]$process.ExitCode
            if ($exitCode -eq 0) {
                $status = "OK"
                $note = ""
            }
            else {
                $status = "FAILED"
                $note = "exit code $exitCode"
            }
        }

        if ($status -eq "OK" -and (Test-Path -LiteralPath $stderr)) {
            $stderrText = Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue
            if ($stderrText -match "Traceback \(most recent call last\)") {
                $status = "FAILED"
                $exitCode = -996
                $note = "python traceback detected in stderr"
            }
        }
    }
    catch {
        $status = "FAILED"
        $note = $_.Exception.Message
        $exitCode = -998
    }
    finally {
        $sw.Stop()
    }

    Add-StepResult -Name $Name -Status $status -ExitCode $exitCode -DurationMinutes $sw.Elapsed.TotalMinutes -StdoutLog $stdout -StderrLog $stderr -Note $note

    if ($status -eq "OK") {
        Write-Log ("OK: {0} finished in {1:n1} min" -f $Name, $sw.Elapsed.TotalMinutes)
    }
    else {
        Write-Log ("{0}: {1} ({2})" -f $status, $Name, $note)
        if (Test-Path -LiteralPath $stderr) {
            $tail = Get-Content -LiteralPath $stderr -Tail 12 -ErrorAction SilentlyContinue
            if ($tail) {
                Write-Log "Last stderr lines:"
                foreach ($line in $tail) {
                    Write-Log ("  " + $line)
                }
            }
        }
        if ($Critical -and -not $IgnoreFailure) {
            throw "Critical step failed: $Name ($note)"
        }
        $script:NonCriticalFailures += 1
    }

    if ($CoolDown -and $CoolDownSeconds -gt 0 -and -not $DryRun) {
        Write-Log "Cooling down for $CoolDownSeconds seconds."
        Start-Sleep -Seconds $CoolDownSeconds
    }

    return ($status -eq "OK")
}

function Invoke-PythonScript {
    param(
        [string]$Name,
        [string]$ScriptPath,
        [string[]]$Arguments = @(),
        [int]$TimeoutMinutes = $DefaultTimeoutMinutes,
        [bool]$Critical = $true,
        [bool]$IgnoreFailure = $false,
        [bool]$CoolDown = $false
    )

    $fullPath = Join-Path -Path $Root -ChildPath $ScriptPath
    if (-not (Test-Path -LiteralPath $fullPath)) {
        $script:StepIndex += 1
        $safe = Get-SafeName $Name
        $stdout = Join-Path -Path $LogDir -ChildPath ("{0:D2}_{1}.stdout.log" -f $script:StepIndex, $safe)
        $stderr = Join-Path -Path $LogDir -ChildPath ("{0:D2}_{1}.stderr.log" -f $script:StepIndex, $safe)
        Set-Content -LiteralPath $stdout -Value "Missing script: $ScriptPath" -Encoding ASCII
        Set-Content -LiteralPath $stderr -Value "" -Encoding ASCII
        Add-StepResult -Name $Name -Status "MISSING" -ExitCode -997 -DurationMinutes 0 -StdoutLog $stdout -StderrLog $stderr -Note "missing $ScriptPath"
        Write-Log "MISSING: $ScriptPath"
        if ($Critical -and -not $IgnoreFailure) {
            throw "Missing critical script: $ScriptPath"
        }
        $script:NonCriticalFailures += 1
        return $false
    }

    $args = @($ScriptPath) + $Arguments
    return Invoke-LoggedCommand -Name $Name -FilePath $script:PythonExe -ArgumentList $args -TimeoutMinutes $TimeoutMinutes -Critical $Critical -IgnoreFailure $IgnoreFailure -CoolDown $CoolDown
}

function Backup-CurrentOutputs {
    if ($DryRun) {
        Write-Log "DryRun: backup skipped."
        return
    }

    $backupDir = Join-Path -Path $RunDir -ChildPath "backup_before"
    if (-not (Test-Path -LiteralPath $backupDir)) {
        New-Item -ItemType Directory -Path $backupDir | Out-Null
    }

    $patterns = @(
        "data\config*.json",
        "data\toi3492_120s_reference.csv",
        "data\toi3492_*chain*.npy",
        "outputs\*.json",
        "outputs\*.csv",
        "figures\*.png",
        "arxiv_main.tex",
        "references.bib"
    )

    $count = 0
    foreach ($pattern in $patterns) {
        $items = Get-ChildItem -Path (Join-Path -Path $Root -ChildPath $pattern) -File -ErrorAction SilentlyContinue
        foreach ($item in $items) {
            $relative = $item.FullName.Substring($Root.Length).TrimStart('\')
            $destName = $relative -replace '[\\/:]+', '__'
            Copy-Item -LiteralPath $item.FullName -Destination (Join-Path -Path $backupDir -ChildPath $destName) -Force
            $count += 1
        }
    }

    Write-Log "Backed up $count existing outputs to $backupDir"
}

function Snapshot-CoreOutputs {
    param([string]$Label)

    if ($DryRun) {
        return
    }

    $dest = Join-Path -Path $SnapshotDir -ChildPath (Get-SafeName $Label)
    if (-not (Test-Path -LiteralPath $dest)) {
        New-Item -ItemType Directory -Path $dest | Out-Null
    }

    $files = @(
        "data\config.json",
        "data\config_corrected_120s.json",
        "outputs\mcmc_diagnostics_120s_corrected.json",
        "outputs\transit_fit_120s_density_locked.json",
        "outputs\transit_fit_120s_eccentric.json",
        "outputs\false_positive_tests_120s.json",
        "outputs\gaia_contamination_check.json",
        "outputs\dilution_corrected_transit_params.json",
        "outputs\tess_source_localization_120s.json",
        "outputs\spoc_dv_summary.json",
        "outputs\spoc_vs_local_comparison.json",
        "outputs\ttv_analysis_120s.json",
        "outputs\statistical_validation_120s.json",
        "outputs\triceratops_validation_120s.json"
    )

    foreach ($rel in $files) {
        $src = Join-Path -Path $Root -ChildPath $rel
        if (Test-Path -LiteralPath $src) {
            $destName = $rel -replace '[\\/:]+', '__'
            Copy-Item -LiteralPath $src -Destination (Join-Path -Path $dest -ChildPath $destName) -Force
        }
    }
}

function Write-ScienceCheck {
    param([string]$Label)

    $out = Join-Path -Path $RunDir -ChildPath ("science_check_{0}.txt" -f (Get-SafeName $Label))
    $lines = @()
    $lines += "Science check: $Label"
    $lines += "Created: $(Get-Date -Format o)"

    $configPath = Join-Path -Path $Root -ChildPath "data\config_corrected_120s.json"
    if (-not (Test-Path -LiteralPath $configPath)) {
        $lines += "Missing data\config_corrected_120s.json"
        Set-Content -LiteralPath $out -Value $lines -Encoding ASCII
        return
    }

    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $s = $config.stellar
    $t = $config.transit
    $tc = $config.transit_corrected_120s

    $depthCalc = [math]::Pow([double]$t.rp_rs, 2.0) * 1000000.0
    $rpCalc = [double]$t.rp_rs * [double]$s.r_star * 109.1
    $gMsun = 2942.2062
    $arPred = [math]::Pow($gMsun * [double]$s.m_star * [math]::Pow([double]$t.period, 2.0) / (4.0 * [math]::Pow([math]::PI, 2.0)), 1.0 / 3.0) / [double]$s.r_star

    $arPrior = $arPred
    $arPriorSigma = 0.5
    if ($tc -and $tc.PSObject.Properties.Name -contains "a_rs_prior") {
        $arPrior = [double]$tc.a_rs_prior
        $arPriorSigma = [double]$tc.a_rs_prior_sigma
    }
    $tension = ([double]$t.a_rs - $arPrior) / [math]::Sqrt([math]::Pow([double]$t.a_rs_err, 2.0) + [math]::Pow($arPriorSigma, 2.0))

    $lines += ("Teff/logg/R/M: {0:n0} K / {1:n3} / {2:n4} Rsun / {3:n4} Msun" -f [double]$s.teff, [double]$s.logg, [double]$s.r_star, [double]$s.m_star)
    $lines += ("LD: u1={0:n6}, u2={1:n6}, source={2}" -f [double]$config.limb_darkening.u1, [double]$config.limb_darkening.u2, [string]$config.limb_darkening.source)
    $lines += ("Rp/Rs={0:n8} +/- {1:n8}" -f [double]$t.rp_rs, [double]$t.rp_rs_err)
    $lines += ("Depth stored={0:n3} ppm; recalculated={1:n3} ppm; delta={2:n3} ppm" -f [double]$t.depth_ppm, $depthCalc, ([double]$t.depth_ppm - $depthCalc))
    $lines += ("Rp stored={0:n4} Rearth; recalculated={1:n4} Rearth; delta={2:n4}" -f [double]$t.rp_earth, $rpCalc, ([double]$t.rp_earth - $rpCalc))
    $lines += ("a/Rs fitted={0:n4} +/- {1:n4}; Kepler={2:n4}; prior={3:n4} +/- {4:n4}; tension={5:n3} sigma" -f [double]$t.a_rs, [double]$t.a_rs_err, $arPred, $arPrior, $arPriorSigma, $tension)
    $lines += ("b={0:n4}; inc={1:n4} deg; duration={2:n4} hr" -f [double]$t.impact_parameter, [double]$t.inc, [double]$t.duration_hrs)

    $diagPath = Join-Path -Path $Root -ChildPath "outputs\mcmc_diagnostics_120s_corrected.json"
    if (Test-Path -LiteralPath $diagPath) {
        $diag = Get-Content -LiteralPath $diagPath -Raw | ConvertFrom-Json
        $tauText = (($diag.autocorr_time_steps | ForEach-Object { "{0:n2}" -f [double]$_ }) -join ", ")
        $lines += ("MCMC acceptance={0:n5}; 50tau={1}; tau=[{2}]" -f [double]$diag.acceptance_fraction_mean, [string]$diag.autocorr_reliable_50tau_rule, $tauText)
    }

    $fppPath = Join-Path -Path $Root -ChildPath "outputs\statistical_validation_120s.json"
    if (Test-Path -LiteralPath $fppPath) {
        $fpp = Get-Content -LiteralPath $fppPath -Raw | ConvertFrom-Json
        $lines += ("Simplified FPP={0:n6}% ; a/Rstar caveat sigma={1:n3}" -f [double]$fpp.FPP_percent, [double]$fpp.aRstar_tension_sigma)
    }

    $triPath = Join-Path -Path $Root -ChildPath "outputs\triceratops_validation_120s.json"
    if (Test-Path -LiteralPath $triPath) {
        $tri = Get-Content -LiteralPath $triPath -Raw | ConvertFrom-Json
        $tp = $null
        if ($tri.scenario_probabilities -and $tri.scenario_probabilities.PSObject.Properties.Name -contains "TP") {
            $tp = [double]$tri.scenario_probabilities.TP
        }
        $lines += ("TRICERATOPS N={0}; FPP={1}; TP={2}" -f [int]$tri.n_draws, [double]$tri.FPP, $tp)
    }

    Set-Content -LiteralPath $out -Value $lines -Encoding ASCII
    foreach ($line in $lines) {
        Write-Log $line
    }
}

function Assert-ScienceRanges {
    $configPath = Join-Path -Path $Root -ChildPath "data\config_corrected_120s.json"
    $diagPath = Join-Path -Path $Root -ChildPath "outputs\mcmc_diagnostics_120s_corrected.json"
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $t = $config.transit

    $problems = @()
    if ([double]$t.rp_rs -lt 0.052 -or [double]$t.rp_rs -gt 0.061) { $problems += "Rp/Rs outside expected range" }
    if ([double]$t.depth_ppm -lt 2900 -or [double]$t.depth_ppm -gt 3500) { $problems += "depth outside expected range" }
    if ([double]$t.rp_earth -lt 14.0 -or [double]$t.rp_earth -gt 18.0) { $problems += "Rp outside expected range" }
    if ([double]$t.a_rs -lt 8.0 -or [double]$t.a_rs -gt 10.5) { $problems += "a/Rs outside expected range" }

    if (Test-Path -LiteralPath $diagPath) {
        $diag = Get-Content -LiteralPath $diagPath -Raw | ConvertFrom-Json
        if ([double]$diag.acceptance_fraction_mean -lt 0.45 -or [double]$diag.acceptance_fraction_mean -gt 0.75) { $problems += "MCMC acceptance outside expected range" }
        if (-not [bool]$diag.autocorr_reliable_50tau_rule) { $problems += "MCMC 50tau rule failed" }
    }
    else {
        $problems += "missing MCMC diagnostics"
    }

    if ($problems.Count -gt 0) {
        throw ("Science range guard failed: " + ($problems -join "; "))
    }
    Write-Log "Science range guard passed."
}

function Assert-LimbDarkeningSource {
    if ($AllowApproximateLimbDarkening) {
        Write-Log "Approximate limb darkening explicitly allowed."
        return
    }

    $configPath = Join-Path -Path $Root -ChildPath "data\config.json"
    $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
    $source = [string]$config.limb_darkening.source
    if ($source -match "Approximate") {
        throw "Limb-darkening fell back to approximate values; rerun later or use -AllowApproximateLimbDarkening intentionally."
    }
    Write-Log "Limb-darkening source guard passed: $source"
}

function Write-RunSummaryMarkdown {
    $lines = @()
    $lines += "# Overnight Pipeline Summary"
    $lines += ""
    $lines += "Run ID: $RunId"
    $lines += "Started/finished: see master.log"
    $lines += "Non-critical failures: $script:NonCriticalFailures"
    $lines += "Timeouts: $script:TimeoutFailures"
    $lines += ""
    $lines += "## Key Files"
    $lines += "- Master log: master.log"
    $lines += "- Step table: steps.csv"
    $lines += "- Science checks: science_check_before.txt, science_check_after_main_fit.txt, science_check_final.txt"
    $lines += "- Backup: backup_before/"
    $lines += "- Snapshots: snapshots/"
    $lines += ""
    $lines += "## Step Results"
    $lines += ""
    $lines += "| # | Step | Status | Minutes | Note |"
    $lines += "|---:|---|---|---:|---|"
    foreach ($step in $script:StepResults) {
        $lines += ("| {0} | {1} | {2} | {3:n2} | {4} |" -f $step.index, $step.name, $step.status, [double]$step.duration_minutes, $step.note)
    }
    $lines += ""
    $lines += "## Interpretation Reminder"
    $lines += ""
    $lines += "TOI-3492.01 remains a candidate. TRICERATOPS and FPP results are screening evidence, not RV confirmation."
    Set-Content -LiteralPath $SummaryMd -Value $lines -Encoding ASCII
}

try {
    Write-Log "Run directory: $RunDir"
    Write-Log "Root: $Root"
    Write-Log "DryRun: $DryRun"

    $env:OMP_NUM_THREADS = "1"
    $env:MKL_NUM_THREADS = "1"
    $env:OPENBLAS_NUM_THREADS = "1"
    $env:NUMEXPR_NUM_THREADS = "1"
    $env:PYTHONPATH = (Join-Path -Path $Root -ChildPath "scripts") + ";" + $env:PYTHONPATH
    Write-Log "Thread limits set to 1 for BLAS/OpenMP-heavy libraries."

    Enable-KeepAwake

    $script:PythonExe = Resolve-Executable -Name "python.exe" -Fallbacks @("python")
    if (-not $script:PythonExe) {
        throw "python.exe not found in PATH"
    }
    Write-Log "Python executable: $script:PythonExe"

    $battery = Get-WmiObject -Class Win32_Battery -ErrorAction SilentlyContinue
    if ($battery) {
        $statuses = @($battery | ForEach-Object { $_.BatteryStatus })
        $acLikely = $false
        foreach ($status in $statuses) {
            if ($status -in @(2, 6, 7, 8, 9)) { $acLikely = $true }
        }
        if ($acLikely) {
            Write-Log "Battery check: AC/charging status detected."
        }
        else {
            Write-Log "WARNING: AC power not clearly detected. Plug in before leaving the laptop."
        }
    }
    else {
        Write-Log "Battery check: no battery object returned; desktop/driver may not expose it."
    }

    $driveName = (Split-Path -Qualifier $Root).TrimEnd(':')
    $drive = Get-PSDrive -Name $driveName -ErrorAction SilentlyContinue
    if ($drive) {
        Write-Log ("Free disk on {0}: {1:n1} GB" -f $driveName, ($drive.Free / 1GB))
        if ($drive.Free -lt 5GB) {
            throw "Less than 5 GB free disk space."
        }
    }

    Backup-CurrentOutputs

    $importCheck = Join-Path -Path $RunDir -ChildPath "check_imports.py"
    @'
import importlib
mods = [
    "numpy", "pandas", "matplotlib", "batman", "emcee", "corner",
    "lightkurve", "astroquery", "astropy", "scipy", "triceratops"
]
missing = []
for mod in mods:
    try:
        importlib.import_module(mod)
    except Exception as exc:
        missing.append((mod, str(exc)))
if missing:
    for mod, err in missing:
        print(f"MISSING {mod}: {err}")
    raise SystemExit(1)
print("All required imports OK")
'@ | Set-Content -LiteralPath $importCheck -Encoding ASCII

    Invoke-LoggedCommand -Name "00_import_check" -FilePath $script:PythonExe -ArgumentList @($importCheck) -TimeoutMinutes 10 -Critical $true | Out-Null

    $externalToolAudit = Join-Path -Path $RunDir -ChildPath "external_validation_tools_audit.py"
    @'
import importlib
import importlib.metadata as metadata
import importlib.util
import shutil

tools = [
    ("BATMAN", "batman", "used by the local transit-model scripts"),
    ("TRICERATOPS", "triceratops", "used by the local screening script"),
    ("VESPA", "vespa", "formal FPP package; install attempted, but PyPI source build needs Microsoft C++ Build Tools on this Windows laptop"),
    ("PASTIS", "pastis", "validation/modeling framework; usually needs dedicated setup"),
    ("Juliet", "juliet", "joint photometry/RV modeling; not required without RV data"),
    ("RadVel", "radvel", "RV modeling; not useful without RV time series"),
    ("TensorFlow/AstroNet dependency", "tensorflow", "AstroNet-like classifiers need trained models and image inputs"),
]

print("External validation/modeling tool availability audit")
print("This audit is informational. Missing or unusable packages do not fail the overnight run.")
for label, module, note in tools:
    found = importlib.util.find_spec(module) is not None
    if not found:
        print(f"{label:32s} module={module:14s} installed=False import_ok=False | {note}")
        continue
    try:
        mod = importlib.import_module(module)
        version = getattr(mod, "__version__", None)
        if version is None:
            try:
                version = metadata.version(module)
            except Exception:
                version = "unknown"
        print(f"{label:32s} module={module:14s} installed=True import_ok=True version={version} | {note}")
    except Exception as exc:
        print(f"{label:32s} module={module:14s} installed=True import_ok=False error={type(exc).__name__}: {exc} | {note}")

for command in ["vespa", "radvel", "pastis", "blender", "dave", "astronet"]:
    print(f"command {command:12s} found={shutil.which(command) is not None}")

print("PASTIS on PyPI is not the exoplanet PASTIS package; DAVE on PyPI is not the TESS/K2 DAVE vetter. They are intentionally not installed as false positives.")
print("BLENDER, DAVE, PASTIS, and AstroNet are not simple drop-in local scripts here; they require dedicated products/models.")
print("The current overnight run therefore logs their availability but continues with the reproducible local BATMAN/MCMC/FPP/TRICERATOPS workflow.")
'@ | Set-Content -LiteralPath $externalToolAudit -Encoding ASCII

    Invoke-LoggedCommand -Name "00b_external_validation_tools_audit" -FilePath $script:PythonExe -ArgumentList @($externalToolAudit) -TimeoutMinutes 10 -Critical $false -IgnoreFailure $true | Out-Null
    Write-ScienceCheck -Label "before"

    Invoke-PythonScript -Name "01_verify_baseline" -ScriptPath "scripts\verify_final.py" -TimeoutMinutes 15 -Critical $true | Out-Null

    Invoke-PythonScript -Name "02_stellar_params" -ScriptPath "scripts\stellar_params.py" -TimeoutMinutes 90 -Critical $true -CoolDown $true | Out-Null
    Assert-LimbDarkeningSource

    Invoke-PythonScript -Name "03_archive_enrichment" -ScriptPath "scripts\archive_enrichment.py" -TimeoutMinutes 90 -Critical $true -CoolDown $true | Out-Null

    Invoke-PythonScript -Name "03b_query_spectroscopic_archives" -ScriptPath "scripts\query_spectroscopic_archives.py" -TimeoutMinutes 180 -Critical $false -IgnoreFailure $true -CoolDown $true | Out-Null

    Invoke-PythonScript -Name "04_alias_120s_analysis" -ScriptPath "scripts\alias_120s_analysis.py" -TimeoutMinutes 120 -Critical $true -CoolDown $true | Out-Null

    Invoke-PythonScript -Name "05_build_120s_reference_lightcurve" -ScriptPath "scripts\build_120s_reference_lightcurve.py" -TimeoutMinutes 120 -Critical $true -CoolDown $true | Out-Null

    Invoke-PythonScript -Name "06_transit_model_120s_corrected" -ScriptPath "scripts\transit_model_120s_corrected.py" -TimeoutMinutes 240 -Critical $true -CoolDown $true | Out-Null
    Write-ScienceCheck -Label "after_main_fit"
    Assert-ScienceRanges
    Snapshot-CoreOutputs -Label "after_main_fit"

    Invoke-PythonScript -Name "07_transit_model_120s_density_locked" -ScriptPath "scripts\transit_model_120s_density_locked.py" -TimeoutMinutes 180 -Critical $true -CoolDown $true | Out-Null

    Invoke-PythonScript -Name "08_transit_model_120s_eccentric" -ScriptPath "scripts\transit_model_120s_eccentric.py" -TimeoutMinutes 240 -Critical $true -CoolDown $true | Out-Null

    Invoke-PythonScript -Name "09_false_positive_tests_120s" -ScriptPath "scripts\false_positive_tests_120s.py" -TimeoutMinutes 60 -Critical $true | Out-Null

    Invoke-PythonScript -Name "10_gaia_contamination_check" -ScriptPath "scripts\gaia_contamination_check.py" -TimeoutMinutes 90 -Critical $true -CoolDown $true | Out-Null

    Invoke-PythonScript -Name "11_dilution_robustness" -ScriptPath "scripts\dilution_robustness.py" -TimeoutMinutes 30 -Critical $true | Out-Null

    Invoke-PythonScript -Name "12_tess_source_localization_120s" -ScriptPath "scripts\tess_source_localization_120s.py" -TimeoutMinutes 120 -Critical $true -CoolDown $true | Out-Null

    Invoke-PythonScript -Name "13_stellar_activity" -ScriptPath "scripts\stellar_activity.py" -TimeoutMinutes 90 -Critical $true -CoolDown $true | Out-Null

    Invoke-PythonScript -Name "14_ttv_analysis" -ScriptPath "scripts\ttv_analysis.py" -TimeoutMinutes 90 -Critical $true | Out-Null

    Invoke-PythonScript -Name "15_statistical_validation" -ScriptPath "scripts\statistical_validation.py" -TimeoutMinutes 60 -Critical $true | Out-Null

    Invoke-PythonScript -Name "16_spoc_dv_extract" -ScriptPath "scripts\spoc_dv_extract.py" -TimeoutMinutes 60 -Critical $true | Out-Null

    Invoke-PythonScript -Name "17_parse_dv_xml_audit" -ScriptPath "scripts\parse_dv_xml.py" -TimeoutMinutes 30 -Critical $false -IgnoreFailure $true | Out-Null

    Invoke-PythonScript -Name "18_triceratops_validation_50000" -ScriptPath "scripts\triceratops_validation.py" -Arguments @("--n", "$TriceratopsDraws", "--search-radius", "4", "--bins", "240", "--window-days", "0.70") -TimeoutMinutes 240 -Critical $true -CoolDown $true | Out-Null
    Snapshot-CoreOutputs -Label ("triceratops_{0}" -f $TriceratopsDraws)

    if ($RunStressTriceratops) {
        Invoke-PythonScript -Name "19_triceratops_validation_100000_stress" -ScriptPath "scripts\triceratops_validation.py" -Arguments @("--n", "$TriceratopsStressDraws", "--search-radius", "4", "--bins", "240", "--window-days", "0.70") -TimeoutMinutes 300 -Critical $false -IgnoreFailure $true -CoolDown $true | Out-Null
        Snapshot-CoreOutputs -Label ("triceratops_{0}_stress" -f $TriceratopsStressDraws)
    }
    else {
        Write-Log "Stress TRICERATOPS run disabled by parameter."
    }

    if ($CompileLatex) {
        $pdflatex = Resolve-Executable -Name "pdflatex.exe" -Fallbacks @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Programs\MiKTeX\miktex\bin\x64\pdflatex.exe"))
        $bibtex = Resolve-Executable -Name "bibtex.exe" -Fallbacks @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Programs\MiKTeX\miktex\bin\x64\bibtex.exe"))

        if ((Test-Path -LiteralPath (Join-Path -Path $Root -ChildPath "arxiv_main.tex")) -and $pdflatex -and $bibtex) {
            Invoke-LoggedCommand -Name "20_latex_pdflatex_pass1" -FilePath $pdflatex -ArgumentList @("-interaction=nonstopmode", "arxiv_main.tex") -TimeoutMinutes 30 -Critical $false -IgnoreFailure $true | Out-Null
            Invoke-LoggedCommand -Name "21_latex_bibtex" -FilePath $bibtex -ArgumentList @("arxiv_main") -TimeoutMinutes 15 -Critical $false -IgnoreFailure $true | Out-Null
            Invoke-LoggedCommand -Name "22_latex_pdflatex_pass2" -FilePath $pdflatex -ArgumentList @("-interaction=nonstopmode", "arxiv_main.tex") -TimeoutMinutes 30 -Critical $false -IgnoreFailure $true | Out-Null
            Invoke-LoggedCommand -Name "23_latex_pdflatex_pass3" -FilePath $pdflatex -ArgumentList @("-interaction=nonstopmode", "arxiv_main.tex") -TimeoutMinutes 30 -Critical $false -IgnoreFailure $true | Out-Null
        }
        else {
            Write-Log "LaTeX compile skipped: arxiv_main.tex or MiKTeX executables not found."
        }
    }
    else {
        Write-Log "LaTeX compile disabled by parameter."
    }

    Invoke-PythonScript -Name "24_verify_final" -ScriptPath "scripts\verify_final.py" -TimeoutMinutes 15 -Critical $true | Out-Null
    Write-ScienceCheck -Label "final"
    Snapshot-CoreOutputs -Label "final"
    Write-RunSummaryMarkdown

    Write-Log "OVERNIGHT PIPELINE COMPLETE"
    Write-Log "Morning summary: $SummaryMd"
    exit 0
}
catch {
    Write-Log "FATAL: $($_.Exception.Message)"
    Write-RunSummaryMarkdown
    exit 1
}
finally {
    Disable-KeepAwake
}
