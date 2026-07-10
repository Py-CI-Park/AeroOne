Set-StrictMode -Version Latest

$script:PhaseOrder = @{}

function Initialize-RotationJournal {
    param([Parameter(Mandatory = $true)][hashtable]$PhaseOrder)

    $script:PhaseOrder = $PhaseOrder.Clone()
}

function Read-RotationJournalCandidate {
    param([string]$Path, [string]$WorkspaceRoot)

    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        return $null
    }
    Assert-SecureAcl -Path $Path
    $null = Assert-SinglePhysicalFile -Path $Path
    try {
        $candidate = Read-ProtectedJson -Path $Path -Purpose 'rotation-journal'
        $validated = Invoke-RotationPython -WorkspaceRoot $WorkspaceRoot -Request @{
            action = 'journal_validate'
            journal = $candidate
        }
        return $validated.journal
    } catch {
        return $null
    }
}

function Read-RotationJournal {
    param([string]$CurrentPath, [string]$PreviousPath, [string]$WorkspaceRoot)

    $current = Read-RotationJournalCandidate -Path $CurrentPath -WorkspaceRoot $WorkspaceRoot
    $previous = Read-RotationJournalCandidate -Path $PreviousPath -WorkspaceRoot $WorkspaceRoot
    if ($null -ne $current -and $null -ne $previous) {
        if ([int]$current.sequence -ne ([int]$previous.sequence + 1)) {
            throw 'journal-sequence-invalid'
        }
        return $current
    }
    if ($null -ne $current) {
        return $current
    }
    if ($null -ne $previous) {
        return $previous
    }
    throw 'journal-invalid'
}

function Write-JournalPhase {
    param(
        $Journal,
        [string]$Phase,
        [string]$JournalPath,
        [string]$PreviousPath,
        [string]$WorkspaceRoot
    )

    if (-not $script:PhaseOrder.ContainsKey($Phase)) {
        throw 'journal-phase-invalid'
    }
    $advanced = Invoke-RotationPython -WorkspaceRoot $WorkspaceRoot -Request @{
        action = 'journal_advance'
        journal = $Journal
        phase = $Phase
    }
    Write-ProtectedJson -Value $advanced.journal -Path $JournalPath -Purpose 'rotation-journal' -BackupPath $PreviousPath
    return $advanced.journal
}

Export-ModuleMember -Function @(
    'Initialize-RotationJournal',
    'Read-RotationJournal',
    'Write-JournalPhase'
)
