Set-StrictMode -Version Latest

if ($null -eq ('AeroOneRotationClipboardNative' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;

public static class AeroOneRotationClipboardNative
{
    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool OpenClipboard(IntPtr owner);

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool CloseClipboard();

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool EmptyClipboard();

    [DllImport("user32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool IsClipboardFormatAvailable(uint format);

    [DllImport("user32.dll", SetLastError = true)]
    public static extern IntPtr GetClipboardData(uint format);

    [DllImport("kernel32.dll", SetLastError = true)]
    public static extern IntPtr GlobalLock(IntPtr memory);

    [DllImport("kernel32.dll", SetLastError = true)]
    [return: MarshalAs(UnmanagedType.Bool)]
    public static extern bool GlobalUnlock(IntPtr memory);
}
'@
}
$script:ClipboardMaximumAttempts = 20
$script:ClipboardRetryMilliseconds = 250

function Set-RotationSecureClipboard {
    param([Parameter(Mandatory = $true)][string]$Text)

    Add-Type -AssemblyName PresentationCore
    $data = [Windows.DataObject]::new()
    $data.SetData([Windows.DataFormats]::UnicodeText, [object]$Text)
    $data.SetData('ExcludeClipboardContentFromMonitorProcessing', [object][int]1)
    $data.SetData('CanIncludeInClipboardHistory', [object][int]0)
    $data.SetData('CanUploadToCloudClipboard', [object][int]0)
    if (-not $data.GetDataPresent('ExcludeClipboardContentFromMonitorProcessing', $false) -or
        [int]$data.GetData('CanIncludeInClipboardHistory', $false) -ne 0 -or
        [int]$data.GetData('CanUploadToCloudClipboard', $false) -ne 0) {
        throw 'clipboard-exclusion-metadata-invalid'
    }
    try {
        $publishedSuccessfully = $false
        for ($attempt = 1; $attempt -le $script:ClipboardMaximumAttempts; $attempt += 1) {
            try {
                [Windows.Clipboard]::SetDataObject($data, $true)
                $publishedSuccessfully = $true
                break
            } catch [Runtime.InteropServices.COMException] {
                if ($attempt -lt $script:ClipboardMaximumAttempts) {
                    Start-Sleep -Milliseconds $script:ClipboardRetryMilliseconds
                }
            } catch [Runtime.InteropServices.ExternalException] {
                if ($attempt -lt $script:ClipboardMaximumAttempts) {
                    Start-Sleep -Milliseconds $script:ClipboardRetryMilliseconds
                }
            }
        }
        if (-not $publishedSuccessfully) {
            throw 'clipboard-secure-set-failed'
        }
        $status = Get-RotationSecureClipboardStatus -Expected $Text
        if (-not $status.TextMatches -or -not $status.Excluded -or
            $status.History -ne 0 -or $status.Cloud -ne 0) {
            $null = Clear-RotationOwnedClipboard -Expected $Text
            throw 'clipboard-exclusion-verification-failed'
        }
    } catch [Runtime.InteropServices.ExternalException] {
        throw 'clipboard-secure-set-failed'
    } catch [InvalidOperationException] {
        throw 'clipboard-secure-set-failed'
    }
}

function Get-RotationSecureClipboardStatus {
    param([Parameter(Mandatory = $true)][string]$Expected)

    Add-Type -AssemblyName PresentationCore
    for ($attempt = 1; $attempt -le $script:ClipboardMaximumAttempts; $attempt += 1) {
        try {
            $published = [Windows.Clipboard]::GetDataObject()
            if ($null -eq $published) {
                if ($attempt -eq $script:ClipboardMaximumAttempts) {
                    throw 'clipboard-read-timeout'
                }
                Start-Sleep -Milliseconds $script:ClipboardRetryMilliseconds
                continue
            }
            return [PSCustomObject]@{
                TextMatches = [string]$published.GetData([Windows.DataFormats]::UnicodeText, $false) -ceq $Expected
                Excluded = $published.GetDataPresent('ExcludeClipboardContentFromMonitorProcessing', $false)
                History = [int]$published.GetData('CanIncludeInClipboardHistory', $false)
                Cloud = [int]$published.GetData('CanUploadToCloudClipboard', $false)
            }
        } catch [Runtime.InteropServices.COMException] {
            if ($attempt -eq $script:ClipboardMaximumAttempts) {
                throw 'clipboard-read-timeout'
            }
            Start-Sleep -Milliseconds $script:ClipboardRetryMilliseconds
        } catch [Runtime.InteropServices.ExternalException] {
            if ($attempt -eq $script:ClipboardMaximumAttempts) {
                throw 'clipboard-read-timeout'
            }
            Start-Sleep -Milliseconds $script:ClipboardRetryMilliseconds
        }
    }
}

function Clear-RotationOwnedClipboard {
    param([Parameter(Mandatory = $true)][AllowEmptyString()][string]$Expected)

    if ([string]::IsNullOrEmpty($Expected)) {
        return 'Cleared'
    }
    if (-not [AeroOneRotationClipboardNative]::OpenClipboard([IntPtr]::Zero)) {
        return 'Failed'
    }
    try {
        if (-not [AeroOneRotationClipboardNative]::IsClipboardFormatAvailable(13)) {
            return 'NotOwned'
        }
        $handle = [AeroOneRotationClipboardNative]::GetClipboardData(13)
        if ($handle -eq [IntPtr]::Zero) {
            return 'Failed'
        }
        $pointer = [AeroOneRotationClipboardNative]::GlobalLock($handle)
        if ($pointer -eq [IntPtr]::Zero) {
            return 'Failed'
        }
        try {
            $current = [Runtime.InteropServices.Marshal]::PtrToStringUni($pointer)
        } finally {
            $null = [AeroOneRotationClipboardNative]::GlobalUnlock($handle)
        }
        if ($current -cne $Expected) {
            return 'NotOwned'
        }
        if (-not [AeroOneRotationClipboardNative]::EmptyClipboard()) {
            return 'Failed'
        }
        return 'Cleared'
    } finally {
        $null = [AeroOneRotationClipboardNative]::CloseClipboard()
    }
}

function Resolve-RotationClipboardDecision {
    param(
        [Parameter(Mandatory = $true)]
        [ValidateSet('Cleared', 'NotOwned', 'Failed')]
        [string]$Result,
        [Parameter(Mandatory = $true)][int]$Attempt,
        [Parameter(Mandatory = $true)][int]$MaximumAttempts
    )

    if ($Result -ne 'Failed') {
        return [PSCustomObject]@{
            KeepOwnership = $false
            ScheduleRetry = $false
            AllowClose = $true
            OperatorActionRequired = $false
        }
    }
    $automaticRetry = $Attempt -lt $MaximumAttempts
    return [PSCustomObject]@{
        KeepOwnership = $true
        ScheduleRetry = $automaticRetry
        AllowClose = $false
        OperatorActionRequired = -not $automaticRetry
    }
}

Export-ModuleMember -Function @(
    'Set-RotationSecureClipboard',
    'Get-RotationSecureClipboardStatus',
    'Clear-RotationOwnedClipboard',
    'Resolve-RotationClipboardDecision'
)
